"""Offline operator authentication and server-enforced permissions."""
import hashlib,hmac,secrets,time

ROLES={
 'admin':{'sale','purchase','return','purchase_return','inventory','inspection','accounting','backup','users','year-close','recovery','prescriptions','settlement','receipt','parties'},
 'manager':{'sale','purchase','return','purchase_return','inventory','inspection','backup','settlement','receipt','parties'},
 'pharmacist':{'sale','return','receipt','prescriptions'},
 'cashier':{'sale','receipt'},
 'accountant':{'accounting','backup','settlement','receipt','parties'},
}

def initialize(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS operator(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE COLLATE NOCASE,password_hash TEXT NOT NULL,salt TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,failed INTEGER NOT NULL DEFAULT 0,locked_until INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS session(token_hash TEXT PRIMARY KEY,operator INTEGER NOT NULL REFERENCES operator(id),expires INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,operator INTEGER NOT NULL REFERENCES operator(id),action TEXT NOT NULL,created_at INTEGER NOT NULL);
 ''')
 if 'registration' not in {r[1] for r in c.execute('PRAGMA table_info(operator)')}:c.execute("ALTER TABLE operator ADD COLUMN registration TEXT NOT NULL DEFAULT ''")


def password_hash(password,salt):
 return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()

def create_operator(c,d):
 username=str(d.get('username','')).strip();password=d.get('password');role=d.get('role')
 if not username or len(username)>80:raise ValueError('Enter an operator name of 1–80 characters')
 if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a password of 12–256 characters')
 if role not in ROLES:raise ValueError('Select a supported role')
 registration=str(d.get('registration','')).strip()
 if len(registration)>160:raise ValueError('Registration is too long')
 if role=='pharmacist' and not registration:raise ValueError('Pharmacist registration is required')
 salt=secrets.token_hex(16)
 c.execute('INSERT INTO operator(username,password_hash,salt,role,registration) VALUES(?,?,?,?,?)',(username,password_hash(password,salt),salt,role,registration))

def login(c,d):
 username=str(d.get('username','')).strip();password=d.get('password','')
 if not isinstance(password,str) or len(password)>256:raise ValueError('Invalid operator name or password')
 user=c.execute('SELECT * FROM operator WHERE username=?',(username,)).fetchone();now=int(time.time())
 # Use the same hash work for unknown operators to avoid a cheap username probe.
 candidate=password_hash(password,user['salt'] if user else '00'*16)
 if not user or not user['active'] or user['locked_until']>now or not hmac.compare_digest(candidate,user['password_hash']):
  if user:
   failed=user['failed']+1
   c.execute('UPDATE operator SET failed=?,locked_until=? WHERE id=?',(failed,now+300 if failed>=5 else user['locked_until'],user['id']))
  return None
 c.execute('UPDATE operator SET failed=0,locked_until=0 WHERE id=?',(user['id'],))
 token=secrets.token_urlsafe(32);c.execute('DELETE FROM session WHERE expires<=?',(now,))
 c.execute('INSERT INTO session VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],now+28800))
 return token

def current(c,token):
 if not token:return None
 row=c.execute('SELECT operator.id,username,role,registration FROM session JOIN operator ON operator.id=session.operator WHERE token_hash=? AND expires>? AND active=1',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
 return dict(row) if row else None

def authorize(user,path,d):
 if not user:raise PermissionError('Sign in to continue')
 permission={'/api/checkout':'sale','/api/held':'sale','/api/held-delete':'sale','/api/recall':'inventory','/api/recall-close':'inventory','/api/year-preview':'year-close','/api/year-close':'year-close','/api/backup-inspect':'recovery','/api/backup-import':'recovery','/api/restore':'recovery','/api/parties':'parties','/api/products':'inventory','/api/inspection':'inspection','/api/backup':'backup','/api/users':'users','/api/users/update':'users','/api/company':'accounting','/api/ledgers':'accounting','/api/openings':'accounting','/api/period-lock':'accounting'}.get(path)
 if path=='/api/settlements':permission='receipt' if d.get('kind')=='receipt' else 'settlement'
 if path in ('/api/documents','/api/quote'):permission=d.get('kind')
 if permission not in ROLES.get(user['role'],set()):raise PermissionError('Your role does not allow this operation')

def redact(state,user):
 state={**state,'operator':user,'held_bills':[r for r in state.get('held_bills',[]) if r['owner']==user['id'] or user['role']=='admin']}
 if user['role'] not in ('admin','pharmacist'):state={**state,'prescription_register':[]}
 if user['role']=='cashier':
  state={**state,'documents':state['sales'],'outstanding':[r for r in state.get('outstanding',[]) if r['kind']=='sale'],'settlements':[r for r in state.get('settlements',[]) if r['kind']=='receipt'],'journal':[],'accounts':[],'ledgers':[l for l in state['ledgers'] if l['category'] in ('cash','bank','customer','supplier','party')],'openings':[],'inspections':[],'movements':[]}
 if user['role'] not in ('admin','accountant'):
  state={**state,'closing_stock_reviews':[],'closed_years':[],'year_openings':[],'journal':[],'accounts':[],'ledgers':[l for l in state['ledgers'] if l['category'] in ('cash','bank','customer','supplier','party')],'openings':[]}
 return state

def update_operator(c,d):
 user=c.execute('SELECT * FROM operator WHERE id=?',(int(d['id']),)).fetchone()
 if not user:raise ValueError('Operator not found')
 registration=str(d.get('registration',user['registration'])).strip()
 role=d.get('role',user['role']);active=d.get('active',bool(user['active']))
 if role not in ROLES or not isinstance(active,bool):raise ValueError('Invalid operator role or status')
 if user['role']=='admin' and user['active'] and (role!='admin' or not active):
  if c.execute("SELECT COUNT(*) FROM operator WHERE role='admin' AND active=1").fetchone()[0]<=1:raise ValueError('Keep at least one active administrator')
 if len(registration)>160:raise ValueError('Registration is too long')
 if role=='pharmacist' and not registration:raise ValueError('Pharmacist registration is required')
 password=d.get('password','')
 if password:
  if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a password of 12–256 characters')
  salt=secrets.token_hex(16)
  c.execute('UPDATE operator SET password_hash=?,salt=?,failed=0,locked_until=0 WHERE id=?',(password_hash(password,salt),salt,user['id']))
 c.execute('UPDATE operator SET role=?,active=?,registration=? WHERE id=?',(role,int(active),registration,user['id']))
 c.execute('DELETE FROM session WHERE operator=?',(user['id'],))
