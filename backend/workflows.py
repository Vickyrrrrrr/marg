"""Held counter bills and batch recall controls using durable local records."""
import commercial
import json
import secrets
import time
from datetime import date


def initialize(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS held_bill(id TEXT PRIMARY KEY,owner INTEGER NOT NULL REFERENCES operator(id),label TEXT NOT NULL,payload TEXT NOT NULL,updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS batch_recall(id INTEGER PRIMARY KEY,product TEXT NOT NULL REFERENCES products(id),reason TEXT NOT NULL,reference TEXT NOT NULL,opened_by INTEGER NOT NULL REFERENCES operator(id),opened_at INTEGER NOT NULL,closed_by INTEGER REFERENCES operator(id),closed_at INTEGER,closure TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS active_batch_recall ON batch_recall(product) WHERE closed_at IS NULL;
    ''')


def snapshot(c):
    return {'held_bills': [{**dict(r), 'payload': json.loads(r['payload'])} for r in c.execute('SELECT * FROM held_bill ORDER BY updated_at DESC')],
            'recalls': [dict(r) for r in c.execute('SELECT batch_recall.*,products.name,products.batch,operator.username AS opened_by_name FROM batch_recall JOIN products ON products.id=product JOIN operator ON operator.id=opened_by ORDER BY batch_recall.id DESC')]}


def recalled(c, product):
    return bool(c.execute('SELECT 1 FROM batch_recall WHERE product=? AND closed_at IS NULL', (product,)).fetchone())


def held(c, identifier, actor):
    row = c.execute('SELECT * FROM held_bill WHERE id=?', (identifier,)).fetchone()
    if not row or not actor or (row['owner'] != actor['id'] and actor['role'] != 'admin'):
        raise ValueError('Held bill is unavailable to this operator')
    return row


def mutate(c, path, d, actor, integer):
    if not actor:
        raise PermissionError('Sign in to continue')
    if path == '/api/held-delete':
        held(c, d.get('id'), actor)
        c.execute('DELETE FROM held_bill WHERE id=?', (d['id'],))
    elif path == '/api/held':
        payload = d.get('payload')
        label = d.get('label')
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            raise ValueError('Enter a held-bill label of 1–120 characters')
        if not isinstance(payload, dict) or not isinstance(payload.get('lines'), list) or not 1 <= len(payload['lines']) <= 500:
            raise ValueError('Add medicines before holding a bill')
        lines = []
        seen = set()
        for item in payload['lines']:
            pid = item['product']
            if pid in seen or not c.execute('SELECT 1 FROM products WHERE id=?', (pid,)).fetchone():
                raise ValueError('Unknown or repeated batch')
            seen.add(pid)
            lines.append({'product': pid, 'qty': integer(item['qty']), 'discount_percent': commercial.discount(item.get('discount_percent', 0)) / 100})
        party = payload.get('party', '')
        trade = payload.get('trade', 'retail')
        rx = payload.get('prescription') or {}
        if not isinstance(party, str) or len(party) > 120 or trade not in ('retail', 'wholesale') or not isinstance(rx, dict):
            raise ValueError('Invalid held-bill details')
        allowed = ('reference', 'prescription_date', 'patient', 'patient_address', 'prescriber', 'prescriber_address')
        rx = {k: rx.get(k, '') for k in allowed}
        if any(not isinstance(v, str) or len(v) > 500 for v in rx.values()):
            raise ValueError('Invalid prescription fields')
        if any(rx.values()) and actor['role'] not in ('admin', 'pharmacist'):
            raise ValueError('Only a pharmacist or administrator may retain prescription details')
        day=payload.get('date',date.today().isoformat())
        if not isinstance(day,str):raise ValueError('Invalid held-bill date')
        day=date.fromisoformat(day).isoformat()
        normalized = {'date':day,'party': party, 'trade': trade, 'prescription': rx, 'lines': lines}
        identifier = d.get('id')
        if identifier:
            held(c, identifier, actor)
            c.execute('UPDATE held_bill SET label=?,payload=?,updated_at=? WHERE id=?', (label.strip(), json.dumps(normalized), int(time.time()), identifier))
        else:
            c.execute('INSERT INTO held_bill VALUES(?,?,?,?,?)', (secrets.token_hex(16), actor['id'], label.strip(), json.dumps(normalized), int(time.time())))
    elif path == '/api/recall':
        if actor['role'] not in ('admin', 'manager'):
            raise PermissionError('Only an administrator or manager may recall a batch')
        product = d.get('product')
        if not c.execute('SELECT 1 FROM products WHERE id=?', (product,)).fetchone():
            raise ValueError('Select a medicine batch')
        reason = d.get('reason'); reference = d.get('reference', '')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500 or not isinstance(reference, str) or len(reference) > 160:
            raise ValueError('Enter the recall reason and a valid reference')
        if recalled(c, product):
            raise ValueError('This batch already has an active recall')
        c.execute('INSERT INTO batch_recall(product,reason,reference,opened_by,opened_at) VALUES(?,?,?,?,?)', (product, reason.strip(), reference.strip(), actor['id'], int(time.time())))
    elif path == '/api/recall-close':
        if actor['role'] not in ('admin', 'manager'):
            raise PermissionError('Only an administrator or manager may close a recall')
        row = c.execute('SELECT * FROM batch_recall WHERE id=? AND closed_at IS NULL', (d.get('id'),)).fetchone()
        reason = d.get('closure')
        if not row or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
            raise ValueError('Select an active recall and record the closure findings')
        c.execute('UPDATE batch_recall SET closed_by=?,closed_at=?,closure=? WHERE id=?', (actor['id'], int(time.time()), reason.strip(), row['id']))
    else:
        raise ValueError('Unknown workflow')
