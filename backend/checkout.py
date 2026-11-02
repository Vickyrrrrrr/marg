"""Post a counter receipt inside the sale's stock/accounting transaction."""
import settlements


def initialize(c):
    c.execute('''CREATE TABLE IF NOT EXISTS checkout_payment(
        document INTEGER PRIMARY KEY REFERENCES documents(id),
        mode TEXT NOT NULL CHECK(mode IN ('cash','bank','credit')),
        ledger INTEGER REFERENCES ledger(id),
        received INTEGER NOT NULL CHECK(received>=0),
        tendered INTEGER NOT NULL CHECK(tendered>=0),
        change INTEGER NOT NULL CHECK(change>=0),
        voucher INTEGER REFERENCES documents(id))''')


def post(c, document, data, cents, validate_date):
    payment = data.get('payment')
    if not isinstance(payment, dict):
        raise ValueError('Choose cash, bank or credit for this sale')
    mode = payment.get('mode')
    if mode not in ('cash', 'bank', 'credit'):
        raise ValueError('Choose cash, bank or credit for this sale')
    doc = c.execute('SELECT * FROM documents WHERE id=?', (document,)).fetchone()
    tendered = cents(payment.get('amount', 0))
    ledger = None
    received = 0
    change = 0
    voucher = None
    if mode == 'credit':
        if tendered or payment.get('ledger') not in (None, ''):
            raise ValueError('Credit sales cannot include a cash/bank receipt')
    else:
        ledger = c.execute('SELECT id,category FROM ledger WHERE id=?', (payment.get('ledger'),)).fetchone()
        if not ledger or ledger['category'] != mode:
            raise ValueError('Select a matching cash or bank ledger')
        if tendered <= 0 and doc['total']:
            raise ValueError('Enter the amount received, or choose credit')
        if mode == 'bank' and tendered > doc['total']:
            raise ValueError('Bank receipt cannot exceed the invoice total')
        received = min(tendered, doc['total'])
        change = tendered - received
        if received:
            voucher = settlements.post(c, dict(kind='receipt', date=doc['date'], ledger=ledger['id'],
                amount=f'{received // 100}.{received % 100:02d}', request_key='checkout-' + str(document),
                allocations=[dict(invoice=document, amount=f'{received // 100}.{received % 100:02d}')]), cents, validate_date)
    c.execute('INSERT INTO checkout_payment VALUES(?,?,?,?,?,?,?)', (
        document, mode, ledger['id'] if ledger else None, received, tendered, change, voucher))


def snapshot(c):
    return {r['document']: dict(r) for r in c.execute('SELECT * FROM checkout_payment')}
