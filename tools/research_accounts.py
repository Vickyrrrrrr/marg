"""Read shipped table structures; never execute embedded formulas or code."""
import struct,json,hashlib,collections,zipfile,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'analysis/extracted/app/System';OUT=ROOT/'analysis/account-research';OUT.mkdir(exist_ok=True)
def dbf(b):
 if len(b)<32:raise ValueError('Missing header')
 n=struct.unpack_from('<I',b,4)[0];header,size=struct.unpack_from('<HH',b,8)
 if header<33 or size<1 or header+n*size>len(b):raise ValueError('Invalid table boundaries')
 fields=[];offset=1
 for i in range(32,header-1,32):
  if b[i]==13:break
  d=b[i:i+32];name=d[:11].split(b'\0')[0].decode('ascii');length=d[16];fields.append(dict(name=name,type=chr(d[11]),length=length,decimals=d[17],offset=offset));offset+=length
 if offset!=size:raise ValueError('Field lengths do not match record size')
 rows=[]
 for index in range(n):
  raw=b[header+index*size:header+(index+1)*size]
  if raw[0]==42:continue
  row={f['name']:raw[f['offset']:f['offset']+f['length']].decode('cp1252',errors='replace').strip() for f in fields}
  rows.append((index+1,header+index*size,row))
 return fields,rows
b=(SRC/'marg0001.ini').read_bytes();_,rows=dbf(b);schemas=collections.defaultdict(list)
for index,offset,r in rows:
 schemas[r['FILENAME']].append({**r,'source_record':index,'source_byte_offset':offset})
(OUT/'declared-schemas.json').write_text(json.dumps({'source':'marg0001.ini','sha256':hashlib.sha256(b).hexdigest(),'tables':schemas},indent=2))
b=(SRC/'marg0004.ini').read_bytes();fields,rows=dbf(b)
groups=[{'record':i,'offset':o,**{k:r[k] for k in ['COUNTRY','GCODE','PARNAM','GROUP','TYPE','PAYDR','PAYCR','RECDR','RECCR','SALDR','SALCR','PURDR','PURCR']}} for i,o,r in rows]
(OUT/'group-reference.json').write_text(json.dumps({'source':'marg0004.ini','sha256':hashlib.sha256(b).hexdigest(),'fields':fields,'rows':groups},indent=2))
with zipfile.ZipFile(SRC/'autodemo.zip') as z:
 samples=[]
 for name in z.namelist():
  if name.upper().startswith(('ACGROUP.','LEDGER.','COMPANY.','VOUCHER.','OUTSTAND.')):
   if z.getinfo(name).flag_bits & 1:
    samples.append({'member':name,'encrypted':True,'fields':None,'records':None});continue
   data=z.read(name)
   try:f,rs=dbf(data)
   except ValueError:continue
   samples.append({'member':name,'sha256':hashlib.sha256(data).hexdigest(),'records':len(rs),'fields':f})
(OUT/'bundled-demo-schemas.json').write_text(json.dumps(samples,indent=2))
print('Declared table count:',len(schemas));print('Shipped group reference rows:',len(groups));print('Bundled sample tables:',len(samples))
for name,fs in schemas.items():
 if any(k in name.upper() for k in ['COMP','GROUP','LEDG','VOU','OUT','YEAR','SETUP']):print(name,','.join(f['FIELD_NAME'] for f in fs))
print('Reference group names:',', '.join(sorted({r['PARNAM'] for r in groups if r['COUNTRY']=='INDIA'})))
