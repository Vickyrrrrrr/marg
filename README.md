# Ledgerly

Ledgerly is a Windows and macOS desktop application being developed for pharmacy billing, batch inventory and business accounting. It uses Electron with a local Python backend and SQLite database. Marg ERP is a workflow reference; Ledgerly has its own implementation and interface.

Implemented workflows include company and financial-year setup, classified ledger creation, balanced opening entries, period locks, batch inventory, pack/loose sales, inclusive/exclusive tax pricing, MRP checks, purchase receipts, customer/supplier returns, return quarantine and inspection, journal entries, a trial balance and database backups.

This is an incomplete development build. Full payment allocation, GST reporting, prescription controls, printing, authentication, financial-year rollover and verified production installers remain unfinished. See [GOALS.md](GOALS.md) for the intended scope and [TESTING.md](TESTING.md) for pre-push checks.

## Run locally

Install Node.js and Python 3.12, then run:

```sh
npm ci
npm start
```

For backend/UI development without Electron, run `python server.py` and open `http://127.0.0.1:8001`. Use `python3` where that is your Python command. The desktop app stores its database in the operating system's application-data folder; backend-only development uses `data/erp.sqlite3`.

## Build desktop installers

Build on the target operating system:

```sh
python -m pip install pyinstaller==6.16.0
python desktop/build_backend.py
python desktop/smoke_backend.py
```

Then run `npm run package:win` on Windows or `npm run package:mac` on macOS. Packaged apps include the backend, so users do not need Python. Builds are unsigned until signing credentials are configured.

GitHub builds run only when someone manually starts **Desktop validation** in the repository's Actions tab. Pushing code does not trigger Actions.
