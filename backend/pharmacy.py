"""Medicine identity and immutable prescription-linked dispensing records."""
from datetime import date
FIELDS=('generic_name','strength','manufacturer','hsn','barcode','schedule')

def initialize(c):
 columns={r[1] for r in c.execute('PRAGMA table_info(products)')}
 for field in FIELDS:
  if field not in columns:c.execute(f"ALTER TABLE products ADD COLUMN {field} TEXT NOT NULL DEFAULT '{'OTC' if field=='schedule' else ''}'")
 if 'drug_licence' not in {r[1] for r in c.execute('PRAGMA table_info(ledger)')}:c.execute("ALTER TABLE ledger ADD COLUMN drug_licence TEXT NOT NULL DEFAULT ''")
 if 'trade' not in {r[1] for r in c.execute('PRAGMA table_info(documents)')}:c.execute("ALTER TABLE documents ADD COLUMN trade TEXT NOT NULL DEFAULT 'retail'")
 c.executescript('''
 CREATE INDEX IF NOT EXISTS products_barcode ON products(barcode);
 CREATE TABLE IF NOT EXISTS prescription(document INTEGER PRIMARY KEY REFERENCES documents(id),reference TEXT NOT NULL,prescription_date TEXT NOT NULL,patient TEXT NOT NULL,patient_address TEXT NOT NULL,prescriber TEXT NOT NULL,prescriber_address TEXT NOT NULL,pharmacist INTEGER NOT NULL REFERENCES operator(id),registration TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS dispense_line(document INTEGER NOT NULL REFERENCES documents(id),product TEXT NOT NULL REFERENCES products(id),name TEXT NOT NULL,batch TEXT NOT NULL,schedule TEXT NOT NULL,quantity INTEGER NOT NULL,manufacturer TEXT NOT NULL,expiry TEXT NOT NULL,PRIMARY KEY(document,product));
 ''')

def save_product(c,identifier,d):
 if any(k in d and not isinstance(d[k],str) for k in FIELDS):raise ValueError('Medicine identifiers must be text')
 values={k:d.get(k,'OTC' if k=='schedule' else '').strip() for k in FIELDS}
 if values['schedule'] not in ('OTC','H','H1'):raise ValueError('Supported classifications are OTC, H and H1; Schedule X is not supported')
 if any(len(v)>160 for v in values.values()):raise ValueError('Medicine identifiers must be 160 characters or fewer')
 product=c.execute('SELECT * FROM products WHERE id=?',(identifier,)).fetchone()
 if values['hsn'] and (not values['hsn'].isdigit() or len(values['hsn']) not in (4,6,8)):raise ValueError('HSN must contain 4, 6 or 8 digits')
 if any(ord(char)<32 for char in values['barcode']):raise ValueError('Barcode cannot contain control characters')
 if values['schedule']!='OTC' and (not product['expiry'] or not values['manufacturer']):raise ValueError('Scheduled medicines require manufacturer and expiry')
 if values['barcode']:
  others=c.execute('SELECT * FROM products WHERE barcode=? AND id!=?',(values['barcode'],identifier)).fetchall()
  for other in others:
   if other['name'].casefold()!=product['name'].casefold() or any(other[k].casefold()!=values[k].casefold() for k in ('strength','generic_name','manufacturer','schedule')):raise ValueError('Barcode is already assigned to a different medicine identity')
 c.execute('UPDATE products SET '+','.join(f'{k}=?' for k in FIELDS)+' WHERE id=?',(*values.values(),identifier))

def validate_sale(c,d,actor,day,products):
 trade=d.get('trade','retail')
 if trade not in ('retail','wholesale'):raise ValueError('Select retail or wholesale')
 restricted=[p for p in products if p['schedule'] in ('H','H1')]
 if not restricted:return trade,None
 if trade=='wholesale':
  if not actor or actor['role'] not in ('admin','manager'):raise ValueError('Scheduled wholesale sales require an administrator or manager')
  company=c.execute('SELECT * FROM company').fetchone();ledger=c.execute('SELECT * FROM ledger WHERE id=?',(d.get('_party_ledger'),)).fetchone()
  if not company['drug_licence'].strip() or not ledger or not ledger['drug_licence'].strip():raise ValueError('Scheduled wholesale sales require business and customer drug licences')
  return trade,None
 if not actor or actor['role'] not in ('admin','pharmacist') or not actor.get('registration','').strip():raise ValueError('Scheduled retail sales require a signed-in registered pharmacist')
 rx=d.get('prescription')
 if not isinstance(rx,dict):raise ValueError('Enter prescription details for scheduled retail medicines')
 required=('reference','prescription_date','patient','patient_address','prescriber','prescriber_address')
 if any(not isinstance(rx.get(k),str) for k in required):raise ValueError('Prescription fields must be text')
 values={k:rx[k].strip() for k in required}
 if any(not v or len(v)>500 for v in values.values()):raise ValueError('Complete patient, prescriber, addresses, prescription reference and date')
 if date.fromisoformat(values['prescription_date']).isoformat()>day:raise ValueError('Prescription date cannot be after the sale date')
 return trade,values

def record(c,doc,trade,rx,actor,products,quantities):
 c.execute('UPDATE documents SET trade=? WHERE id=?',(trade,doc))
 if rx:
  c.execute('INSERT INTO prescription VALUES(?,?,?,?,?,?,?,?,?)',(doc,rx['reference'],rx['prescription_date'],rx['patient'],rx['patient_address'],rx['prescriber'],rx['prescriber_address'],actor['id'],actor['registration']))
  for p in products:
   if p['schedule'] in ('H','H1'):c.execute('INSERT INTO dispense_line VALUES(?,?,?,?,?,?,?,?)',(doc,p['id'],p['name'],p['batch'],p['schedule'],quantities[p['id']],p['manufacturer'],p['expiry']))

def register(c):
 return [dict(r) for r in c.execute('SELECT dispense_line.*,documents.date,prescription.reference,prescription.prescription_date,prescription.patient,prescription.patient_address,prescription.prescriber,prescription.prescriber_address,prescription.registration,operator.username AS pharmacist FROM dispense_line JOIN prescription ON prescription.document=dispense_line.document JOIN documents ON documents.id=dispense_line.document JOIN operator ON operator.id=prescription.pharmacist ORDER BY documents.id DESC')]
