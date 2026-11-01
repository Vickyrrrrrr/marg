import base64
import hashlib
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import http.cookiejar
from contextlib import closing
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server
import recovery
import security


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = server.DB
        server.DB = Path(self.temp.name) / 'store.sqlite3'
        server.init()
        with server.connection() as c:
            security.create_operator(c, dict(username='owner', password='owner-password-123', role='admin'))
            self.token = security.login(c, dict(username='owner', password='owner-password-123'))
            self.actor = security.current(c, self.token)
        server.mutate('/api/company', dict(name='Test pharmacy', address='Test address', year_start='2024-01-01', year_end='2024-12-31'))
        server.mutate('/api/products', dict(name='Test medicine', batch='A', expiry='2030-01', price=10, tax=0))
        self.pid = server.snapshot()['products'][0]['id']
        self.buy(10)
        self.backup = server.backup()
        self.info = recovery.inspect(server.DB, self.backup['filename'])
        self.data = dict(filename=self.info['filename'], sha256=self.info['sha256'], password='owner-password-123', confirm='Test pharmacy')

    def tearDown(self):
        server.DB = self.original
        self.temp.cleanup()

    def buy(self, quantity):
        server.mutate('/api/documents', dict(kind='purchase', party='Test supplier', date='2024-01-01', lines=[dict(product=self.pid, qty=quantity, price=5)]))

    def test_restore_replaces_data_revokes_sessions_and_preserves_safety_copy(self):
        self.buy(4)
        result = recovery.restore(server.DB, self.data, self.actor, server.backup)
        self.assertEqual(server.snapshot()['products'][0]['stock'], 10)
        with server.connection() as c:
            self.assertIsNone(security.current(c, self.token))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM recovery_event').fetchone()[0], 1)
        with closing(sqlite3.connect(server.DB.parent / 'backups' / result['safety_backup'])) as c:
            self.assertEqual(c.execute('SELECT stock FROM products').fetchone()[0], 14)
        self.assertEqual(recovery.inspect(server.DB, self.info['filename'])['sha256'], self.info['sha256'])

    def test_changed_backup_and_wrong_confirmation_do_not_replace_live_data(self):
        self.buy(3)
        for fields in ({'password': 'incorrect'}, {'confirm': 'Other business'}, {'sha256': '0' * 64}):
            with self.assertRaises(ValueError):
                recovery.restore(server.DB, {**self.data, **fields}, self.actor, server.backup)
            self.assertEqual(server.snapshot()['products'][0]['stock'], 13)
        with server.connection() as c:
            self.assertIsNotNone(security.current(c, self.token))

    def test_invalid_schema_and_integrity_are_rejected(self):
        path = recovery.location(server.DB, self.info['filename'])
        with closing(sqlite3.connect(path)) as c:
            c.execute('CREATE TABLE unexpected(value TEXT)')
            c.commit()
        with self.assertRaisesRegex(ValueError, 'schema'):
            recovery.inspect(server.DB, path.name)
        path.write_bytes(b'not a database')
        with self.assertRaises(ValueError):
            recovery.inspect(server.DB, path.name)

    def test_unbalanced_journal_is_rejected(self):
        path = recovery.location(server.DB, self.info['filename'])
        with closing(sqlite3.connect(path)) as c:
            c.execute('UPDATE journal SET debit=debit+1 WHERE id=(SELECT MIN(id) FROM journal)')
            c.commit()
        with self.assertRaisesRegex(ValueError, 'unbalanced'):
            recovery.inspect(server.DB, path.name)

    def test_import_validates_and_traversal_is_denied(self):
        raw = recovery.location(server.DB, self.info['filename']).read_bytes()
        info = recovery.import_file(server.DB, {'content': base64.b64encode(raw).decode()})
        self.assertEqual(info['sha256'], hashlib.sha256(raw).hexdigest())
        count = len(recovery.listing(server.DB))
        for raw in (b'not SQLite', b'SQLite format 3\x00' + b'\x00' * 300):
            with self.assertRaises(ValueError):
                recovery.import_file(server.DB, {'content': base64.b64encode(raw).decode()})
        self.assertEqual(len(recovery.listing(server.DB)), count)
        for name in ('../store.sqlite3', '/store.sqlite3', 'ledgerly-../../store.sqlite3'):
            with self.assertRaises(ValueError):
                recovery.inspect(server.DB, name)

    def test_http_restore_permissions_and_session_invalidation(self):
        service = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        url = 'http://127.0.0.1:' + str(service.server_port)
        def post(path, data):
            req = urllib.request.Request(url + path, json.dumps(data).encode(), {'Content-Type': 'application/json'})
            try:
                with client.open(req) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as e:
                with e:
                    return e.code, json.load(e)
        try:
            self.assertEqual(post('/api/login', dict(username='owner', password='owner-password-123'))[0], 200)
            self.assertEqual(post('/api/backup-inspect', {'filename': self.info['filename']})[0], 200)
            self.assertEqual(post('/api/restore', self.data)[0], 200)
            self.assertEqual(post('/api/backup', {})[0], 401)
            for role in ('manager', 'cashier', 'pharmacist', 'accountant'):
                with self.assertRaises(PermissionError):
                    security.authorize({'role': role}, '/api/restore', {})
        finally:
            service.shutdown()
            service.server_close()
            thread.join()

    def test_newer_database_version_is_not_downgraded(self):
        with server.connection() as c:
            c.execute('PRAGMA user_version='+str(server.SCHEMA_VERSION+1))
        with self.assertRaisesRegex(ValueError,'newer'):
            server.init()
        with server.connection() as c:
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],server.SCHEMA_VERSION+1)

    def test_request_waiting_on_restore_must_authenticate_again(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        service=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=service.serve_forever,daemon=True)
        thread.start()
        entered=threading.Event();proceed=threading.Event();waiting=threading.Event()
        original=recovery.restore
        def delayed(*args):
            entered.set()
            if not proceed.wait(5):raise RuntimeError('Test coordination timed out')
            return original(*args)
        def request(path,data):
            req=urllib.request.Request('http://127.0.0.1:'+str(service.server_port)+path,json.dumps(data).encode(),{'Content-Type':'application/json','Cookie':'ledgerly_session='+self.token})
            try:
                with urllib.request.urlopen(req,timeout=10) as r:return r.status
            except urllib.error.HTTPError as e:
                with e:return e.code
        def pending():
            waiting.set()
            return request('/api/documents',dict(kind='purchase',party='Test supplier',date='2024-01-02',lines=[dict(product=self.pid,qty=5,price=5)]))
        try:
            with patch.object(recovery,'restore',delayed), ThreadPoolExecutor(max_workers=2) as pool:
                restore=pool.submit(request,'/api/restore',self.data)
                self.assertTrue(entered.wait(3))
                purchase=pool.submit(pending)
                self.assertTrue(waiting.wait(3));proceed.set()
                self.assertEqual(restore.result(),200)
                self.assertEqual(purchase.result(),401)
            self.assertEqual(server.snapshot()['products'][0]['stock'],10)
        finally:
            proceed.set();service.shutdown();service.server_close();thread.join()
