import unittest,tempfile
from pathlib import Path
import server
class Workflow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();server.DB=Path(self.tmp.name)/'db';server.init();server.mutate('/api/company',dict(name='Test company',address='Test address',year_start=str(server.date.today().year)+'-01-01',year_end=str(server.date.today().year)+'-12-31'));server.mutate('/api/products',dict(name='Test product',batch='A',expiry='2030-01',price=100,tax=12));self.pid=server.snapshot()['products'][0]['id']
 def tearDown(self):self.tmp.cleanup()
 def doc(self,kind,qty,reference=None):return server.mutate('/api/documents',dict(kind=kind,party='Test',reference=reference,lines=[dict(product=self.pid,qty=qty,price=60)]))
 def test_purchase_sale_return(self):
  self.doc('purchase',10);s=self.doc('sale',3);self.assertEqual(s['products'][0]['stock'],7);self.assertEqual(s['sales'][0]['total'],336);s=self.doc('return',2,2);self.assertEqual(s['products'][0]['stock'],7);self.assertEqual(s['products'][0]['quarantine'],2)
  with self.assertRaises(ValueError):self.doc('return',2,2)
  self.assertEqual(server.snapshot()['products'][0]['stock'],7)
 def test_oversell_atomic(self):
  self.doc('purchase',1)
  with self.assertRaises(ValueError):self.doc('sale',2)
  self.assertEqual(len(server.snapshot()['documents']),1)
 def test_supplier_return(self):
  self.doc('purchase',10);s=self.doc('purchase_return',4,1);self.assertEqual(s['products'][0]['stock'],6);self.assertEqual(s['documents'][-1]['total'],268.8)
 def test_partial_return_rounding(self):
  with server.connection() as c:c.execute('UPDATE products SET price=1,tax=1800')
  self.doc('purchase',3);self.doc('sale',3)
  for _ in range(3):self.doc('return',1,2)
  s=server.snapshot();self.assertEqual(sum(d['total'] for d in s['documents'] if d['kind']=='return'),s['sales'][0]['total'])
 def test_return_inspection(self):
  self.doc('purchase',2);self.doc('sale',2);self.doc('return',2,2)
  with self.assertRaises(ValueError):self.doc('sale',1)
  server.mutate('/api/inspection',dict(product=self.pid,qty=1,disposition='release',reason='Intact pack inspected'))
  self.assertEqual(server.snapshot()['products'][0]['stock'],1)
  server.mutate('/api/inspection',dict(product=self.pid,qty=1,disposition='dispose',reason='Damaged pack'))
  self.assertEqual(server.snapshot()['products'][0]['quarantine'],0)
 def test_backup_preserves_data(self):
  self.doc('purchase',5);result=server.backup()
  import sqlite3
  with sqlite3.connect(server.DB.parent/'backups'/result['filename']) as c:
   self.assertEqual(c.execute('SELECT stock FROM products').fetchone()[0],5)
 def test_inclusive_pack_sale_quote(self):
  with server.connection() as c:c.execute('UPDATE products SET price=11200,mrp=11200,tax_inclusive=1,pack_size=10')
  self.doc('purchase',30)
  payload=dict(kind='sale',lines=[dict(product=self.pid,qty=2,unit='pack')])
  quote=server.mutate('/api/quote',payload)
  self.assertEqual(quote['total_paise'],224000)
  self.assertEqual(server.snapshot()['products'][0]['stock'],30)
  result=server.mutate('/api/documents',payload)
  self.assertEqual(result['sales'][0]['total'],2240)
  self.assertEqual(result['products'][0]['stock'],10)
 def test_mrp_guard(self):
  with self.assertRaises(ValueError):server.mutate('/api/products',dict(name='Above MRP',batch='B',price=101,tax=12,mrp=100,tax_inclusive=True))
  with server.connection() as c:c.execute('UPDATE products SET mrp=10000')
  self.doc('purchase',2)
  with self.assertRaises(ValueError):self.doc('sale',1)
 def test_inclusive_partial_return(self):
  with server.connection() as c:c.execute('UPDATE products SET price=11200,tax_inclusive=1')
  self.doc('purchase',3);self.doc('sale',3);r=self.doc('return',1,2)
  self.assertEqual(r['documents'][-1]['total'],112)
 def test_migration_repeatable(self):
  server.init();server.init();self.assertEqual(len(server.snapshot()['products']),1)
 def test_duplicate_submission(self):
  self.doc('purchase',3)
  payload=dict(kind='sale',request_key='same-request',lines=[dict(product=self.pid,qty=1)])
  server.mutate('/api/documents',payload);r=server.mutate('/api/documents',payload)
  self.assertEqual(r['products'][0]['stock'],2);self.assertEqual(len(r['sales']),1)
  payload['lines'][0]['qty']=2
  with self.assertRaises(ValueError):server.mutate('/api/documents',payload)
 def test_journal_balances_and_reverses(self):
  self.doc('purchase',3);self.doc('sale',3)
  for _ in range(3):self.doc('return',1,2)
  state=server.snapshot()
  for document in state['documents']:
   entries=[r for r in state['journal'] if r['document']==document['id']]
   self.assertTrue(entries)
   self.assertEqual(sum(r['debit']-r['credit'] for r in entries),0)
  for a in state['accounts']:
   if a['account'] in ('Sales','Trade receivables','Output tax pending classification'):self.assertEqual(a['debit'],a['credit'])
 def test_quote_has_no_journal_effect(self):
  self.doc('purchase',3);before=server.snapshot()['journal']
  server.mutate('/api/quote',dict(kind='sale',lines=[dict(product=self.pid,qty=1)]))
  self.assertEqual(server.snapshot()['journal'],before)
 def test_inclusive_tax_split(self):
  with server.connection() as c:c.execute('UPDATE products SET price=11200,tax_inclusive=1')
  self.doc('purchase',1);self.doc('sale',1)
  entries={r['account']:r for r in server.snapshot()['journal'] if r['document']==2}
  self.assertEqual(entries['Sales']['credit'],10000)
  self.assertEqual(entries['Output tax pending classification']['credit'],1200)
 def test_company_period_rules(self):
  self.doc('purchase',1)
  with self.assertRaises(ValueError):server.mutate('/api/documents',dict(kind='sale',date='2001-01-01',lines=[dict(product=self.pid,qty=1)]))
  server.mutate('/api/period-lock',dict(locked_through=server.date.today().isoformat()))
  with self.assertRaises(ValueError):self.doc('sale',1)
 def test_balanced_openings(self):
  server.mutate('/api/ledgers',dict(name='Cash',category='cash'));server.mutate('/api/ledgers',dict(name='Capital',category='equity'))
  with self.assertRaises(ValueError):server.mutate('/api/openings',dict(lines=[dict(ledger=1,debit=100)]))
  self.assertFalse(server.snapshot()['openings_posted'])
  server.mutate('/api/openings',dict(lines=[dict(ledger=1,debit=100),dict(ledger=2,credit=100)]))
  self.assertTrue(server.snapshot()['openings_posted'])
  self.assertEqual(sum(a['debit']-a['credit'] for a in server.snapshot()['accounts']),0)
  with self.assertRaises(ValueError):server.mutate('/api/openings',dict(lines=[dict(ledger=1,debit=100),dict(ledger=2,credit=100)]))
if __name__=='__main__':unittest.main()
