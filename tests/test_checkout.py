import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server


class Checkout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = server.DB
        server.DB = Path(self.tmp.name) / 'store'
        server.init()
        year = server.date.today().year
        server.mutate('/api/company', dict(name='Test', address='Test', year_start=f'{year}-01-01', year_end=f'{year}-12-31'))
        for category in ('cash', 'bank'):
            server.mutate('/api/ledgers', dict(name=category, category=category))
        self.ledgers = {r['category']: r['id'] for r in server.snapshot()['ledgers']}
        server.mutate('/api/products', dict(name='Medicine', batch='A', expiry=f'{year+2}-01', price=112, tax=12, tax_inclusive=True))
        self.pid = server.snapshot()['products'][0]['id']
        server.mutate('/api/documents', dict(kind='purchase', party='Supplier', lines=[dict(product=self.pid, qty=20, price=50)]))

    def tearDown(self):
        server.DB = self.previous
        self.tmp.cleanup()

    def payload(self, mode='cash', amount='120', **extra):
        return dict(kind='sale', party='Customer', request_key='checkout-test', lines=[dict(product=self.pid, qty=1)], payment=dict(mode=mode, ledger=self.ledgers.get(mode), amount=amount), **extra)

    def test_cash_change_and_balanced_receipt(self):
        state = server.mutate('/api/checkout', self.payload())
        doc = next(d for d in state['documents'] if d['id'] == state['posted_document'])
        self.assertEqual(doc['checkout']['received'], 11200)
        self.assertEqual(doc['checkout']['change'], 800)
        self.assertEqual(state['products'][0]['stock'], 19)
        self.assertEqual(sum(j['debit']-j['credit'] for j in state['journal']), 0)
        self.assertEqual(next(r['balance_paise'] for r in state['outstanding'] if r['invoice'] == doc['id']), 0)

    def test_partial_bank_receipt(self):
        state = server.mutate('/api/checkout', self.payload('bank', '50'))
        self.assertEqual(next(r['balance_paise'] for r in state['outstanding'] if r['invoice'] == state['posted_document']), 6200)

    def test_credit_has_no_receipt(self):
        state = server.mutate('/api/checkout', self.payload('credit', '0'))
        self.assertEqual(state['settlements'], [])
        self.assertEqual(next(r['balance_paise'] for r in state['outstanding'] if r['invoice'] == state['posted_document']), 11200)

    def test_invalid_payment_rolls_back_stock_invoice_and_journal(self):
        before = server.snapshot()
        for mode, amount in [('bank', '120'), ('credit', '1'), ('cash', '0')]:
            with self.assertRaises(ValueError):
                server.mutate('/api/checkout', self.payload(mode, amount))
            after = server.snapshot()
            for key in ('products', 'documents', 'journal', 'settlements'):
                self.assertEqual(after[key], before[key])
        data = self.payload()
        data['payment']['ledger'] = self.ledgers['bank']
        with self.assertRaises(ValueError):
            server.mutate('/api/checkout', data)
        self.assertEqual(server.snapshot()['products'], before['products'])

    def test_retry_returns_original_invoice(self):
        data = self.payload()
        first = server.mutate('/api/checkout', data)
        server.mutate('/api/checkout', {**data, 'request_key': 'another'})
        retry = server.mutate('/api/checkout', data)
        self.assertEqual(retry['posted_document'], first['posted_document'])
        self.assertEqual(len(retry['settlements']), 2)
        self.assertEqual(retry['products'][0]['stock'], 18)

    def test_request_key_cannot_cross_posting_endpoints(self):
        data = self.payload()
        server.mutate('/api/documents', data)
        with self.assertRaises(ValueError):
            server.mutate('/api/checkout', data)
        self.assertEqual(server.snapshot()['settlements'], [])

    def test_checkout_requires_key_and_sale_kind(self):
        data = self.payload()
        del data['request_key']
        with self.assertRaises(ValueError):
            server.mutate('/api/checkout', data)
        data = self.payload()
        data['kind'] = 'purchase'
        with self.assertRaises(ValueError):
            server.mutate('/api/checkout', data)

    def test_quote_tax_components_match_saved_invoice(self):
        data = self.payload()
        quote = server.mutate('/api/quote', data)
        self.assertEqual(quote['lines'][0]['taxable_paise'], 10000)
        self.assertEqual(quote['lines'][0]['tax_paise'], 1200)
        state = server.mutate('/api/checkout', data)
        doc = next(d for d in state['documents'] if d['id'] == state['posted_document'])
        self.assertEqual(round(doc['total'] * 100), quote['total_paise'])
