import unittest,tempfile,sys,threading,json,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server,security

class Access(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.original=server.DB;server.DB=Path(self.tmp.name)/'store.sqlite3';server.init()
  self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.http.server_port)
  self.owner=self.client()
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.thread.join();server.DB=self.original;self.tmp.cleanup()
 def client(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def request(self,path,data=None,client=None):
  req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
  try:
   with (client or self.owner).open(req,timeout=10) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as error:
   with error:return error.code,json.load(error)
 def bootstrap(self):
  self.assertEqual(self.request('/api/bootstrap',dict(username='owner',password='strong-owner-password'))[0],200)
 def test_owner_bootstrap_and_logout(self):
  self.assertEqual(self.request('/api/state')[0],401);self.bootstrap()
  self.assertEqual(self.request('/api/state')[1]['operator']['role'],'admin')
  self.assertEqual(self.request('/api/bootstrap',dict(username='other',password='another-password'))[0],409)
  self.request('/api/logout',{});self.assertEqual(self.request('/api/state')[0],401)
 def test_cashier_cannot_change_company_or_create_operators(self):
  self.bootstrap();self.request('/api/users',dict(username='cashier',password='cashier-password',role='cashier'))
  client=self.client();self.assertEqual(self.request('/api/login',dict(username='cashier',password='cashier-password'),client)[0],200)
  self.assertEqual(self.request('/api/company',{},client)[0],403)
  self.assertEqual(self.request('/api/users',dict(username='intruder',password='secret-password',role='admin'),client)[0],403)
  self.assertEqual(self.request('/api/documents',dict(kind='purchase',lines=[]),client)[0],403)
  state=self.request('/api/state',client=client)[1];self.assertEqual(state['journal'],[])
 def test_wrong_password_and_expired_session(self):
  self.bootstrap();self.assertEqual(self.request('/api/login',dict(username='owner',password='incorrect'))[0],401)
  with server.connection() as c:c.execute('UPDATE session SET expires=0')
  self.assertEqual(self.request('/api/state')[0],401)
 def test_password_storage_and_audit(self):
  self.bootstrap();self.request('/api/company',dict(name='Test company',address='Test address',year_start='2026-01-01',year_end='2026-12-31'))
  with server.connection() as c:
   operator=c.execute('SELECT * FROM operator').fetchone();self.assertNotEqual(operator['password_hash'],'strong-owner-password');self.assertEqual(len(operator['password_hash']),64)
   self.assertEqual(c.execute('SELECT action FROM audit').fetchone()[0],'/api/company')

 def test_cannot_disable_last_administrator(self):
  self.bootstrap();owner=self.request('/api/state')[1]['operator']
  self.assertEqual(self.request('/api/users/update',dict(id=owner['id'],active=False,role='admin'))[0],400)
  self.assertEqual(self.request('/api/state')[0],200)
 def test_disabling_operator_revokes_session(self):
  self.bootstrap();self.request('/api/users',dict(username='counter',password='counter-password',role='cashier'))
  client=self.client();self.request('/api/login',dict(username='counter',password='counter-password'),client)
  users=self.request('/api/users')[1]['users'];counter=next(u for u in users if u['username']=='counter')
  self.assertEqual(self.request('/api/users/update',dict(id=counter['id'],active=False,role='cashier'))[0],200)
  self.assertEqual(self.request('/api/state',client=client)[0],401)
