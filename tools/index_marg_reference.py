"""Read-only index of configuration labels; does not establish runtime behavior."""
import csv,hashlib,json,struct,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'analysis/extracted/app/System/marg0007.ini';b=p.read_bytes()
n=struct.unpack_from('<I',b,4)[0];h,size=struct.unpack_from('<HH',b,8)
if h+n*size>len(b):raise ValueError('Truncated configuration table')
fields=[]
for pos in range(32,h-32,32):
 if b[pos]==13:break
 d=b[pos:pos+32];fields.append((d[:11].split(b'\0')[0].decode('ascii'),d[16]))
rows=[]
for index in range(n):
 raw=b[h+index*size:h+(index+1)*size]
 if raw[0]==42:continue
 row={};offset=1
 for name,length in fields:
  row[name]=raw[offset:offset+length].decode('cp1252',errors='replace').strip();offset+=length
 if row['QUESTION']:rows.append({'record':index+1,'byte_offset':h+index*size,'type':row['TYPE'],'group':row['STYLE'],'label':row['QUESTION'],'evidence':'shipped configuration label; behavior unverified'})
output=root/'analysis/configuration-index.csv'
with output.open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
groups=collections.Counter((r['type'],r['group']) for r in rows)
lines=['# Marg reference investigation','', 'REA skill: reverse-engineer-anything, installed with rea-agents 6.8.0.','', '## Observed executable facts', '', '- PE32 x86; .NET CLI metadata absent.','- REA import inspection: 4 imported DLLs, 46 imported functions.','- REA resource inspection: 17 resources. Payload contents and runtime behavior are not established.','- Main executable SHA-256: 55488c500463a5b46fcea23e46299a0806319bcd6c42b29716f5177184ef987f.','', '## Configuration reference', '',f'Source SHA-256: {hashlib.sha256(b).hexdigest()}. {n} records declared; {len(rows)} active labeled records indexed using an independent read-only DBF reader. This is not a REA behavior trace.','', '| Type | Group | Indexed labels |','|---|---|---|']
lines += [f'| {t} | {g} | {count} |' for (t,g),count in groups.most_common()]
lines += ['', '## Limits and next investigations', '', 'Ghidra is not configured; REA reports that a Ghidra 12.1.x installation and compatible Java runtime are required for that provider. The existing CLI supports the static inspections completed here. A native decompiler alone may inspect only the launcher if business logic resides in another runtime/payload. No complete feature recovery is claimed.', '', 'Next trace targets: sale price and tax basis; batch selection; expiry constraints; pack conversion; return linkage; supplier claims; permissions; printing; prescription registers. For each, retain the exact artifact identity, observed input/output, reference location, inferred rule, unresolved cases, and an independently written acceptance test. No source or graphical assets from Marg are incorporated into our application.']
(root/'docs/rea-investigation.md').write_text('\n'.join(lines)+'\n')
print(f'Indexed {len(rows)} active configuration labels in {len(groups)} groups')
