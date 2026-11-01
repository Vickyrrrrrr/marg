import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server,security

class Pharmacy(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.previous=server.DB;server.DB=Path(self.tmp.name)/'db';server.init();year=server.date.today().year
  server.mutate('/api/company',dict(name='Test',address='Test',drug_licence='TEST-DL',year_start=f'{year}-01-01',year_end=f'{year}-12-31'))
  d=dict(name='Test medicine',batch='H1A',price=100,tax=0,manufacturer='Test manufacturer',schedule='H1',expiry=f'{year+2}-01',barcode='TESTBAR',generic_name='Test generic',strength='Test strength')
  self.product=server.mutate('/api/products',d)['products'][0]['id'];server.mutate('/api/documents',dict(kind='purchase',party='Supplier',lines=[dict(product=self.product,qty=20,price=50)]))
  with server.connection() as c:
   security.create_operator(c,dict(username='pharmacist',password='test-password-long',role='pharmacist',registration='TEST-REG'))
   u=c.execute('SELECT id,username,role,registration FROM operator').fetchone();self.actor=dict(u)
  self.rx=dict(reference='RX-001',prescription_date=server.date.today().isoformat(),patient='Test patient',patient_address='Test address',prescriber='Test prescriber',prescriber_address='Test clinic')
 def tearDown(self):server.DB=self.previous;self.tmp.cleanup()
 def sale(self,**extra):
  d=dict(kind='sale',party='Customer',prescription=self.rx,lines=[dict(product=self.product,qty=2)]);d.update(extra);return server.mutate('/api/documents',d,self.actor)
 def test_scheduled_sale_requires_prescription(self):
  before=server.snapshot()
  with self.assertRaises(ValueError):self.sale(prescription={})
  self.assertEqual(server.snapshot()['products'][0]['stock'],20);self.assertEqual(len(server.snapshot()['documents']),len(before['documents']))
 def test_scheduled_sale_requires_pharmacist(self):
  with self.assertRaises(ValueError):server.mutate('/api/documents',dict(kind='sale',party='Customer',prescription=self.rx,lines=[dict(product=self.product,qty=1)]),None)
 def test_supply_register_is_atomic_and_retained_after_return(self):
  state=self.sale();sale=state['sales'][-1];r=state['prescription_register'][0];self.assertEqual(r['patient'],'Test patient');self.assertEqual(r['quantity'],2);self.assertEqual(r['registration'],'TEST-REG')
  state=server.mutate('/api/documents',dict(kind='return',reference=sale['id'],lines=[dict(product=self.product,qty=1)]));self.assertEqual(len(state['prescription_register']),1);self.assertEqual(state['prescription_register'][0]['quantity'],2)
 def test_prescription_dates_and_null_fields(self):
  rx={**self.rx,'prescription_date':f'{server.date.today().year+1}-01-01'}
  with self.assertRaises(ValueError):self.sale(prescription=rx)
  with self.assertRaises(ValueError):self.sale(prescription={**self.rx,'patient':None})
 def test_wholesale_licences(self):
  with server.connection() as c:
   security.create_operator(c,dict(username='manager',password='test-manager-password',role='manager'))
   self.actor=dict(c.execute("SELECT id,username,role,registration FROM operator WHERE username='manager'").fetchone())
  state=server.mutate('/api/parties',dict(name='Business customer',category='customer'));customer=next(l['id'] for l in state['ledgers'] if l['name']=='Business customer')
  with self.assertRaisesRegex(ValueError,'licences'):self.sale(trade='wholesale',party_ledger=customer,prescription=None)
  licensed=server.mutate('/api/parties',dict(name='Licensed customer',category='customer',drug_licence='TEST-CUSTOMER-DL'));identifier=next(l['id'] for l in licensed['ledgers'] if l['name']=='Licensed customer')
  state=self.sale(trade='wholesale',party_ledger=identifier,prescription=None);self.assertEqual(state['sales'][-1]['trade'],'wholesale');self.assertEqual(state['prescription_register'],[])
 def test_barcode_identity_and_batch_reuse(self):
  d=dict(name='Test medicine',batch='H1B',price=100,tax=0,manufacturer='Test manufacturer',schedule='H1',expiry=f'{server.date.today().year+2}-02',barcode='TESTBAR',generic_name='Test generic',strength='Test strength')
  self.assertEqual(len(server.mutate('/api/products',d)['products']),2)
  with self.assertRaises(ValueError):server.mutate('/api/products',{**d,'name':'Different medicine','batch':'Other'})
 def test_medical_records_are_hidden_from_cashier_and_accountant(self):
  state=self.sale()
  for role in ('cashier','accountant','manager'):self.assertEqual(security.redact(state,dict(id=999,role=role))['prescription_register'],[])
  self.assertEqual(len(security.redact(state,self.actor)['prescription_register']),1)
 def test_pharmacist_registration_is_required(self):
  with server.connection() as c:
   with self.assertRaises(ValueError):security.create_operator(c,dict(username='invalid',password='test-password-long',role='pharmacist'))
 def test_schedule_x_is_not_silently_accepted(self):
  with self.assertRaises(ValueError):server.mutate('/api/products',dict(name='Unsupported',batch='X',price=10,tax=0,schedule='X'))

 def test_cashier_cannot_use_wholesale_to_bypass_dispensing_controls(self):
  actor={**self.actor,'role':'cashier'}
  with self.assertRaises(ValueError):server.mutate('/api/documents',dict(kind='sale',trade='wholesale',party='Customer',lines=[dict(product=self.product,qty=1)]),actor)
 def test_metadata_validation(self):
  for extra in [dict(manufacturer=None),dict(hsn='ABC'),dict(barcode='bad\nbarcode')]:
   with self.assertRaises(ValueError):server.mutate('/api/products',dict(name='Invalid',batch='Bad',price=10,tax=0,**extra))
