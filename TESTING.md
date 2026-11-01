# Pre-push verification

## Application changes

Run the complete backend suite before pushing changes to Python, transaction rules, database setup or connected UI workflows:

```sh
python -m unittest discover -s tests -v
```

**Current requirement: all 70 backend tests must pass, with no failures, errors or skipped tests.** Keep all existing relevant tests when adding functionality; update this count when the suite grows. Do not add tests solely to reach a count.

The suite covers purchases/sales/returns, atomic overselling prevention, return limits and rounding, quarantine/inspection, backup preservation, pack conversion, authoritative quotes, MRP limits, inclusive tax, migrations, duplicate submissions, journal balancing, period locks and balanced opening entries. Each protects a real data or money-handling behavior.

Also run these **10 JavaScript syntax checks** when changing application or desktop JavaScript:

```sh
node --check app/app.js
node --check app/backend.js
node --check app/auth.js
node --check app/payments.js
node --check app/parties.js
node --check app/invoices.js
node --check app/pharmacy.js
node --check app/workflows.js
node --check app/icons.js
node --check desktop/main.cjs
```

For a changed user workflow, manually exercise it through the UI, including invalid input and persistence after restart. Backend tests do not establish UI correctness.

## Packaging changes

On each affected target OS, package the backend and run **1 packaged-backend smoke test** before producing its installer:

```sh
python scripts/build_backend.py
python scripts/smoke_backend.py
```

That test checks startup, HTTP assets and database persistence after restart using temporary test data. Then build the Windows installer or macOS image and verify launch and shutdown on that OS. Linux checks do not certify either desktop target.

## Documentation and workflow-only changes

Check affected links, commands and workflow configuration. Application tests need not be rerun unless executable behavior changed. There are no automatic pre-push hooks or automatic Actions triggers.

## GitHub Actions

Keep one workflow: **Desktop validation**. It is triggered exclusively by `workflow_dispatch`, using Actions → Desktop validation → Run workflow. It runs the backend tests and packaging smoke test on Windows and macOS, then produces unsigned development installers. No push, pull-request, schedule or release trigger is configured. Start it manually when desktop build validation is needed.

Two connection-lifecycle regression tests verify that success commits and failure rolls back while both paths close SQLite handles. These prevent Windows temporary-directory cleanup failures. The suite currently totals 70 tests.

Manual build commands explicitly use `--publish never`, with `build.publish` disabled in package.json. Workflow artifacts do not require a GitHub release token. Select one target platform for a faster focused build; use both when validating cross-platform changes. Caches reduce repeat download time, not the actual compilation work.

Authentication tests exercise the actual HTTP service: first-owner bootstrap, sign-in/out, role-denied writes, expired sessions, password hashing, audit attribution, last-admin protection and session revocation on operator disable. These protect offline business data rather than testing UI labels.

Settlement tests cover partial receipts, exact invoice clearing, balanced postings, paid-invoice returns/refunds, supplier refunds, retry protection, multi-invoice allocation, cross-party rejection, amount mismatch, concurrent clearing, ledger type validation and period locks. Cashier API checks allow customer receipts while denying supplier payments.

Party-ledger tests cover case-insensitive identity, quote purity, original-party return linkage, classification checks, duplicate prevention and settlement against the exact invoice account. Existing unlinked historical documents retain their original generic accounting rather than being silently reassigned.

Invoice tests verify that the saved company snapshot is not changed by later business-profile edits. Browser review also covers party creation, linked ledger statements, original-party return selection and the printable saved invoice.

Pharmacy tests cover prescription completeness and dates, pharmacist authorization/registration, atomic and retained supply records, wholesale licence checks, barcode identity across batches, privacy filtering, metadata validation and rejection of unsupported Schedule X. Browser verification covers pharmacist creation/login, medicine creation, barcode selection, prescription sale and register display.


Recovery tests validate real replacement and safety-backup contents, session revocation, waiting-request authentication, password/name/hash checks, rejected schema/corruption/unbalanced journals, validated import, traversal protection and refusal to downgrade a newer database. Year-close tests check reviewed inventory adjustments, preview purity, archived balances, repeated carry-forward, retained earnings, prior-year invoice settlement/returns, locks, invalid confirmation and premature closure.

Counter workflow tests check durable held bills without financial/stock effects, owner privacy, atomic consumption with sale retry, retained holds after posting failure, recall enforcement in quotes/sales/inspection, authorized closure, and multi-batch supplier invoices with duplicate prevention and rollback. Browser verification must cover receipt entry, close with reviewed inventory, export, reload/resume held bill, recall/trace/closure, sale and restore/sign-in with the expected balances.
