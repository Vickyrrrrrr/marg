import sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server
class PartyIdentity(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.previous=server.DB;server.DB=Path(self.tmp.name)/'db';server.init();year=server.date.today().year
  server.mutate('/api/company',dict(name='Test',address='Test',year_start=f'{year}-01-01',year_end=f'{year}-12-31'))
  server.mutate('/api/products',dict(name='Test medicine',batch='T',price=100,tax=0));self.product=server.snapshot()['products'][0]['id'];self.doc('purchase',10,'Test supplier')
 def tearDown(self):server.DB=self.previous;self.tmp.cleanup()
 def doc(self,kind,qty,party='Test customer',**extra):
  d=dict(kind=kind,party=party,lines=[dict(product=self.product,qty=qty,price=50)]);d.update(extra);return server.mutate('/api/documents',d)
 def test_names_resolve_case_insensitively(self):
  first=self.doc('sale',1,'Test Customer')['sales'][-1];second=self.doc('sale',1,'test customer')['sales'][-1]
  self.assertEqual(first['party_ledger'],second['party_ledger']);self.assertEqual(second['party'],'Test Customer')
 def test_quote_does_not_create_party(self):
  before=server.snapshot()['ledgers'];server.mutate('/api/quote',dict(kind='sale',party='Not saved',lines=[dict(product=self.product,qty=1)]));self.assertEqual(before,server.snapshot()['ledgers'])
 def test_return_inherits_original_identity(self):
  original=self.doc('sale',2)['sales'][-1];returned=self.doc('return',1,'Wrong party',reference=original['id'])['documents'][-1]
  self.assertEqual(returned['party_ledger'],original['party_ledger']);self.assertEqual(returned['party'],original['party'])
 def test_party_classification(self):
  state=server.mutate('/api/parties',dict(name='Supplier only',category='supplier'));ledger=next(l for l in state['ledgers'] if l['name']=='Supplier only')
  with self.assertRaises(ValueError):self.doc('sale',1,party_ledger=ledger['id'])
  with self.assertRaises(ValueError):server.mutate('/api/parties',dict(name='Invalid',category='cash'))
 def test_receipt_clears_the_same_party_account(self):
  sale=self.doc('sale',1)['sales'][-1];server.mutate('/api/ledgers',dict(name='Till',category='cash'));cash=next(l['id'] for l in server.snapshot()['ledgers'] if l['category']=='cash')
  server.mutate('/api/settlements',dict(kind='receipt',date=server.date.today().isoformat(),ledger=cash,amount=100,request_key=str(uuid.uuid4()),allocations=[dict(invoice=sale['id'],amount=100)]))
  account=next(a for a in server.snapshot()['accounts'] if a['account'].startswith(f"Party ledger: {sale['party_ledger']}:"));self.assertEqual(account['debit'],account['credit'])
 def test_duplicate_party_and_wrong_return_ledger(self):
  sale=self.doc('sale',1)['sales'][-1]
  with self.assertRaises(ValueError):server.mutate('/api/parties',dict(name='test CUSTOMER',category='party'))
  other=server.mutate('/api/parties',dict(name='Other',category='customer'));identifier=next(l['id'] for l in other['ledgers'] if l['name']=='Other')
  with self.assertRaises(ValueError):self.doc('return',1,reference=sale['id'],party_ledger=identifier)

 def test_invoice_company_snapshot_is_immutable(self):
  original=self.doc('sale',1)['sales'][-1];company=server.snapshot()['company'];company['name']='Updated company';server.mutate('/api/company',company)
  saved=next(d for d in server.snapshot()['sales'] if d['id']==original['id'])
  self.assertEqual(saved['company_snapshot']['name'],'Test');self.assertEqual(server.snapshot()['company']['name'],'Updated company')

 def test_openings_and_invoice_post_to_same_party_ledger(self):
  old=server.DB;server.DB=Path(self.tmp.name)/'opening-case'
  try:
   server.init();year=server.date.today().year;server.mutate('/api/company',dict(name='Test',address='Test',year_start=f'{year}-01-01',year_end=f'{year}-12-31'))
   state=server.mutate('/api/parties',dict(name='Opening customer',category='customer'));customer=state['ledgers'][0]['id']
   server.mutate('/api/ledgers',dict(name='Capital',category='equity'));capital=next(l['id'] for l in server.snapshot()['ledgers'] if l['category']=='equity')
   state=server.mutate('/api/openings',dict(lines=[dict(ledger=customer,debit=100),dict(ledger=capital,credit=100)]))
   product_state=server.mutate('/api/products',dict(name='Opening case product',batch='O',price=100,tax=0));product=product_state['products'][0]['id']
   server.mutate('/api/documents',dict(kind='purchase',party='Opening supplier',lines=[dict(product=product,qty=1,price=50)]))
   sale=server.mutate('/api/documents',dict(kind='sale',party_ledger=customer,lines=[dict(product=product,qty=1)]))['sales'][-1]
   cash=server.mutate('/api/ledgers',dict(name='Opening till',category='cash'));cash_id=next(l['id'] for l in cash['ledgers'] if l['category']=='cash')
   state=server.mutate('/api/settlements',dict(kind='receipt',date=server.date.today().isoformat(),ledger=cash_id,amount=100,request_key=str(uuid.uuid4()),allocations=[dict(invoice=sale['id'],amount=100)]))
   account=next(a for a in state['accounts'] if a['account'].startswith(f'Party ledger: {customer}:'))
   self.assertEqual(account['debit']-account['credit'],10000)
  finally:server.DB=old
