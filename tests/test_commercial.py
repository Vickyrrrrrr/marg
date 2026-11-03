import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server
import security


class CommercialTerms(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = server.DB
        server.DB = Path(self.tmp.name) / 'store'
        server.init()
        year = server.date.today().year
        server.mutate('/api/company', dict(name='Test', address='Test', year_start=f'{year}-01-01', year_end=f'{year}-12-31'))
        server.mutate('/api/products', dict(name='Medicine', batch='A', price=112, tax=12, tax_inclusive=True, pack_size=10))
        self.pid = server.snapshot()['products'][0]['id']
        self.post('purchase', 30, price=60)

    def tearDown(self):
        server.DB = self.old
        self.tmp.cleanup()

    def post(self, kind, qty, **terms):
        reference = terms.pop('reference', None)
        state = server.mutate('/api/documents', dict(kind=kind, party='Test party', reference=reference, lines=[dict(product=self.pid, qty=qty, **terms)]))
        return state['documents'][-1]

    def test_discount_inclusive_and_full_return_reconciles(self):
        sale = self.post('sale', 3, discount_percent='12.34')
        self.assertEqual(round(sale['total']*100), 29454)
        returned = [self.post('return', 1, reference=sale['id']) for _ in range(3)]
        self.assertEqual(sum(round(d['total']*100) for d in returned), 29454)
        self.assertTrue(all(d['lines'][0]['discount_bps'] == 1234 for d in returned))
        self.assertEqual(sum(d['lines'][0]['taxable'] for d in returned), sale['lines'][0]['taxable'])
        self.assertEqual(sum(j['debit']-j['credit'] for j in server.snapshot()['journal']), 0)

    def test_exclusive_discount_rounding_and_quote_purity(self):
        before = server.snapshot()
        q = server.mutate('/api/quote', dict(kind='purchase', party='New supplier', lines=[dict(product=self.pid, qty=3, price='0.05', discount_percent='10')]))
        self.assertEqual(q['total_paise'], 16)
        self.assertEqual(q['lines'][0]['taxable_paise'], 14)
        self.assertEqual(server.snapshot()['ledgers'], before['ledgers'])
        self.assertEqual(server.snapshot()['documents'], before['documents'])

    def test_purchase_free_units_are_loose_and_not_charged(self):
        d = self.post('purchase', 2, unit='pack', free_qty=3, price=50, discount_percent=10)
        self.assertEqual(d['lines'][0]['qty'], 23)
        self.assertEqual(d['lines'][0]['free_qty'], 3)
        self.assertEqual(round(d['total']*100), 100800)
        self.assertEqual(server.snapshot()['products'][0]['stock'], 53)

    def test_supplier_returns_allocate_paid_value_over_received_units(self):
        d = self.post('purchase', 10, free_qty=2, price=50, discount_percent=10)
        first = self.post('purchase_return', 5, reference=d['id'])
        second = self.post('purchase_return', 7, reference=d['id'])
        self.assertEqual(round((first['total']+second['total'])*100), round(d['total']*100))
        self.assertEqual(first['lines'][0]['taxable']+second['lines'][0]['taxable'],d['lines'][0]['taxable'])
        with self.assertRaises(ValueError):self.post('purchase_return',1,reference=d['id'])

    def test_invalid_discount_and_free_units_roll_back(self):
        before = server.snapshot()
        for terms in [dict(discount_percent=-1),dict(discount_percent=101),dict(discount_percent='0.001'),dict(discount_percent='NaN'),dict(free_qty=1),dict(free_qty=-1),dict(free_qty='1.5')]:
            with self.subTest(terms=terms), self.assertRaises(ValueError):self.post('sale',1,**terms)
        after=server.snapshot()
        for field in ('products','documents','journal'):self.assertEqual(before[field],after[field])

    def test_checkout_creates_and_uses_customer_ledger(self):
        state=server.mutate('/api/checkout',dict(kind='sale',party='New customer',request_key='customer-ledger',payment=dict(mode='credit',amount=0),lines=[dict(product=self.pid,qty=1,discount_percent=10)]))
        d=next(d for d in state['documents'] if d['id']==state['posted_document'])
        party=next(l for l in state['ledgers'] if l['name']=='New customer')
        self.assertEqual(d['party_ledger'],party['id'])
        self.assertTrue(any(j['document']==d['id'] and j['account'].startswith(f"Party ledger: {party['id']}:") for j in state['journal']))

    def test_held_bill_preserves_discount(self):
        with server.connection() as c:
            security.create_operator(c,dict(username='owner',password='test-password-123',role='admin'))
            actor=dict(c.execute('SELECT * FROM operator').fetchone())
        state=server.mutate('/api/held',dict(label='Counter',payload=dict(lines=[dict(product=self.pid,qty=2,discount_percent='7.25')])),actor)
        self.assertEqual(state['held_bills'][0]['payload']['lines'][0]['discount_percent'],7.25)
        server.init()
        self.assertEqual(server.snapshot()['held_bills'][0]['payload']['lines'][0]['discount_percent'],7.25)

    def test_reinitialization_preserves_terms(self):
        d=self.post('purchase',2,free_qty=1,price=50,discount_percent=5)
        server.init();server.init()
        saved=next(x for x in server.snapshot()['documents'] if x['id']==d['id'])
        self.assertEqual(saved['lines'][0]['discount_bps'],500)
        self.assertEqual(saved['lines'][0]['free_qty'],1)
