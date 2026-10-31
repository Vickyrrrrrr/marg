# Account setup: evidence and implementation specification

## Scope and evidence quality

This report examines the uploaded Marg ERP installer's shipped files. No generated records or fabricated customer transactions are used. The bundled `autodemo.zip` is a demonstration dataset, not a live business database; its selected account members are encrypted and were only inventoried. No runtime accounting behavior is claimed from that archive.

Run `python3 tools/research_accounts.py` to reproduce the table inspection. Outputs live under `analysis/account-research/` with source hashes and byte/record references. Source data is reference material only, not an application dependency.

REA/Ghidra literal trace of `ACGROUP` on margwin.exe returned no matches in its defined-string inventory. The evidence is analysis/ghidra-account-trace.json. This does not prove account-group functionality is absent: the earlier loader traces and opaque resource payload limit what this native analysis establishes.

## What the shipped tables establish

| Artifact | Observation | Interpretation boundary |
|---|---|---|
| marg0001.ini | 2,493 field-definition records describing 65 named table structures | A shipped schema dictionary, not a live database or complete schema guarantee |
| ACGROUP dictionary | Parent/group identifiers, name, type, opening, debit, credit, balance and transaction-direction flags | Group hierarchy and accounting balances are represented; flag semantics are not recovered |
| marg0004.ini | 117 group-reference records, including India classifications for assets, liabilities, capital, sales, purchases, cash, bank, debtors and creditors | Country-specific reference data, not proof of automatic creation for a particular edition |
| GLEDGER dictionary | Voucher, date, account/group codes, debit/credit, remarks, entry/modification identity and date fields | Voucher-based postings and audit metadata are represented; field abbreviations need behavior validation |
| PENDINGS dictionary | Invoice/voucher identifiers, due days/date, final value and balance, plus item/batch fields | Outstanding and pending-transaction data is represented; do not assume every record is a receivable |
| FNMACR dictionary | Operator identity and permissions-like fields | User configuration exists; permission meanings and password security are not established |
| PRO/PROL dictionary | Pack and unit fields, multiple price rates, MRP, opening/balance, tax, scheme and free quantity fields | Product/stock configuration is broader than the current app; business calculations remain unverified |
| marg0007.ini | Configuration includes opening freeze, carry balances, billwise/on-account outstanding and financial-year administration | Shipped options, not validated execution paths |

## Workflow corroborated by official documentation

1. Select a company and define its new financial-year start/end. Marg documents optional transfer of ledger balances, outstanding amounts, stock, challans and pending orders. Transfer/history behavior must be treated separately rather than just copying a closing total. Source: https://care.margcompusoft.com/margerp/general-queries/304/utils/common
2. Enter ledger opening balances through opening balances or ledger modification. On-account balances differ from bill-by-bill balances; bill-by-bill requires invoice and due details. Source: https://care.margcompusoft.com/margerp/opening-balances/1856/1/How-to-Feed-Ledger-Opening
3. Review group summaries with debit/credit, underlying ledgers, opening balances and date ranges. Source: https://care.margcompusoft.com/margerp/group-summary/30168/1/How-to-see-group-summary
4. Carry-forward must reconcile previous closing to current opening. Later changes in the previous period can require refreshed carry-forward. Source: https://care.margcompusoft.com/margerp/carry-balances/306/1/If-last-year-closing-balances

These steps are documented behavior, not observations of this exact installed build.

## Our end-to-end account-setup contract

### Company and periods
- Persist legal/trade names, address, state/country, currency, GST registration status and applicable drug licence details. Do not prefill a fictional pharmacy identity.
- Keep company identities separate from operator identities. Select active company explicitly.
- Persist accounting periods with dates, status and lock date. Reject overlapping years for a company and transactions outside the selected open period.
- Establish a controlled rollover operation: preflight reconciliation, verified backup, opening transfer, reconciliation report, atomic commit and repeat-execution protection.

### Chart of accounts and parties
- Maintain classified groups and immutable account IDs; prohibit hierarchy cycles and posting to summary groups.
- Store customer/supplier ledger IDs on invoices rather than relying on typed party names.
- Store bank/cash accounts separately and use explicit tax account mappings. A generic output-tax account must not be represented as complete Indian GST accounting.
- Validate required business identifiers and track modifications with operator, timestamp and reason.

### Opening balances
- Stage debit/credit amounts per ledger, as of the period start; validate a balanced opening batch before posting.
- For billwise ledgers, collect invoice number/date, due date, original value, outstanding amount and debit/credit direction. Their sum must equal the ledger opening.
- Reconcile inventory quantity and cost by batch separately from ledger openings. Prevent doubling an inventory opening with a purchase receipt.
- Freeze posted openings; use reviewed correction entries instead of silent edits.

### Transactions through reports
- Save a document, balanced accounting entries, stock changes and audit metadata atomically.
- Receipts/payments allocate to outstanding invoices, with partial settlement, on-account amounts and overpayment rules.
- Returns reverse original invoice values and tax allocations; customer stock returns require inspection before saleability.
- Every report must use the selected company and period and drill down to source documents: ledger, group summary, trial balance, receivables/payables ageing, cash/bank book and reconciliation.
- Lock-period changes require a controlled reopening process. Preserve historical document identity and audit trail.

## Actual implementation gap

The app currently has a single database with free-text parties, limited product/batch masters and invoice-linked journal entries. It has no complete company/financial-year model, classified chart of accounts, opening-balance workflow, invoice settlement, cash/bank reconciliation or period locks. Its journal screen is real persisted data but is not a complete accounting system. These gaps must be implemented and tested before production claims.

## Required acceptance scenarios

- Fresh company with no fake records: create a year, classified accounts, debtor/creditor and balanced opening batch.
- Billwise openings reconcile exactly to ledger openings; reject mismatch without partial writes.
- Purchase to supplier payable, sale to customer receivable, partial settlement, return and remaining balance reconcile.
- Block posting into closed/out-of-period dates; preserve another company's data isolation.
- Rollover twice cannot duplicate openings; closing-to-opening reconciliation remains exact.
- Backup, restore and reopen preserve document IDs, ledger totals, stock and outstanding allocation.
- Desktop restart preserves the selected company/year; keyboard-only setup and transaction flows work on Windows and macOS.
