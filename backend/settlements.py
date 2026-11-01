"""Invoice-linked receipts, supplier payments and refunds in integer paise."""
import hashlib,json

KINDS={'receipt':('sale',1),'payment':('purchase',1),'refund':('sale',-1),'supplier_refund':('purchase',-1)}

def initialize(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS settlement(voucher INTEGER NOT NULL REFERENCES documents(id),invoice INTEGER NOT NULL REFERENCES documents(id),amount INTEGER NOT NULL CHECK(amount>0),direction INTEGER NOT NULL CHECK(direction IN (-1,1)),PRIMARY KEY(voucher,invoice));
 CREATE TABLE IF NOT EXISTS settlement_request(key TEXT PRIMARY KEY,digest TEXT NOT NULL,voucher INTEGER NOT NULL REFERENCES documents(id));
 CREATE TABLE IF NOT EXISTS settlement_account(voucher INTEGER PRIMARY KEY REFERENCES documents(id),ledger INTEGER NOT NULL REFERENCES ledger(id));
 ''')

def outstanding(c,invoice):
 doc=c.execute("SELECT * FROM documents WHERE id=? AND kind IN ('sale','purchase')",(invoice,)).fetchone()
 if not doc:raise ValueError('Select a sale or purchase invoice')
 returned=c.execute("SELECT COALESCE(SUM(total),0) FROM documents WHERE reference=? AND kind IN ('return','purchase_return')",(invoice,)).fetchone()[0]
 paid=c.execute('SELECT COALESCE(SUM(amount*direction),0) FROM settlement WHERE invoice=?',(invoice,)).fetchone()[0]
 return doc,doc['total']-returned-paid

def snapshot(c):
 balances=[]
 for row in c.execute("SELECT id FROM documents WHERE kind IN ('sale','purchase') ORDER BY id DESC"):
  doc,balance=outstanding(c,row['id']);balances.append({'invoice':doc['id'],'number':doc['kind'].upper()+'-'+str(doc['id']).zfill(5),'kind':doc['kind'],'party':doc['party'],'date':doc['date'],'total_paise':doc['total'],'balance_paise':balance})
 rows=[dict(r) for r in c.execute('SELECT settlement.*,documents.kind,documents.date,documents.party,ledger.name AS cash_account FROM settlement JOIN documents ON documents.id=settlement.voucher JOIN settlement_account ON settlement_account.voucher=documents.id JOIN ledger ON ledger.id=settlement_account.ledger ORDER BY voucher DESC')]
 return {'outstanding':balances,'settlements':rows}

def post(c,d,cents,validate_date):
 kind=d.get('kind')
 if kind not in KINDS:raise ValueError('Select receipt, payment or refund')
 key=d.get('request_key')
 if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('A transaction request key is required')
 digest=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 previous=c.execute('SELECT * FROM settlement_request WHERE key=?',(key,)).fetchone()
 if previous:
  if previous['digest']!=digest:raise ValueError('Request key already used for a different settlement')
  return previous['voucher']
 day=validate_date(c,d['date'])
 ledger=c.execute("SELECT * FROM ledger WHERE id=? AND category IN ('cash','bank')",(int(d['ledger']),)).fetchone()
 if not ledger:raise ValueError('Select a cash or bank ledger')
 allocations=d.get('allocations')
 if not isinstance(allocations,list) or not 1<=len(allocations)<=500:raise ValueError('Allocate at least one invoice')
 source_kind,direction=KINDS[kind];party=None;seen=set();lines=[]
 for row in allocations:
  invoice=int(row['invoice']);amount=cents(row['amount'])
  if invoice in seen or amount<=0:raise ValueError('Use each invoice once with a positive amount')
  seen.add(invoice);doc,balance=outstanding(c,invoice)
  if doc['kind']!=source_kind:raise ValueError('Invoice type does not match settlement')
  if direction*balance<=0 or amount>direction*balance:raise ValueError('Allocation exceeds the remaining invoice balance')
  if doc['date']>day:raise ValueError('Settlement cannot precede invoice date')
  if party is None:party=doc['party']
  if doc['party']!=party:raise ValueError('Allocate invoices for one party per voucher')
  if not c.execute('SELECT 1 FROM journal WHERE document=?',(invoice,)).fetchone():raise ValueError('Reconcile this legacy invoice before settlement')
  lines.append((invoice,amount))
 total=sum(amount for invoice,amount in lines)
 if cents(d.get('amount',0))!=total:raise ValueError('Allocated amounts must equal the voucher amount')
 voucher=c.execute('INSERT INTO documents(kind,party,date,total) VALUES(?,?,?,?)',(kind,party,day,total)).lastrowid
 c.execute('INSERT INTO settlement_account VALUES(?,?)',(voucher,ledger['id']))
 c.executemany('INSERT INTO settlement VALUES(?,?,?,?)',[(voucher,invoice,amount,direction) for invoice,amount in lines])
 # Qualify cash/bank accounts so an account named "Sales" cannot merge into sales revenue.
 cash='Cash/bank: '+ledger['name'];control='Trade receivables' if source_kind=='sale' else 'Trade payables'
 incoming=kind in ('receipt','supplier_refund')
 postings=[(cash,total,0),(control,0,total)] if incoming else [(control,total,0),(cash,0,total)]
 for account,debit,credit in postings:c.execute('INSERT INTO journal(document,account,debit,credit) VALUES(?,?,?,?)',(voucher,account,debit,credit))
 c.execute('INSERT INTO settlement_request VALUES(?,?,?)',(key,digest,voucher))
 return voucher
