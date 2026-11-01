# Pre-push verification

## Application changes

Run the complete backend suite before pushing changes to Python, transaction rules, database setup or connected UI workflows:

```sh
python -m unittest discover -s tests -v
```

**Current requirement: all 31 backend tests must pass, with no failures, errors or skipped tests.** Keep all existing relevant tests when adding functionality; update this count when the suite grows. Do not add tests solely to reach a count.

The suite covers purchases/sales/returns, atomic overselling prevention, return limits and rounding, quarantine/inspection, backup preservation, pack conversion, authoritative quotes, MRP limits, inclusive tax, migrations, duplicate submissions, journal balancing, period locks and balanced opening entries. Each protects a real data or money-handling behavior.

Also run these **6 JavaScript syntax checks** when changing application or desktop JavaScript:

```sh
node --check app/app.js
node --check app/backend.js
node --check app/auth.js
node --check app/payments.js
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

Two connection-lifecycle regression tests verify that success commits and failure rolls back while both paths close SQLite handles. These prevent Windows temporary-directory cleanup failures. The suite currently totals 31 tests.

Manual build commands explicitly use `--publish never`, with `build.publish` disabled in package.json. Workflow artifacts do not require a GitHub release token. Select one target platform for a faster focused build; use both when validating cross-platform changes. Caches reduce repeat download time, not the actual compilation work.

Authentication tests exercise the actual HTTP service: first-owner bootstrap, sign-in/out, role-denied writes, expired sessions, password hashing, audit attribution, last-admin protection and session revocation on operator disable. These protect offline business data rather than testing UI labels.

Settlement tests cover partial receipts, exact invoice clearing, balanced postings, paid-invoice returns/refunds, supplier refunds, retry protection, multi-invoice allocation, cross-party rejection, amount mismatch, concurrent clearing, ledger type validation and period locks. Cashier API checks allow customer receipts while denying supplier payments.
