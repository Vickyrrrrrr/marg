# Ledgerly ERP development build

Run `python3 server.py` from this directory. The UI and API share port 8001 (override with PORT). Persistent SQLite data lives in data/erp.sqlite3. Back up this file while the server is stopped.

Flow: create a product batch in Inventory; receive stock in Purchases & returns; create a sale in Billing; return against the original sale invoice. The server validates quantities, rejects overselling and expired stock, limits returns to sold quantities, and commits each document and its stock movements atomically. Monetary amounts are stored in integer paise.

Verification: `python3 -m unittest test_server.py`.

This is a development build without authentication. Do not expose it publicly or enter live business data. Missing work includes user roles, full double-entry accounting, payment allocation, GST compliance integrations, printing, purchase orders, offline operation, migration and browser verification. Tax calculations are illustrative, not a compliance certification.

## Desktop target: Windows and macOS

Electron launches a loopback-only backend on a dynamically allocated port. SQLite is stored in Electron's OS-specific userData folder, not in the installed application. The renderer has no Node access, is sandboxed, and blocks external navigation/new windows. Closing the desktop app stops its backend.

Development: install Node/Python, run `npm install`, then `npm start`.

Packaging on each target OS: install PyInstaller, run `python desktop/build_backend.py`, then `npm run package:win` on Windows or `npm run package:mac` on macOS. Packaged builds embed the Python backend executable, so end users do not need Python. Build and test each architecture separately. Windows signing and macOS signing/notarization credentials are not configured. Installers have not yet been built or tested on either OS.

### Pricing and quantities

Stock is measured in whole loose units. Each batch has a pack size. Billing can accept packs, converts them to loose units, and previews the authoritative backend total before saving. Sale prices and optional MRP are per loose unit. The tax basis is explicit per batch; existing batches remain tax-exclusive after migration. Customer returns allocate original invoice amounts and enter quarantine. New sale retries carry an idempotency key to prevent duplicate posting within the active session. No tax-jurisdiction compliance claim is made.

### Journal scope

New sales/purchases and their returns post balanced journal entries in the same database transaction as stock. Purchases use a periodic purchases account; perpetual inventory valuation and cost-of-goods-sold postings are not implemented. Input/output tax is held in explicitly unclassified accounts pending jurisdiction logic. Payments, bank reconciliation and statutory statements are not implemented. Historical documents are flagged as unposted, not silently treated as complete ledger history. Returns against historical lines without a taxable-value snapshot are rejected until reconciliation is implemented. The trial balance is a development control, not a statutory accounting report.


### Company and year setup

Use Company setup to enter the business identity and financial-year dates. Create classified ledgers and post balanced opening balances before the first invoice. The trial balance includes those openings. Transaction dates must be within the year and after its lock date. This build has one company per database; rollover, multiple companies and billwise opening allocation remain unimplemented. No seeded business records are created.

### Verification performed

16 backend unit/integration tests; JavaScript syntax checks; Chromium UI workflow (company setup, batch creation, purchase receipt, pack sale, saved history); packaged Linux backend startup, HTTP assets and persisted-data restart check. Windows/macOS CI is configured but its results must be checked separately. This is a development application, not a verified production Marg replacement.
