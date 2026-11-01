# Verification and desktop workflows

## Before pushing application changes

Run the source checks and all test groups:

```sh
python scripts/ci_checks.py --group all
```

All **73 current tests** must pass, with no errors, failures, unexpected successes, expected failures or skipped tests. Do not add tests merely to reach a count. Source checks validate the **10 JavaScript files**, Python syntax, package/lock consistency and assignment of every test module to a CI group. A new test module must be added to `GROUPS` in `scripts/ci_checks.py`; otherwise source validation fails.

For a focused change, run an individual group with `python scripts/ci_checks.py --group pharmacy`, substituting the group below. Results are written to ignored `reports/*.json`. On Actions, each group also adds its status and elapsed time to the job summary. The original `python -m unittest discover -s tests -v` command remains available, but the CI runner additionally rejects skipped/expected-failure tests.

| CI group | Tests | Behaviour protected |
|---|---:|---|
| `billing-stock` | 18 | Purchases, sales, returns, overselling, MRP, packs, inclusive tax, rounding, balanced journals, periods, migrations and SQLite handle cleanup |
| `pharmacy` | 11 | Prescription completeness, pharmacist permissions, wholesale licences, supply register retention, patient privacy and barcode identity |
| `parties-invoices` | 8 | Stable party identity, classifications, duplicate prevention, opening/settlement accounts and immutable saved invoice identity |
| `payments` | 7 | Partial/multi-invoice allocations, refunds, retries, concurrent clearing, cash/bank ledgers and locked dates |
| `financial-year` | 6 | Reviewed inventory adjustments, preview purity, archived balances, carry-forward, retained earnings, prior-year invoices and closure validation |
| `security` | 6 | Bootstrap, login/logout, role-denied writes, password storage, session expiry/revocation, audit and last-administrator protection |
| `recovery` | 8 | Safe replacement, safety-copy contents, reauthentication, hashes/schema/integrity, import/traversal, session revocation and waiting-request authentication |
| `counter-recalls` | 6 | Durable holds, atomic sale/retry, recall blocking/closure, multi-batch receipt rollback and supplier-invoice uniqueness |
| `packaging` | 3 | Process/log cleanup after launch failure, startup crash and failure after readiness; real subprocesses and file deletion are exercised |

For a changed user workflow, exercise the UI with valid and invalid inputs and check persistence after restart. Browser verification should cover medicine/party setup, pharmacist login and prescription supply; multi-batch purchase; reviewed year closing; export; reload/resume held bill; recall/trace/closure; sale and restore/sign-in with expected balances. Backend tests do not establish UI correctness.

## One manually triggered Actions workflow

Use **Actions → Desktop validation → Run workflow**. No push, pull-request, schedule or release trigger is configured. There are no automatic pre-push hooks. A fresh run from `main` uses current settings; re-running an old job keeps its original commit/workflow.

| Mode | Validation | Packaging | Platform selection |
|---|---|---|---|
| `fast` | Three packaging-cleanup tests | Backend smoke check and development installer | Windows by default; macOS/both available |
| `validate` | Source/lock checks, then all nine test groups | None | Selected OS or both |
| `release-candidate` | Source/lock checks, then all nine groups on **both OSes** | Only after all checks pass: backend smoke checks, installers, checksums and build metadata | Always Windows **and** macOS |

Source checks run once on Ubuntu without installing application dependencies. Platform tests run on the actual Windows/macOS runners, with business areas shown as separate steps. A failing test group does not hide results from subsequent groups; the job remains failed. Failed or skipped validation prevents candidate packaging. Fast builds do not claim full validation.

Concurrency is separated by branch, mode and target. New fast/validation runs supersede older matching runs. Candidate runs are queued rather than cancelled by another candidate, and fast builds cannot cancel candidates. Jobs have explicit timeouts; matrix failures do not cancel the other OS. Actions are pinned to immutable commit hashes; credentials are not persisted in checkout and repository permissions are read-only.

## Build caching and artifacts

The backend cache is keyed by OS, architecture, Python version and backend/UI/build-input hashes. A cache hit skips PyInstaller installation/compilation; the packaged-backend smoke test **always runs**, including on cache hits. A backend/UI/build-input change invalidates that cache. npm, pip, Electron and installer-tool downloads are also cached. A first build or changed source still requires compilation.

Test reports and available build diagnostics are retained for seven days, including failed validation results. Successful installer artifacts include:

- Windows `.exe` or macOS `.dmg`.
- `SHA256SUMS.txt` covering the installer and metadata.
- `build-info.json` recording version, commit, platform/architecture, tool versions, validation mode and run identity.

Artifacts are distinguished by mode, OS, architecture, run number and attempt. Fast installers are retained for seven days; candidate installers for 30 days. Checksums identify file contents; they do not replace code signing. Installers remain unsigned. No workflow publishes or deploys releases, and build commands use `--publish never` with publishing disabled in package.json.

## Packaging changes and production acceptance

On each affected target OS:

```sh
python -m pip install -r scripts/requirements-build.txt
python scripts/build_backend.py
python scripts/smoke_backend.py
```

The smoke check verifies startup, HTTP assets, saving data, restart persistence and process/log cleanup. PyInstaller uses onedir output in `backend-dist/ledgerly-backend/`, copied by Electron to `resources/backend/`. This avoids the extra service process of onefile builds that could survive launcher termination and lock Windows files.

Then build and launch the actual target installer and verify shutdown, printer/scanner behaviour and representative business workflows. Linux checks cannot certify either desktop target. A candidate workflow passing is a validation milestone, not proof that all pharmacy features, statutory requirements, signed distribution or production acceptance are complete.

## Workflow-only changes

Run actionlint, inspect job dependencies/mode conditions/cache keys, and exercise changed CI tooling, including failure paths. Application tests need not be rerun for documentation/YAML-only edits. When changing the grouping runner, run every group and verify failed/skipped tests cannot produce a passing report. When changing installer metadata, independently verify the checksums and missing-output rejection.
