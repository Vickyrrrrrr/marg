import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server
import security


class CounterWorkflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = server.DB
        server.DB = Path(self.tmp.name) / 'store'
        server.init()
        with server.connection() as c:
            for name in ('owner', 'other'):
                security.create_operator(c, dict(username=name, password='test-password-123', role='admin'))
            self.owner = dict(c.execute("SELECT id,username,role FROM operator WHERE username='owner'").fetchone())
            self.other = dict(c.execute("SELECT id,username,role FROM operator WHERE username='other'").fetchone())
        year = server.date.today().year
        server.mutate('/api/company', dict(name='Test pharmacy', address='Test', year_start=f'{year}-01-01', year_end=f'{year}-12-31'))
        server.mutate('/api/products', dict(name='Medicine', batch='A', expiry=f'{year+2}-01', price=10, tax=0))
        self.pid = server.snapshot()['products'][0]['id']
        self.doc('purchase', 10)

    def tearDown(self):
        server.DB = self.original
        self.tmp.cleanup()

    def doc(self, kind, qty, **extra):
        return server.mutate('/api/documents', dict(kind=kind, party='Test party', lines=[dict(product=self.pid, qty=qty, price=5)], **extra), self.owner)

    def hold(self):
        return server.mutate('/api/held', dict(label='Counter A', payload=dict(party='Test customer', lines=[dict(product=self.pid, qty=2)])), self.owner)['held_bills'][0]['id']

    def test_hold_persists_without_stock_or_accounting_effects(self):
        before = server.snapshot()
        identifier = self.hold()
        server.init()
        after = server.snapshot()
        self.assertEqual(after['products'], before['products'])
        self.assertEqual(after['journal'], before['journal'])
        self.assertEqual(after['documents'], before['documents'])
        self.assertEqual(after['held_bills'][0]['id'], identifier)

    def test_post_consumes_held_bill_atomically_and_retry_does_not_duplicate(self):
        identifier = self.hold()
        state = self.doc('sale', 2, draft_id=identifier, request_key='held-post')
        self.assertEqual(state['held_bills'], [])
        self.assertEqual(state['products'][0]['stock'], 8)
        state = self.doc('sale', 2, draft_id=identifier, request_key='held-post')
        self.assertEqual(len(state['sales']), 1)

    def test_failed_sale_retains_held_bill_and_owner_privacy(self):
        identifier = self.hold()
        with self.assertRaises(ValueError):
            self.doc('sale', 11, draft_id=identifier)
        state = server.snapshot()
        self.assertEqual(len(state['held_bills']), 1)
        other = {**self.other, 'role': 'cashier'}
        self.assertEqual(security.redact(state, other)['held_bills'], [])
        with self.assertRaises(ValueError):
            server.mutate('/api/held-delete', dict(id=identifier), other)
        with self.assertRaises(ValueError):
            server.mutate('/api/held', dict(label='Rx', payload=dict(prescription={'patient': 'Private patient'}, lines=[dict(product=self.pid, qty=1)])), other)

    def test_recall_blocks_quote_sale_and_quarantine_release(self):
        self.doc('sale', 2)
        self.doc('return', 1, reference=2)
        server.mutate('/api/recall', dict(product=self.pid, reason='Manufacturer quality recall', reference='Test recall'), self.owner)
        for path in ('/api/quote', '/api/documents'):
            with self.assertRaisesRegex(ValueError, 'Recalled'):
                server.mutate(path, dict(kind='sale', lines=[dict(product=self.pid, qty=1)]), self.owner)
        with self.assertRaisesRegex(ValueError, 'Recalled'):
            server.mutate('/api/inspection', dict(product=self.pid, qty=1, disposition='release', reason='Intact'), self.owner)
        state = server.snapshot()
        self.assertEqual(state['products'][0]['stock'], 8)
        self.assertEqual(state['products'][0]['quarantine'], 1)
        self.assertEqual(len(state['sales']), 1)

    def test_recall_closure_requires_authority_and_records_history(self):
        state = server.mutate('/api/recall', dict(product=self.pid, reason='Test recall'), self.owner)
        identifier = state['recalls'][0]['id']
        with self.assertRaises(PermissionError):
            server.mutate('/api/recall-close', dict(id=identifier, closure='Cleared'), {**self.other, 'role': 'cashier'})
        with self.assertRaises(ValueError):
            server.mutate('/api/recall-close', dict(id=identifier, closure=''), self.owner)
        server.mutate('/api/recall-close', dict(id=identifier, closure='Manufacturer cleared batch'), self.owner)
        state = self.doc('sale', 1)
        self.assertEqual(len(state['recalls']), 1)
        self.assertEqual(state['recalls'][0]['closure'], 'Manufacturer cleared batch')
        self.assertEqual(state['products'][0]['stock'], 9)

    def test_multiline_purchase_is_atomic_and_supplier_invoice_is_unique(self):
        server.mutate('/api/products', dict(name='Second medicine', batch='B', expiry='2030-01', price=20, tax=12))
        second = next(p['id'] for p in server.snapshot()['products'] if p['name'] == 'Second medicine')
        payload = dict(kind='purchase', party='Test party', supplier_invoice='SUP-1', request_key='multiline', lines=[dict(product=self.pid, qty=2, price=4), dict(product=second, qty=3, price=8)])
        state = server.mutate('/api/documents', payload, self.owner)
        self.assertEqual(len(state['documents'][-1]['lines']), 2)
        self.assertEqual(state['documents'][-1]['total'], 34.88)
        self.assertEqual(state['documents'][-1]['supplier_invoice'], 'SUP-1')
        server.mutate('/api/documents', payload, self.owner)
        with self.assertRaisesRegex(ValueError, 'already been received'):
            server.mutate('/api/documents', {**payload, 'supplier_invoice': 'sup-1', 'request_key': 'duplicate-number'}, self.owner)
        before = server.snapshot()
        with self.assertRaises(ValueError):
            server.mutate('/api/documents', {**payload, 'supplier_invoice': 'SUP-2', 'request_key': 'bad-line', 'lines': [payload['lines'][0], dict(product='missing', qty=1, price=4)]}, self.owner)
        after = server.snapshot()
        self.assertEqual(after['products'], before['products'])
        self.assertEqual(after['journal'], before['journal'])
        self.assertEqual(after['documents'], before['documents'])
