"""Company, accounting period and opening-ledger configuration."""
from datetime import date

def initialize(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS company(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,address TEXT NOT NULL,gstin TEXT NOT NULL,drug_licence TEXT NOT NULL,year_start TEXT NOT NULL,year_end TEXT NOT NULL,locked_through TEXT);
 CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,category TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS opening_batch(id INTEGER PRIMARY KEY CHECK(id=1),posted_on TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS opening_line(ledger INTEGER PRIMARY KEY REFERENCES ledger(id),debit INTEGER NOT NULL CHECK(debit>=0),credit INTEGER NOT NULL CHECK(credit>=0),CHECK(debit=0 OR credit=0));
 ''')

def snapshot(c):
 company=c.execute('SELECT * FROM company').fetchone()
 return {'company':dict(company) if company else None,'ledgers':[dict(r) for r in c.execute('SELECT * FROM ledger ORDER BY name')],'openings':[dict(r) for r in c.execute('SELECT opening_line.*,ledger.name FROM opening_line JOIN ledger ON ledger.id=opening_line.ledger')],'openings_posted':bool(c.execute('SELECT 1 FROM opening_batch').fetchone())}

def mutate(c,path,d,cents):
 if path=='/api/company':
  name=str(d.get('name','')).strip();address=str(d.get('address','')).strip()
  if not name or not address:raise ValueError('Company name and address are required')
  start=date.fromisoformat(d['year_start']);end=date.fromisoformat(d['year_end'])
  if start>=end or (end-start).days>366:raise ValueError('Select a valid financial-year date range')
  old=c.execute('SELECT * FROM company').fetchone()
  activity=c.execute('SELECT COUNT(*) FROM documents').fetchone()[0] or c.execute('SELECT COUNT(*) FROM opening_batch').fetchone()[0] or c.execute('SELECT COUNT(*) FROM financial_year').fetchone()[0]
  if old and activity and (old['year_start']!=start.isoformat() or old['year_end']!=end.isoformat()):raise ValueError('Cannot change financial year after posting; rollover is required')
  c.execute('INSERT INTO company(id,name,address,gstin,drug_licence,year_start,year_end) VALUES(1,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,address=excluded.address,gstin=excluded.gstin,drug_licence=excluded.drug_licence,year_start=excluded.year_start,year_end=excluded.year_end',(name,address,str(d.get('gstin','')).strip().upper(),str(d.get('drug_licence','')).strip(),start.isoformat(),end.isoformat()))
 elif path in ('/api/ledgers','/api/parties'):
  category=d['category'];name=str(d['name']).strip()
  if path=='/api/parties' and category not in ('customer','supplier','party'):raise ValueError('Select customer, supplier or both')
  if category not in ('asset','liability','equity','income','expense','customer','supplier','party','cash','bank'):raise ValueError('Select an account category')
  if not name:raise ValueError('Ledger name is required')
  if category not in ('cash','bank','customer','supplier','party') and (name.lower() in {'sales','purchases','trade receivables','trade payables','input tax pending classification','output tax pending classification','year-end retained earnings','inventory at year close','opening stock expense','closing stock adjustment'} or name.lower().startswith(('party ledger:','cash/bank:'))):raise ValueError('This ledger name is reserved for system postings')
  if c.execute('SELECT 1 FROM ledger WHERE name=? COLLATE NOCASE',(name,)).fetchone():raise ValueError('Ledger name already exists')
  c.execute('INSERT INTO ledger(name,category,phone,address,gstin,drug_licence) VALUES(?,?,?,?,?,?)',(name,category,str(d.get('phone','')).strip(),str(d.get('address','')).strip(),str(d.get('gstin','')).strip().upper(),str(d.get('drug_licence','')).strip()))
 elif path=='/api/openings':
  company=c.execute('SELECT * FROM company').fetchone()
  if not company:raise ValueError('Set up your company first')
  if c.execute('SELECT 1 FROM financial_year').fetchone():raise ValueError('Opening balances were carried forward from the closed year')
  if c.execute('SELECT 1 FROM opening_batch').fetchone():raise ValueError('Opening balances already posted')
  if c.execute('SELECT 1 FROM documents').fetchone():raise ValueError('Opening balances must be posted before transactions')
  lines=d['lines'];seen=set();values=[]
  if not lines:raise ValueError('Enter opening balances')
  for line in lines:
   ledger=int(line['ledger']);debit=cents(line.get('debit',0));credit=cents(line.get('credit',0))
   if ledger in seen or (debit and credit):raise ValueError('Use each ledger once with either debit or credit')
   if not c.execute('SELECT 1 FROM ledger WHERE id=?',(ledger,)).fetchone():raise ValueError('Unknown ledger')
   seen.add(ledger);values.append((ledger,debit,credit))
  if sum(x[1]-x[2] for x in values)!=0:raise ValueError('Opening debits must equal opening credits')
  c.execute('INSERT INTO opening_batch VALUES(1,?)',(company['year_start'],))
  c.executemany('INSERT INTO opening_line VALUES(?,?,?)',values)
 elif path=='/api/period-lock':
  company=c.execute('SELECT * FROM company').fetchone()
  if not company:raise ValueError('Set up the company first')
  lock=date.fromisoformat(d['locked_through']).isoformat()
  if not company['year_start']<=lock<=company['year_end']:raise ValueError('Lock date must fall within the financial year')
  if company['locked_through'] and lock<company['locked_through']:raise ValueError('Period locks cannot be moved backwards')
  c.execute('UPDATE company SET locked_through=? WHERE id=1',(lock,))
 else:raise ValueError('Unknown setup operation')

def validate_date(c,value):
 day=date.fromisoformat(value).isoformat();company=c.execute('SELECT * FROM company').fetchone()
 if not company:raise ValueError('Company setup is required before posting transactions')
 if not company['year_start']<=day<=company['year_end']:raise ValueError('Transaction date is outside the financial year')
 if company['locked_through'] and day<=company['locked_through']:raise ValueError('Transaction date is in a locked period')
 return day
