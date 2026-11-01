import sys,tempfile,unittest,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server

class Settlements(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.previous=server.DB;server.DB=Path(self.tmp.name)/'store';server.init();year=server.date.today().year
  server.mutate('/api/company',dict(name='Test',address='Test',year_start=f'{year}-01-01',year_end=f'{year}-12-31'))
  server.mutate('/api/ledgers',dict(name='Till',category='cash'));self.ledger=server.snapshot()['ledgers'][0]['id']
  server.mutate('/api/products',dict(name='Test product',batch='A',expiry=f'{year+2}-01',price=112,tax=12,tax_inclusive=True))
  self.product=server.snapshot()['products'][0]['id'];self.purchase=self.doc('purchase',20,price=60)
 def tearDown(self):server.DB=self.previous;self.tmp.cleanup()
 def doc(self,kind,qty,party='Test party',reference=None,price=60):
  state=server.mutate('/api/documents',dict(kind=kind,party=party,reference=reference,lines=[dict(product=self.product,qty=qty,price=price)]));return state['documents'][-1]['id']
 def pay(self,kind,invoice,amount,key=None,**extra):
  d=dict(kind=kind,date=server.date.today().isoformat(),ledger=self.ledger,amount=amount,request_key=key or str(uuid.uuid4()),allocations=[dict(invoice=invoice,amount=amount)]);d.update(extra);return server.mutate('/api/settlements',d)
 def balance(self,invoice):return next(r['balance_paise'] for r in server.snapshot()['outstanding'] if r['invoice']==invoice)
 def test_partial_receipt_and_double_entry(self):
  sale=self.doc('sale',3);self.pay('receipt',sale,100);self.assertEqual(self.balance(sale),23600)
  state=self.pay('receipt',sale,236);self.assertEqual(self.balance(sale),0)
  self.assertEqual(sum(j['debit']-j['credit'] for j in state['journal']),0)
  with self.assertRaises(ValueError):self.pay('receipt',sale,1)
 def test_paid_invoice_return_and_refund(self):
  sale=self.doc('sale',3);self.pay('receipt',sale,336);self.doc('return',1,reference=sale)
  self.assertEqual(self.balance(sale),-11200);self.pay('refund',sale,112);self.assertEqual(self.balance(sale),0)
  with self.assertRaises(ValueError):self.pay('refund',sale,1)
 def test_supplier_payment_and_refund(self):
  self.pay('payment',self.purchase,1344);self.doc('purchase_return',2,reference=self.purchase)
  self.assertEqual(self.balance(self.purchase),-13440);self.pay('supplier_refund',self.purchase,134.4);self.assertEqual(self.balance(self.purchase),0)
 def test_duplicate_request_is_not_double_posted(self):
  sale=self.doc('sale',2);self.pay('receipt',sale,100,key='retry');state=self.pay('receipt',sale,100,key='retry');self.assertEqual(self.balance(sale),12400)
  self.assertEqual(len(state['settlements']),1)
  with self.assertRaises(ValueError):self.pay('receipt',sale,101,key='retry')
 def test_multi_invoice_party_and_total_validation(self):
  first=self.doc('sale',1);second=self.doc('sale',1)
  self.pay('receipt',first,224,allocations=[dict(invoice=first,amount=112),dict(invoice=second,amount=112)])
  self.assertEqual(self.balance(second),0)
  third=self.doc('sale',1,party='Another party');fourth=self.doc('sale',1)
  with self.assertRaises(ValueError):self.pay('receipt',third,224,allocations=[dict(invoice=third,amount=112),dict(invoice=fourth,amount=112)])
  self.assertEqual(self.balance(third),11200)
  with self.assertRaises(ValueError):self.pay('receipt',third,100,allocations=[dict(invoice=third,amount=99)])
 def test_only_one_concurrent_payment_can_clear_balance(self):
  sale=self.doc('sale',1)
  def attempt(_):
   try:self.pay('receipt',sale,112);return True
   except ValueError:return False
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
  self.assertEqual(sum(results),1);self.assertEqual(self.balance(sale),0)
 def test_account_type_and_period_locks(self):
  sale=self.doc('sale',1);server.mutate('/api/ledgers',dict(name='Expense',category='expense'))
  ledger=next(l['id'] for l in server.snapshot()['ledgers'] if l['name']=='Expense')
  with self.assertRaises(ValueError):self.pay('receipt',sale,112,ledger=ledger)
  server.mutate('/api/period-lock',dict(locked_through=server.date.today().isoformat()))
  with self.assertRaises(ValueError):self.pay('receipt',sale,112)
  self.assertEqual(self.balance(sale),11200)
