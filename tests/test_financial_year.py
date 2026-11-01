import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server
import financial_year


class FinancialYear(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = server.DB
        server.DB = Path(self.tmp.name) / 'store'
        server.init()
        server.mutate('/api/company', dict(name='Test pharmacy', address='Test', year_start='2023-01-01', year_end='2023-12-31'))
        server.mutate('/api/ledgers', dict(name='Till', category='cash'))
        server.mutate('/api/ledgers', dict(name='Capital', category='equity'))
        state = server.snapshot()
        self.cash = next(r['id'] for r in state['ledgers'] if r['name'] == 'Till')
        capital = next(r['id'] for r in state['ledgers'] if r['name'] == 'Capital')
        server.mutate('/api/openings', dict(lines=[dict(ledger=self.cash, debit=100), dict(ledger=capital, credit=100)]))
        server.mutate('/api/products', dict(name='Medicine', batch='A', expiry='2030-01', price=10, tax=0))
        self.pid = server.snapshot()['products'][0]['id']
        self.purchase = self.doc('purchase', 10, '2023-01-01')
        self.sale = self.doc('sale', 2, '2023-01-02')
        self.actor = dict(role='admin', username='Test owner')

    def tearDown(self):
        server.DB = self.original
        self.tmp.cleanup()

    def doc(self, kind, qty, day, reference=None):
        state = server.mutate('/api/documents', dict(kind=kind, party='Test party', date=day, reference=reference, lines=[dict(product=self.pid, qty=qty, price=5)]))
        return state['documents'][-1]['id']

    def close(self, value=40):
        info = server.mutate('/api/year-preview', {})
        # Direct test actor has no operator row; exercise close in the transaction
        # without audit insertion (the HTTP path supplies a genuine operator).
        with server.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            financial_year.close(c, {**info, 'confirm': 'Test pharmacy', 'closing_stock':value, 'valuation_note':'Reviewed purchase cost of remaining stock'}, self.actor, server.TRIAL_BALANCE_SQL)
        return info

    def test_balances_profit_stock_and_invoice_history_survive_rollover(self):
        before = server.snapshot()
        info = self.close()
        self.assertEqual(info['profit_paise'], -3000)  # Periodic purchase accounting.
        state = server.snapshot()
        self.assertEqual(state['company']['year_start'], '2024-01-01')
        self.assertEqual(state['company']['locked_through'], '2023-12-31')
        self.assertEqual(state['products'], before['products'])
        self.assertEqual(state['documents'][:-1], before['documents'])
        self.assertEqual(state['documents'][-1]['kind'], 'year_adjustment')
        self.assertEqual(state['outstanding'], before['outstanding'])
        accounts = {r['account']: r['debit'] - r['credit'] for r in state['accounts']}
        self.assertNotIn('Sales', accounts)
        self.assertNotIn('Purchases', accounts)
        self.assertEqual(accounts['Cash/bank: Till'], 10000)
        self.assertEqual(accounts[financial_year.RETAINED], -1000)
        self.assertEqual(sum(accounts.values()), 0)
        self.assertEqual(state['closed_years'][0]['profit'],1000)
        self.assertEqual(accounts[financial_year.STOCK],4000)
        with self.assertRaises(ValueError):
            self.doc('sale', 1, '2023-12-31')
        with self.assertRaises(ValueError):
            server.mutate('/api/openings', dict(lines=[]))

    def test_prior_invoice_receipt_and_return_post_into_next_year(self):
        self.close()
        server.mutate('/api/settlements', dict(kind='receipt', request_key='next-year', date='2024-01-02', ledger=self.cash, amount=20, allocations=[dict(invoice=self.sale, amount=20)]))
        self.doc('return', 1, '2024-01-03', self.sale)
        state = server.snapshot()
        self.assertEqual(next(r['balance_paise'] for r in state['outstanding'] if r['invoice'] == self.sale), -1000)
        self.assertEqual(sum(r['debit'] - r['credit'] for r in state['accounts']), 0)
        info = self.close(45)
        self.assertEqual(info['profit_paise'], -1000)
        accounts = {r['account']: r['debit'] - r['credit'] for r in server.snapshot()['accounts']}
        self.assertEqual(accounts[financial_year.RETAINED], -500)
        self.assertEqual(accounts['Cash/bank: Till'], 12000)

    def test_invalid_confirmation_dates_and_permissions_are_atomic(self):
        info = server.mutate('/api/year-preview', {})
        for fields in ({'confirm': 'wrong'}, {'next_start': '2024-01-02'}, {'year_end': '2022-12-31'}):
            with self.assertRaises(ValueError):
                with server.connection() as c:
                    financial_year.close(c, {**info, 'confirm': 'Test pharmacy', **fields}, self.actor, server.TRIAL_BALANCE_SQL)
            self.assertEqual(server.snapshot()['closed_years'], [])
        with self.assertRaises(PermissionError):
            with server.connection() as c:
                financial_year.close(c, info, dict(role='accountant'), server.TRIAL_BALANCE_SQL)

    def test_unbalanced_and_legacy_documents_prevent_close(self):
        with server.connection() as c:
            c.execute('DELETE FROM journal WHERE document=?', (self.sale,))
        with self.assertRaisesRegex(ValueError, 'Reconcile'):
            server.mutate('/api/year-preview', {})

    def test_cannot_close_unfinished_year(self):
        with server.connection() as c:
            c.execute('UPDATE company SET year_end=?', (str(server.date.today().year + 1) + '-12-31',))
        with self.assertRaisesRegex(ValueError, 'end date'):
            server.mutate('/api/year-preview', {})

    def test_reviewed_stock_adjustment_matches_preview_and_rejects_missing_basis(self):
        before = server.snapshot()
        info = server.mutate('/api/year-preview', {'closing_stock':40})
        self.assertEqual(info['profit_paise'],1000)
        self.assertEqual(server.snapshot()['documents'],before['documents'])
        with self.assertRaises(ValueError):
            with server.connection() as c:
                financial_year.close(c,{**info,'confirm':'Test pharmacy','closing_stock':40},self.actor,server.TRIAL_BALANCE_SQL)
        self.assertEqual(server.snapshot()['closed_years'],[])
        self.close(40)
        state=server.snapshot()
        self.assertEqual(state['closed_years'][0]['profit'],info['profit_paise'])
        self.assertEqual(state['closing_stock_reviews'][0]['amount'],4000)
        adjustment=state['documents'][-1]['id']
        self.assertEqual(sum(r['debit']-r['credit'] for r in state['journal'] if r['document']==adjustment),0)
