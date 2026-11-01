"""Persistent party-ledger identity shared by invoices, returns and settlements."""

def initialize(c):
 columns={r[1] for r in c.execute('PRAGMA table_info(ledger)')}
 for name in ('phone','address','gstin'):
  if name not in columns:c.execute(f"ALTER TABLE ledger ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
 if 'party_ledger' not in {r[1] for r in c.execute('PRAGMA table_info(documents)')}:
  c.execute('ALTER TABLE documents ADD COLUMN party_ledger INTEGER REFERENCES ledger(id)')

def account(c,identifier,fallback):
 if identifier is None:return fallback
 row=c.execute('SELECT id,name FROM ledger WHERE id=?',(identifier,)).fetchone()
 if not row:raise ValueError('Party ledger not found')
 return f"Party ledger: {row['id']}: {row['name']}"

def resolve(c,d,kind,create):
 if kind in ('return','purchase_return'):
  original=c.execute('SELECT party,party_ledger FROM documents WHERE id=?',(d.get('reference'),)).fetchone()
  if not original:raise ValueError('Select the original invoice')
  if d.get('party_ledger') not in (None,'') and int(d['party_ledger'])!=original['party_ledger']:raise ValueError('Return must use the original party ledger')
  return original['party_ledger'],original['party']
 identifier=d.get('party_ledger');name=str(d.get('party','')).strip()
 if identifier not in (None,''):
  row=c.execute('SELECT * FROM ledger WHERE id=?',(int(identifier),)).fetchone()
  if not row:raise ValueError('Party ledger not found')
 else:
  name=name or ('Walk-in customer' if kind=='sale' else '')
  if not name:raise ValueError('Supplier name or ledger is required')
  matches=c.execute('SELECT * FROM ledger WHERE name=? COLLATE NOCASE',(name,)).fetchall()
  if len(matches)>1:raise ValueError('Ambiguous ledger name; select its ID')
  row=matches[0] if matches else None
  if row is None:
   if not create:return None,name
   identifier=c.execute("INSERT INTO ledger(name,category) VALUES(?,'party')",(name,)).lastrowid
   return identifier,name
 required='customer' if kind=='sale' else 'supplier'
 if row['category'] not in (required,'party'):raise ValueError('Ledger classification does not allow this transaction')
 return row['id'],row['name']
