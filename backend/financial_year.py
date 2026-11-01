"""Close a completed year without deleting stock, invoices or receivable history."""
import json
import time
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

RETAINED = 'Year-end retained earnings'
STOCK = 'Inventory at year close'
OPENING_STOCK = 'Opening stock expense'
CLOSING_STOCK = 'Closing stock adjustment'


def money(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError('Enter a valid reviewed closing-stock value') from e
    if not amount.is_finite() or amount < 0 or amount > Decimal('100000000000'):
        raise ValueError('Enter a valid reviewed closing-stock value')
    return int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def initialize(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS closing_stock(year_start TEXT PRIMARY KEY,amount INTEGER NOT NULL CHECK(amount>=0),note TEXT NOT NULL,stock_snapshot TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS financial_year(year_start TEXT PRIMARY KEY,year_end TEXT NOT NULL,closed_by TEXT NOT NULL,closed_at INTEGER NOT NULL,trial_balance TEXT NOT NULL,profit INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS year_opening(year_start TEXT NOT NULL,account TEXT NOT NULL,debit INTEGER NOT NULL CHECK(debit>=0),credit INTEGER NOT NULL CHECK(credit>=0),PRIMARY KEY(year_start,account),CHECK(debit=0 OR credit=0));
    ''')


def preview(c, trial_sql, valuation=None):
    company = c.execute('SELECT * FROM company').fetchone()
    if not company:
        raise ValueError('Set up the company before closing a year')
    for ledger in c.execute("SELECT name,category FROM ledger WHERE category NOT IN ('cash','bank','customer','supplier','party')"):
        if ledger['name'] in ('Sales','Purchases','Trade receivables','Trade payables','Input tax pending classification','Output tax pending classification',RETAINED,STOCK,OPENING_STOCK,CLOSING_STOCK) or ledger['name'].startswith(('Party ledger:','Cash/bank:')):
            raise ValueError('Reconcile the ledger name that conflicts with a system account: '+ledger['name'])
    if date.fromisoformat(company['year_end']) >= date.today():
        raise ValueError('Close a financial year only after its end date')
    if c.execute('SELECT 1 FROM documents WHERE date BETWEEN ? AND ? AND NOT EXISTS(SELECT 1 FROM journal WHERE document=documents.id)', (company['year_start'], company['year_end'])).fetchone():
        raise ValueError('Reconcile documents without journal entries before closing')
    if c.execute('SELECT document FROM journal GROUP BY document HAVING SUM(debit-credit)!=0').fetchone():
        raise ValueError('Correct unbalanced journals before closing')
    trial = [dict(r) for r in c.execute(trial_sql)]
    if sum(r['debit'] - r['credit'] for r in trial):
        raise ValueError('Trial balance must balance before closing')
    opening_stock = sum(r['debit']-r['credit'] for r in trial if r['account']==STOCK)
    if valuation is not None:
        closing = money(valuation)
        trial += [{'account':OPENING_STOCK,'debit':opening_stock,'credit':0}, {'account':STOCK,'debit':0,'credit':opening_stock}, {'account':STOCK,'debit':closing,'credit':0}, {'account':CLOSING_STOCK,'debit':0,'credit':closing}]
        merged = {}
        for row in trial:
            target=merged.setdefault(row['account'],{'account':row['account'],'debit':0,'credit':0})
            target['debit']+=row['debit'];target['credit']+=row['credit']
        trial=sorted(merged.values(),key=lambda r:r['account'])
    nominal = {'Sales', 'Purchases', OPENING_STOCK, CLOSING_STOCK} | {r['name'] for r in c.execute("SELECT name FROM ledger WHERE category IN ('income','expense')")}
    balances = {}
    profit = 0
    for row in trial:
        balance = row['debit'] - row['credit']
        if row['account'] in nominal:
            profit -= balance
        else:
            balances[row['account']] = balance
    balances[RETAINED] = balances.get(RETAINED, 0) - profit
    carry = [{'account': name, 'debit': max(0, n), 'credit': max(0, -n)} for name, n in sorted(balances.items()) if n]
    if sum(r['debit'] - r['credit'] for r in carry):
        raise ValueError('Opening carry-forward does not balance')
    next_start = date.fromisoformat(company['year_end']) + timedelta(days=1)
    # Calendar arithmetic also handles a year ending on 28/29 February.
    try:
        next_end = next_start.replace(year=next_start.year + 1) - timedelta(days=1)
    except ValueError:
        next_end = date(next_start.year + 1, 2, 28)
    return {'year_start': company['year_start'], 'year_end': company['year_end'],
            'next_start': next_start.isoformat(), 'next_end': next_end.isoformat(),
            'profit_paise': profit, 'opening_stock_paise': opening_stock, 'trial_balance': trial, 'carry_forward': carry}


def close(c, d, actor, trial_sql):
    if not actor or actor['role'] != 'admin':
        raise PermissionError('Only an administrator may close the financial year')
    info = preview(c, trial_sql)
    if d.get('year_start') != info['year_start'] or d.get('year_end') != info['year_end']:
        raise ValueError('The current year changed; review the closing again')
    company = c.execute('SELECT name FROM company').fetchone()
    if d.get('confirm') != company['name']:
        raise ValueError('Enter the business name exactly to confirm year closure')
    start = date.fromisoformat(d.get('next_start', ''))
    end = date.fromisoformat(d.get('next_end', ''))
    if start.isoformat() != info['next_start'] or not start < end or (end - start).days > 366:
        raise ValueError('The next year must start immediately after this year and end within 366 days')
    stock_value = money(d.get('closing_stock',''))
    note = d.get('valuation_note')
    if not isinstance(note,str) or not 1 <= len(note.strip()) <= 500:
        raise ValueError('Record the closing-stock valuation basis and review reference')
    opening = info['opening_stock_paise']
    entries = [(OPENING_STOCK, opening, 0), (STOCK,0,opening), (STOCK,stock_value,0), (CLOSING_STOCK,0,stock_value)]
    if opening or stock_value:
        doc = c.execute('INSERT INTO documents(kind,party,date,total,company_snapshot) VALUES(?,?,?,?,?)', ('year_adjustment','Closing inventory valuation',info['year_end'],stock_value,json.dumps(dict(c.execute('SELECT * FROM company').fetchone())))).lastrowid
        c.executemany('INSERT INTO journal(document,account,debit,credit) VALUES(?,?,?,?)', [(doc,account,debit,credit) for account,debit,credit in entries if debit or credit])
    stock = [dict(r) for r in c.execute('SELECT id,name,batch,expiry,stock,quarantine FROM products ORDER BY id')]
    c.execute('INSERT INTO closing_stock VALUES(?,?,?,?)',(info['year_start'],stock_value,note.strip(),json.dumps(stock)))
    # Recalculate only after the inventory adjustments, in this same transaction.
    info = preview(c,trial_sql)
    c.execute('INSERT INTO financial_year VALUES(?,?,?,?,?,?)', (info['year_start'], info['year_end'], actor['username'], int(time.time()), json.dumps(info['trial_balance']), info['profit_paise']))
    c.executemany('INSERT INTO year_opening VALUES(?,?,?,?)', [(start.isoformat(), r['account'], r['debit'], r['credit']) for r in info['carry_forward']])
    c.execute('UPDATE company SET year_start=?,year_end=?,locked_through=? WHERE id=1', (start.isoformat(), end.isoformat(), info['year_end']))


def snapshot(c):
    return {'closing_stock_reviews':[dict(r) for r in c.execute('SELECT year_start,amount,note FROM closing_stock ORDER BY year_start DESC')], 'closed_years': [{**dict(r), 'trial_balance': json.loads(r['trial_balance'])} for r in c.execute('SELECT * FROM financial_year ORDER BY year_start DESC')],
            'year_openings': [dict(r) for r in c.execute('SELECT * FROM year_opening WHERE year_start=(SELECT year_start FROM company WHERE id=1) ORDER BY account')]}
