import sqlite3, json, os, secrets, sys, hashlib
from decimal import InvalidOperation
from contextlib import closing
import business_setup
import settlements
import parties
import pharmacy
import security
import recovery
import financial_year
import workflows
from threading import RLock
from functools import wraps
from urllib.parse import urlsplit, parse_qs
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
DB = Path(os.environ.get('LEDGERLY_DATA_DIR', str(ROOT / 'data'))) / 'erp.sqlite3'

SCHEMA_VERSION = 13
DATABASE_LOCK = RLock()

def serialized(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        with DATABASE_LOCK:
            return function(*args, **kwargs)
    return invoke

class DatabaseConnection(sqlite3.Connection):
    """Commit/rollback on context exit and always release the database handle."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connection():
    c = sqlite3.connect(DB, timeout=20, factory=DatabaseConnection)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

@serialized
def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connection() as c:
        if c.execute('PRAGMA user_version').fetchone()[0] > SCHEMA_VERSION:
            raise ValueError('This database requires a newer Ledgerly application')
        c.executescript('\n CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY,name TEXT NOT NULL,batch TEXT NOT NULL,expiry TEXT NOT NULL,stock INTEGER NOT NULL CHECK(stock>=0),price INTEGER NOT NULL,tax INTEGER NOT NULL,UNIQUE(name,batch));\n CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,party TEXT NOT NULL,date TEXT NOT NULL,total INTEGER NOT NULL,reference INTEGER REFERENCES documents(id));\n CREATE TABLE IF NOT EXISTS lines(id INTEGER PRIMARY KEY,document INTEGER REFERENCES documents(id),product TEXT REFERENCES products(id),qty INTEGER NOT NULL,price INTEGER NOT NULL,tax INTEGER NOT NULL,total INTEGER NOT NULL);\n CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,document INTEGER REFERENCES documents(id),product TEXT REFERENCES products(id),quantity INTEGER NOT NULL);\n ')

        columns = {r[1] for r in c.execute('PRAGMA table_info(products)')}
        if 'quarantine' not in columns:
            c.execute('ALTER TABLE products ADD COLUMN quarantine INTEGER NOT NULL DEFAULT 0 CHECK(quarantine>=0)')
        c.execute('CREATE TABLE IF NOT EXISTS inspections(id INTEGER PRIMARY KEY,product TEXT NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL,disposition TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL)')
        for name, definition in [('pack_size','INTEGER NOT NULL DEFAULT 1'), ('mrp','INTEGER'), ('tax_inclusive','INTEGER NOT NULL DEFAULT 0')]:
            if name not in columns:
                c.execute(f'ALTER TABLE products ADD COLUMN {name} {definition}')
        c.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,digest TEXT NOT NULL,document INTEGER NOT NULL REFERENCES documents(id))')
        c.execute('CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY,document INTEGER NOT NULL REFERENCES documents(id),account TEXT NOT NULL,debit INTEGER NOT NULL CHECK(debit>=0),credit INTEGER NOT NULL CHECK(credit>=0),CHECK(debit=0 OR credit=0))')
        line_columns={r[1] for r in c.execute('PRAGMA table_info(lines)')}
        if 'supplier_invoice' not in {r[1] for r in c.execute('PRAGMA table_info(documents)')}:
            c.execute("ALTER TABLE documents ADD COLUMN supplier_invoice TEXT NOT NULL DEFAULT ''")
        if 'company_snapshot' not in {r[1] for r in c.execute('PRAGMA table_info(documents)')}:
            c.execute('ALTER TABLE documents ADD COLUMN company_snapshot TEXT')
        if 'taxable' not in line_columns:
            c.execute('ALTER TABLE lines ADD COLUMN taxable INTEGER')
        business_setup.initialize(c)
        security.initialize(c)
        settlements.initialize(c)
        parties.initialize(c)
        pharmacy.initialize(c)
        recovery.initialize(c)
        financial_year.initialize(c)
        workflows.initialize(c)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS supplier_invoice_identity ON documents(party_ledger,supplier_invoice COLLATE NOCASE) WHERE kind='purchase' AND supplier_invoice!='' AND party_ledger IS NOT NULL")
        c.execute('PRAGMA user_version='+str(SCHEMA_VERSION))

@serialized
def backup():
    folder = DB.parent / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('ledgerly-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
    with connection() as source, closing(sqlite3.connect(target)) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup integrity check failed')
    return {'filename': target.name, 'bytes': target.stat().st_size}

def cents(v):
    d = Decimal(str(v))
    if not (d.is_finite() and d >= 0):
        raise ValueError('Invalid amount')
    return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def integer(v):
    n = int(v)
    if not (str(n) == str(v) and n > 0):
        raise ValueError('Quantity must be a positive integer')
    return n

TRIAL_BALANCE_SQL = """
SELECT account,SUM(debit) AS debit,SUM(credit) AS credit FROM (
 SELECT account,debit,credit FROM journal JOIN documents ON documents.id=journal.document
 WHERE documents.date BETWEEN (SELECT year_start FROM company WHERE id=1) AND (SELECT year_end FROM company WHERE id=1)
 UNION ALL
 SELECT CASE WHEN ledger.category IN ('cash','bank') THEN 'Cash/bank: '||ledger.name WHEN ledger.category IN ('customer','supplier','party') THEN 'Party ledger: '||ledger.id||': '||ledger.name ELSE ledger.name END AS account,
 opening_line.debit,opening_line.credit FROM opening_line JOIN ledger ON ledger.id=opening_line.ledger
 WHERE NOT EXISTS(SELECT 1 FROM financial_year)
 UNION ALL
 SELECT account,debit,credit FROM year_opening WHERE year_start=(SELECT year_start FROM company WHERE id=1)
) GROUP BY account ORDER BY account
"""

@serialized
def snapshot():
    with connection() as c:
        products = [{**dict(r), 'price': r['price'] / 100, 'mrp': None if r['mrp'] is None else r['mrp']/100, 'tax': r['tax'] / 100} for r in c.execute('SELECT * FROM products ORDER BY name')]
        docs = []
        for r in c.execute('SELECT * FROM documents ORDER BY id'):
            lines = [{**dict(l), 'name': l['name'], 'price': l['price'] / 100, 'tax': l['tax'] / 100, 'total': l['total'] / 100} for l in c.execute('SELECT lines.*,products.name,products.batch FROM lines JOIN products ON products.id=lines.product WHERE document=?', (r['id'],))]
            docs.append({**dict(r), 'company_snapshot':json.loads(r['company_snapshot']) if r['company_snapshot'] else None, 'customer': r['party'], 'number': r['kind'].upper() + '-' + str(r['id']).zfill(5), 'total': r['total'] / 100, 'lines': lines})
        return {**business_setup.snapshot(c), **financial_year.snapshot(c), **workflows.snapshot(c), **settlements.snapshot(c), 'prescription_register':pharmacy.register(c), 'products': products, 'sales': [d for d in docs if d['kind'] == 'sale'], 'documents': docs, 'accounts': [dict(r) for r in c.execute(TRIAL_BALANCE_SQL)], 'journal': [dict(r) for r in c.execute('SELECT journal.*,documents.party,documents.date,documents.kind FROM journal JOIN documents ON documents.id=document ORDER BY journal.id DESC')], 'unposted_documents': c.execute('SELECT COUNT(*) FROM documents WHERE NOT EXISTS(SELECT 1 FROM journal WHERE document=documents.id)').fetchone()[0], 'inspections': [dict(r) for r in c.execute('SELECT inspections.*,products.name FROM inspections JOIN products ON products.id=product ORDER BY inspections.id DESC')], 'movements': [dict(r) for r in c.execute('SELECT movements.*,products.name FROM movements JOIN products ON product=products.id ORDER BY movements.id DESC')]}

@serialized
def mutate(path, d, actor=None):
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        if path in ('/api/held','/api/held-delete','/api/recall','/api/recall-close'):
            workflows.mutate(c,path,d,actor,integer)
        elif path == '/api/year-preview':
            return financial_year.preview(c,TRIAL_BALANCE_SQL,d.get('closing_stock'))
        elif path == '/api/year-close':
            financial_year.close(c,d,actor,TRIAL_BALANCE_SQL)
        elif path == '/api/settlements':
            settlements.post(c,d,cents,business_setup.validate_date)
        elif path in ('/api/parties','/api/company','/api/ledgers','/api/openings','/api/period-lock'):
            business_setup.mutate(c,path,d,cents)
        elif path == '/api/inspection':
            pid = d['product']
            qty = integer(d['qty'])
            disposition = d['disposition']
            reason = str(d.get('reason', '')).strip()
            if disposition not in ('release', 'dispose') or not reason:
                raise ValueError('Select a disposition and provide an inspection reason')
            p = c.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
            if not p or p['quarantine'] < qty:
                raise ValueError('Quantity exceeds quarantined stock')
            if disposition == 'release' and workflows.recalled(c,pid):
                raise ValueError('Recalled stock cannot be released for sale')
            if disposition == 'release' and p['expiry'] and p['expiry'] < date.today().strftime('%Y-%m'):
                raise ValueError('Expired returns cannot be released')
            c.execute('UPDATE products SET quarantine=quarantine-?,stock=stock+? WHERE id=?', (qty, qty if disposition == 'release' else 0, pid))
            c.execute('INSERT INTO inspections(product,quantity,disposition,reason,created_at) VALUES(?,?,?,?,?)', (pid, qty, disposition, reason, datetime.now().isoformat()))
        elif path == '/api/products':
            name = str(d['name']).strip()
            batch = str(d['batch']).strip()
            if not (name and batch):
                raise ValueError('Name and batch are required')
            expiry = str(d.get('expiry', ''))
            if not (not expiry or datetime.strptime(expiry, '%Y-%m')):
                raise ValueError('Invalid expiry')
            tax = cents(d['tax'])
            if not tax <= 10000:
                raise ValueError('Invalid tax rate')
            pack_size = integer(d.get('pack_size', 1))
            inclusive = d.get('tax_inclusive', False)
            if not isinstance(inclusive, bool):
                raise ValueError('Tax-inclusive must be true or false')
            mrp = None if d.get('mrp') in (None, '') else cents(d['mrp'])
            price = cents(d['price'])
            gross_unit = price if inclusive else int((Decimal(price)*(1+Decimal(tax)/10000)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            if mrp is not None and gross_unit > mrp:
                raise ValueError('Selling price including tax exceeds MRP')
            identifier=secrets.token_hex(8)
            c.execute('INSERT INTO products(id,name,batch,expiry,stock,price,tax,pack_size,mrp,tax_inclusive) VALUES(?,?,?,?,?,?,?,?,?,?)', (identifier, name, batch, expiry, 0, price, tax, pack_size, mrp, int(inclusive)))
            pharmacy.save_product(c,identifier,d)
        elif path in ('/api/documents','/api/quote'):
            request_key = d.get('request_key') if path == '/api/documents' else None
            digest = hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',', ':')).encode()).hexdigest()
            if request_key:
                if not isinstance(request_key,str) or len(request_key)>100:
                    raise ValueError('Invalid transaction request key')
                previous = c.execute('SELECT * FROM requests WHERE key=?',(request_key,)).fetchone()
                if previous:
                    if previous['digest'] != digest:
                        raise ValueError('This request key was used for a different transaction')
                    return snapshot()
            document_date=business_setup.validate_date(c,d.get('date',date.today().isoformat()))
            kind = d['kind']
            if not kind in ('sale', 'purchase', 'return', 'purchase_return'):
                raise ValueError('Invalid document type')
            supplier_invoice=d.get('supplier_invoice','') if kind=='purchase' else ''
            if not isinstance(supplier_invoice,str) or len(supplier_invoice)>120 or any(ord(ch)<32 for ch in supplier_invoice):raise ValueError('Invalid supplier invoice number')
            supplier_invoice=supplier_invoice.strip()
            items = d['lines']
            if not (items and len(items) <= 500):
                raise ValueError('Add at least one item')
            party_ledger,party = parties.resolve(c,d,kind,create=path=='/api/documents')
            reference = d.get('reference')
            seen = set()
            computed = []
            taxable_amounts = []
            medicine_products=[]
            if kind in ('return', 'purchase_return'):
                source_kind = 'sale' if kind == 'return' else 'purchase'
                if not c.execute('SELECT id FROM documents WHERE id=? AND kind=?', (reference, source_kind)).fetchone():
                    raise ValueError('Select an original document')
            for item in items:
                pid = item['product']
                if not pid not in seen:
                    raise ValueError('Duplicate batch')
                seen.add(pid)
                qty = integer(item['qty'])
                p = c.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
                if not p:
                    raise ValueError('Product not found')
                unit = item.get('unit', 'loose')
                if unit not in ('loose', 'pack'):
                    raise ValueError('Choose loose units or packs')
                qty *= p['pack_size'] if unit == 'pack' else 1
                medicine_products.append(p)
                price = p['price']
                tax = p['tax']
                if kind == 'purchase':
                    price = cents(item['price'])
                if kind == 'sale':
                    if workflows.recalled(c,pid):raise ValueError('Recalled batch cannot be sold')
                    if not p['stock'] >= qty:
                        raise ValueError('Insufficient stock')
                    if not (not p['expiry'] or p['expiry'] >= document_date[:7]):
                        raise ValueError('Expired stock cannot be sold')
                if kind in ('return', 'purchase_return'):
                    original = c.execute('SELECT * FROM lines WHERE document=? AND product=?', (reference, pid)).fetchone()
                    if not original:
                        raise ValueError('Product was not sold on this invoice')
                    returned = c.execute('SELECT COALESCE(SUM(lines.qty),0) FROM lines JOIN documents ON document=documents.id WHERE documents.kind=? AND reference=? AND product=?', (kind, reference, pid)).fetchone()[0]
                    if not qty <= original['qty'] - returned:
                        raise ValueError('Return exceeds original quantity')
                    price = original['price']
                    tax = original['tax']
                    if kind == 'purchase_return':
                        if not p['stock'] >= qty:
                            raise ValueError('Insufficient stock for supplier return')
                total = int((Decimal(price * qty) * (1 + Decimal(tax) / 10000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                if kind == 'sale' and p['tax_inclusive']:
                    total = price * qty
                if kind == 'sale' and p['mrp'] is not None and total > p['mrp'] * qty:
                    raise ValueError('Selling price including tax exceeds batch MRP')
                if kind in ('return', 'purchase_return'):

                    def allocated(n):
                        return int((Decimal(original['total']) * n / original['qty']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    total = allocated(returned + qty) - allocated(returned)
                taxable = price * qty
                if kind == 'sale' and p['tax_inclusive']:
                    taxable = int((Decimal(total)/(1+Decimal(tax)/10000)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                if kind in ('return','purchase_return'):
                    if original['taxable'] is None:
                        raise ValueError('Original invoice predates the accounting ledger; reconcile it before returning')
                    def allocate_net(n):
                        return int((Decimal(original['taxable'])*n/original['qty']).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
                    taxable = allocate_net(returned+qty)-allocate_net(returned)
                taxable_amounts.append(taxable)
                computed.append((pid, qty, price, tax, total))
            total = sum((x[4] for x in computed))
            if path == '/api/quote':
                return {'total_paise':total,'lines':[{'product':pid,'quantity':qty,'total_paise':amount} for pid,qty,price,tax,amount in computed]}
            if supplier_invoice and c.execute("SELECT 1 FROM documents WHERE kind='purchase' AND party_ledger=? AND supplier_invoice=? COLLATE NOCASE",(party_ledger,supplier_invoice)).fetchone():raise ValueError('This supplier invoice has already been received')
            held_id=d.get('draft_id') if kind=='sale' else None
            if held_id:workflows.held(c,held_id,actor)
            trade,rx=pharmacy.validate_sale(c,{**d,'_party_ledger':party_ledger},actor,document_date,medicine_products) if kind=='sale' else ('retail',None)
            doc = c.execute('INSERT INTO documents(kind,party,date,total,reference,party_ledger) VALUES(?,?,?,?,?,?)', (kind, party, document_date, total, reference if kind in ('return', 'purchase_return') else None,party_ledger)).lastrowid
            c.execute('UPDATE documents SET supplier_invoice=? WHERE id=?',(supplier_invoice,doc))
            if held_id:c.execute('DELETE FROM held_bill WHERE id=?',(held_id,))
            if kind=='sale':pharmacy.record(c,doc,trade,rx,actor,medicine_products,{pid:qty for pid,qty,price,tax,total in computed})
            company_snapshot=dict(c.execute('SELECT * FROM company').fetchone())
            c.execute('UPDATE documents SET company_snapshot=? WHERE id=?',(json.dumps(company_snapshot),doc))
            if request_key:
                c.execute('INSERT INTO requests VALUES(?,?,?)',(request_key,digest,doc))
            for index, (pid, qty, price, tax, line_total) in enumerate(computed):
                delta = -qty if kind in ('sale', 'purchase_return') else qty
                if kind == 'return':
                    c.execute('UPDATE products SET quarantine=quarantine+? WHERE id=?', (qty, pid))
                    delta = 0
                else:
                    c.execute('UPDATE products SET stock=stock+? WHERE id=?', (delta, pid))
                c.execute('INSERT INTO movements(document,product,quantity) VALUES(?,?,?)', (doc, pid, delta))
                c.execute('INSERT INTO lines(document,product,qty,price,tax,total,taxable) VALUES(?,?,?,?,?,?,?)', (doc, pid, qty, price, tax, line_total, taxable_amounts[index]))
            net = sum(taxable_amounts)
            tax_amount = total-net
            if kind in ('sale','return'):
                postings=[(parties.account(c,party_ledger,'Trade receivables'),total,0),('Sales',0,net),('Output tax pending classification',0,tax_amount)]
            else:
                postings=[('Purchases',net,0),('Input tax pending classification',tax_amount,0),(parties.account(c,party_ledger,'Trade payables'),0,total)]
            if kind in ('return','purchase_return'):
                postings=[(account,credit,debit) for account,debit,credit in postings]
            if sum(debit-credit for account,debit,credit in postings)!=0:
                raise ValueError('Unbalanced accounting transaction')
            for account,debit,credit in postings:
                if debit or credit or total == 0:
                    c.execute('INSERT INTO journal(document,account,debit,credit) VALUES(?,?,?,?)',(doc,account,debit,credit))
        else:
            raise ValueError('Unknown endpoint')
        if actor and path != '/api/quote':
            c.execute('INSERT INTO audit(operator,action,created_at) VALUES(?,?,?)',(actor['id'],path,int(security.time.time())))
    return snapshot()

class Handler(SimpleHTTPRequestHandler):

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / 'app'), **kw)

    def token(self):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return None
        return cookie['ledgerly_session'].value if 'ledgerly_session' in cookie else None

    def user(self):
        with connection() as c:return security.current(c,self.token())

    def answer(self, status, data, cookie=None):
        b = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie is not None:self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(b)

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port))

    @serialized
    def do_GET(self):
        if not self.valid_host():return self.answer(403,{'error':'Invalid local host'})
        if self.path == '/api/auth':
            with connection() as c:
                self.answer(200,{'needs_setup':not c.execute('SELECT 1 FROM operator').fetchone(),'operator':security.current(c,self.token())})
        elif self.path == '/api/state':
            user=self.user()
            if not user:return self.answer(401,{'error':'Sign in to continue'})
            self.answer(200,security.redact(snapshot(),user))
        elif urlsplit(self.path).path in ('/api/backups','/api/backup-download'):
            user=self.user()
            try:security.authorize(user,'/api/backup',{})
            except PermissionError as e:return self.answer(403 if user else 401,{'error':str(e)})
            if self.path=='/api/backups':return self.answer(200,{'backups':recovery.listing(DB)})
            try:
                filename=parse_qs(urlsplit(self.path).query).get('filename',[''])[0]
                path=recovery.location(DB,filename)
                content=path.read_bytes()
            except ValueError as e:return self.answer(400,{'error':str(e)})
            self.send_response(200)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/api/users':
            user=self.user()
            try:security.authorize(user,self.path,{})
            except PermissionError as e:return self.answer(403 if user else 401,{'error':str(e)})
            with connection() as c:self.answer(200,{'users':[dict(r) for r in c.execute('SELECT id,username,role,active,registration FROM operator ORDER BY username')]})
        else:
            super().do_GET()

    @serialized
    def do_POST(self):
        try:
            if not self.valid_host():return self.answer(403,{'error':'Invalid local host'})
            origin = self.headers.get('Origin')
            if origin and origin.split('://', 1)[-1] != self.headers.get('Host'):
                return self.answer(403,{'error':'Cross-origin request rejected'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                raise ValueError('JSON content type required')
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n < (90000000 if self.path=='/api/backup-import' else 1000000):raise ValueError('Invalid request size')
            d = json.loads(self.rfile.read(n))
            if not isinstance(d,dict):raise ValueError('JSON object required')
            if self.path in ('/api/bootstrap','/api/login'):
                with connection() as c:
                    c.execute('BEGIN IMMEDIATE')
                    if self.path=='/api/bootstrap':
                        if c.execute('SELECT 1 FROM operator').fetchone():return self.answer(409,{'error':'Administrator already exists'})
                        security.create_operator(c,{**d,'role':'admin'})
                    token=security.login(c,d)
                if not token:return self.answer(401,{'error':'Invalid operator name or password, or account temporarily locked'})
                return self.answer(200,{'ok':True},'ledgerly_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            if self.path=='/api/logout':
                with connection() as c:c.execute('DELETE FROM session WHERE token_hash=?',(security.hashlib.sha256((self.token() or '').encode()).hexdigest(),))
                return self.answer(200,{'ok':True},'ledgerly_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            user=self.user()
            try:security.authorize(user,self.path,d)
            except PermissionError as e:return self.answer(403 if user else 401,{'error':str(e)})
            if self.path in ('/api/users','/api/users/update'):
                with connection() as c:
                    c.execute('BEGIN IMMEDIATE')
                    if self.path=='/api/users':security.create_operator(c,d)
                    else:security.update_operator(c,d)
                    c.execute('INSERT INTO audit(operator,action,created_at) VALUES(?,?,?)',(user['id'],self.path,int(security.time.time())))
                return self.answer(200,{'ok':True})
            if self.path in ('/api/backup-inspect','/api/backup-import','/api/restore'):
                if self.path=='/api/backup-inspect':result=recovery.inspect(DB,d.get('filename'))
                elif self.path=='/api/backup-import':result=recovery.import_file(DB,d)
                else:result=recovery.restore(DB,d,user,backup)
                return self.answer(200,result,'ledgerly_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0' if self.path=='/api/restore' else None)
            if self.path=='/api/year-close':backup()
            result=backup() if self.path == '/api/backup' else mutate(self.path,d,user)
            self.answer(200,result if self.path in ('/api/quote','/api/backup','/api/year-preview') else security.redact(result,user))
        except (ValueError, KeyError, TypeError, InvalidOperation, sqlite3.IntegrityError) as e:
            self.answer(400, {'error': str(e) or 'Invalid input'})
        except PermissionError as e:
            self.answer(403, {'error':str(e)})
        except (sqlite3.DatabaseError,OSError):
            self.answer(500, {'error':'Local database or backup storage is unavailable. Check disk space and file permissions, then retry.'})
if __name__ == '__main__':
    init()
    http = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8001'))), Handler)
    print('LEDGERLY_READY=http://127.0.0.1:' + str(http.server_port), flush=True)
    http.serve_forever()
