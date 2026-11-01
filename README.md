# Ledgerly

Ledgerly is an offline desktop application for pharmacy retailers and wholesalers, built for Windows and macOS with Electron, Python and SQLite. Business records stay in the local application-data folder. A separately rented server is not needed for a single desktop. Marg ERP is a workflow reference; Ledgerly uses its own implementation and interface.

## Implemented workflows

- Company identity, licences, financial-year setup, classified accounts, customer/supplier masters and balanced opening entries.
- Medicine batches with generic name, strength, manufacturer, schedule, HSN, barcode, expiry, pack size, selling price and MRP. Barcode entry selects an available batch in expiry order for operator review.
- Pack/loose counter sales, inclusive/exclusive tax arithmetic, stock and expiry checks, retry protection and durable held bills. Held bills do not reserve stock; posting rechecks current conditions.
- Multi-batch purchase receipts and original-invoice customer/supplier returns. Supplier invoice numbers are checked for duplicates within a supplier ledger. Customer returns enter quarantine for inspection or disposal.
- Batch recalls with recorded references, reasons and closure findings. Active recalls block sales and quarantine release. Batch history links purchases, supplies and returns without deleting original records.
- Invoice-linked partial/multi-invoice receipts, supplier payments and refunds, using cash/bank ledgers. Exact allocation, party identity, remaining balances, dates and balanced postings are enforced.
- Journal, current-year trial balance, party statements and outstanding invoices. Completed years close with a reviewed closing-stock value and valuation reference. The app posts opening/closing inventory adjustments, archives the closing trial balance, transfers income/expense results to retained earnings and carries balance-sheet accounts forward. Stock quantities and unpaid invoices remain available across years.
- Saved sales invoice display and system printing, with business identity captured when the invoice was posted.
- Backup creation, export, import, inspection and restore. Restore requires an administrator password and business-name confirmation, saves a safety backup, replaces the database atomically and revokes every session. API requests are serialized with recovery so waiting writes must authenticate against the restored database.

## Pharmacy records and access

First launch creates the administrator; there are no default credentials or seeded business transactions. Administrators manage local administrator, manager, pharmacist, cashier and accountant accounts. Role/status/password changes revoke sessions, and the last active administrator cannot be disabled. Passwords use salted PBKDF2 hashes; sessions expire after eight hours. Backend permissions protect writes and attribute changes to operators.

H/H1 retail posting requires prescription reference/date, patient and prescriber details, and a pharmacist or administrator with a recorded pharmacist registration. The supply register is saved atomically with the invoice. Returns do not erase supply records. Only administrators and pharmacists can access the register; CSV export is available. Held prescription details remain limited to the bill's owner and administrators.

Scheduled wholesale supplies require an administrator/manager and recorded company/customer drug licences. They do not create patient dispensing records. Classification and licence/registration details are entered by operators and are not externally verified. Existing batches default to OTC and require review. Prescription fields are informed by the official [Drugs Rules](https://cdsco.gov.in/opencms/resources/UploadCDSCOWeb/2022/drug_rules/Drugs%20Rules%201945_2024%2009.pdf); this application does not certify statutory compliance.

## Current limits

This remains a development build. Complete GST classification/reporting and filing integrations, Schedule X controls, an authoritative medicine catalogue, statutory/thermal invoice formats, purchase orders and schemes, pricing/discount rules, stocktake and automated stock valuation, on-account advances, bank reconciliation and shared-counter networking remain unfinished. Year-end inventory value must be reviewed and entered by the business; the app does not derive FIFO/weighted-average cost or impairment automatically. Historical unlinked/unposted invoices require reconciliation, and unposted documents block year closure.

Backup import/restore accepts matching database schemas up to 64 MB. Backups contain business records, credentials in hashed form and any prescription records; exported files are not encrypted. Store them securely. Restore brings back the backup's operator credentials. An older app refuses a database marked with a newer schema version.

Windows/macOS installers are unsigned development builds. Production use still requires verified target-OS launch, printer/scanner checks, business-account reconciliation and representative pharmacy acceptance testing. See [GOALS.md](GOALS.md) for the intended scope and [TESTING.md](TESTING.md) for required checks.

## Run locally

For development, install Node.js and Python 3.12, then run:

```sh
npm ci
npm start
```

For browser development, run `python backend/server.py` and open `http://127.0.0.1:8001`. Use `python3` where appropriate. Backend-only development uses `data/erp.sqlite3`; the desktop app uses the operating system's application-data folder. The HTTP service binds only to loopback.

## Build desktop installers

Build on the target operating system:

```sh
python -m pip install -r scripts/requirements-build.txt
python scripts/build_backend.py
python scripts/smoke_backend.py
```

Then run `npm run package:win` on Windows or `npm run package:mac` on macOS. Packaged apps include the backend, so end users do not need Python installed.

GitHub Actions runs exclusively through **Actions → Desktop validation → Run workflow**, with Windows selected by default; macOS and both are also available. Routine installer builds run packaging checks; full application tests and JavaScript checks are an optional manual input. Pushes do not trigger Actions. Dependencies, build tools and matching compiled backends are cached, and the packaged-backend smoke check always runs. Installers are uploaded as workflow artifacts, and publishing is disabled with `--publish never`; no GitHub release token is required. Default icons and skipped signing are expected for these development builds.

## Source layout

- `app/`: interface and styles.
- `backend/`: local service, business rules, accounting, access control and recovery.
- `desktop/`: Electron entry point.
- `scripts/`: backend packaging and smoke check.
- `tests/`: transaction, authorization and recovery regression tests.
