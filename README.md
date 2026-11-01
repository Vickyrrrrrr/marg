# Ledgerly

Ledgerly is a Windows and macOS desktop application being developed for pharmacy billing, batch inventory and business accounting. It uses Electron with a local Python backend and SQLite database. Marg ERP is a workflow reference; Ledgerly has its own implementation and interface.

Implemented workflows include company and financial-year setup, classified ledger creation, balanced opening entries, period locks, batch inventory, pack/loose sales, inclusive/exclusive tax pricing, MRP checks, purchase receipts, customer/supplier returns, return quarantine and inspection, journal entries, a trial balance and database backups.

This is an incomplete development build. On-account advances, GST reporting, prescription controls, printing, financial-year rollover and verified production installers remain unfinished. See [GOALS.md](GOALS.md) for the intended scope and [TESTING.md](TESTING.md) for pre-push checks.

## Run locally

Install Node.js and Python 3.12, then run:

```sh
npm ci
npm start
```

For backend/UI development without Electron, run `python backend/server.py` and open `http://127.0.0.1:8001`. Use `python3` where that is your Python command. The desktop app stores its database in the operating system's application-data folder; backend-only development uses `data/erp.sqlite3`.

## Build desktop installers

Build on the target operating system:

```sh
python -m pip install -r scripts/requirements-build.txt
python scripts/build_backend.py
python scripts/smoke_backend.py
```

Then run `npm run package:win` on Windows or `npm run package:mac` on macOS. Packaged apps include the backend, so users do not need Python. Builds are unsigned until signing credentials are configured.

GitHub builds run only when someone manually starts **Desktop validation** in the repository's Actions tab. Pushing code does not trigger Actions.

## Source layout

- `app/`: interface and styles.
- `backend/`: local HTTP service, SQLite transactions and business setup.
- `desktop/`: Electron application entry point.
- `scripts/`: backend packaging requirements, builder and packaged-app smoke check.
- `tests/`: database and transaction regression tests.

Manual Actions runs offer Windows, macOS or both. npm, pip, Electron and installer-tool downloads are cached per platform. Installers are uploaded as workflow artifacts; publishing to GitHub Releases is disabled and no GH_TOKEN is required. Default application icons and skipped signing are expected for these unsigned development builds.


Local operators sign in with administrator, manager, cashier or accountant roles. First launch creates the administrator; no default credentials are seeded. Administrators create operators, reset passwords, change roles and disable access. Role/status/password changes revoke existing sessions, and the last active administrator cannot be disabled. Passwords use salted PBKDF2 hashes; session tokens are stored hashed and expire after eight hours. Sensitive writes are role-checked by the local backend and attributed in its audit table. This remains a loopback-only desktop service; shared-counter networking is not enabled.


Invoice settlements support partial or multi-invoice customer receipts, supplier payments, and refunds after returns. Select one party and a cash/bank ledger, allocate exact amounts, then post a balanced voucher. Allocation totals must match the voucher amount; overpayment, cross-party allocation, wrong invoice types and locked dates are rejected. Retry keys prevent duplicate posting. Outstanding balances and allocation history are persisted. This does not yet include on-account advances, write-offs or bank statement reconciliation; invoice parties are still text identities rather than fully linked party masters.

Reference research has reached 54 bill-adjustment-related records and their readable memo fields in the supplied Marg configuration, in addition to its schema dictionary and REA/Ghidra launcher traces. Receipt/adjustment behavior was corroborated against Marg's official [receipt entry](https://care.margcompusoft.com/margerp/voucher-entry/297/1/-receipt) and [bill allocation](https://care.margcompusoft.com/margerp/voucher-entry/29964/1/How-to-adjust-bill-at) documentation. Static reference fields do not establish complete runtime feature coverage.
