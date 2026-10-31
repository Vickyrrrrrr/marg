# Product goal

Build a dependable Windows and macOS desktop alternative to Marg ERP for pharmacy retail and distribution, with an original, practical interface. Use Marg's documented workflows and authorized software analysis as references. Do not copy its code, visual assets or sample business records.

## Required scope

- **Business setup:** company identity, licences, tax registration, financial years, classified accounts, customer/supplier ledgers, reconciled opening balances, period locks and financial-year rollover.
- **Pharmacy masters:** medicines, generic/brand names, manufacturers, strengths, schedules, HSN, barcodes, units/packs, batches, manufacture/expiry dates, MRP and price lists.
- **Counter sales:** keyboard/barcode entry, clear batch selection, expiry and stock checks, packs/loose units, discounts, taxes, held bills, payment methods, invoices and printing.
- **Purchasing and distribution:** supplier invoices, orders, schemes/free quantities, landed cost, customer pricing, credit controls and collections.
- **Returns and inventory:** original-invoice returns, quarantine and inspection, supplier claims, expiry/breakage handling, stocktake, adjustments, recall traceability and stock valuation.
- **Accounting:** balanced postings, invoice-level receivables/payables, receipts/payments, cash/bank reconciliation, tax classification and financial reports.
- **Records and compliance:** applicable prescription/patient/prescriber records, controlled access, drug registers, GST reports and required integrations.
- **Desktop reliability:** durable local data, verified backup/restore, migrations, audit history, signed installers, updates and recovery on both platforms.

## Quality requirements

Use consistent spacing, readable tables and amounts, explicit units, accessible focus states and keyboard-first flows. Save genuine records to the database; never substitute mock screens or fabricated transactions for functionality. Document unsupported behavior accurately.

A workflow is complete only when its UI, validation, persistence, accounting/stock effects, error handling and relevant tests work together. Production readiness requires verified Windows/macOS builds, printer/scanner checks, representative pharmacy acceptance testing and reconciliation of financial and stock records. Passing backend tests alone is insufficient.
