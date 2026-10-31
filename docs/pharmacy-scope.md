# Pharmacy scope and evidence register

This is an incomplete development application. No claim of Marg parity or pharmacy readiness is made. Marg is a workflow reference; proprietary implementation and visual assets are not used.

## Evidence
- https://margcompusoft.com/marg-features.html — edition feature comparison.
- https://care.margcompusoft.com/margerp/sale-return/4244/1/crc32 — customer return entry includes party, date, item, batch and quantity.
- https://care.margcompusoft.com/margerp/purchase-return/165216/1/what-is-the-process-of-purchase-return-bulk-issue-in-marg-software — supplier return selection and breakage/expiry workflows.
- https://tutorial.margcompusoft.com/tutorial/189 — restrictions for scheduled and narcotic items.
- Local REA artifact evidence identifies the executable; configuration labels indicate options, not verified runtime behavior.

## Acceptance backlog
| Workflow | Required behavior | Current state |
|---|---|---|
| Product master | Generic/brand, strength, manufacturer, HSN, pack/loose units, barcode, drug classification | Name/batch only; incomplete |
| Batch master | MRP, cost, expiry, manufacture date, supplier provenance, audit of corrections | Batch/expiry, per-unit MRP, price tax basis and pack size implemented; provenance and correction audit pending |
| Billing | Search/barcode, batch selection, expiry block, stock block, pack conversion, discounts, tax-inclusive MRP, payments, hold/resume, keyboard entry | Inclusive/exclusive pricing, MRP cap, pack conversion, server quote and sale retry protection implemented; remaining controls pending |
| Purchasing | Supplier invoice, multiple lines, free quantities, schemes, tax and landed cost, duplicate invoice prevention | Single-line receipt only |
| Customer return | Original invoice linkage, remaining quantity, original rates, credit allocation, inspection/quarantine | Quantity and amount checks implemented; quarantine and inspection recorded, role enforcement pending |
| Supplier return | Original receipt linkage, quantity cap, available stock, credit-note settlement | Quantity and amount checks implemented; settlement missing |
| Stock | Batch ledger, FEFO suggestion, quarantine, stocktake, recall, adjustments with reason and approval | Basic movement register only |
| Restricted items | Patient/prescriber records, schedule rules, permissions and prescribed registers | Not implemented; must verify applicable requirements |
| Accounting | Balanced double-entry postings, customer/supplier ledgers, cash/bank reconciliation, financial-year locks | New invoices/returns post balanced entries; basic trial balance available. Tax classification, payments, period locks and valuation pending |
| Tax | CGST/SGST/IGST, place of supply, HSN, credit notes, applicable e-invoice/e-way workflows | Not implemented; basic tax arithmetic only |
| Documents | Correct business identity, drug licences, serials, thermal/A4 printers, reprints | Not implemented |
| Recovery | Scheduled backups, verified restore, migrations, audit history | Manual integrity-checked backup implemented; restore and scheduling pending |
| Desktop | Signed Windows/macOS installers, offline operation, update rollback, printer/scanner tests | Shell and packaging scripts only; unverified |

## UI acceptance
Use local system fonts, 4px spacing increments, aligned labels and tabular amounts. Billing must be operable with a keyboard without a mouse. Preserve drafts across navigation. Make patient, product, batch and quantity unambiguous. Errors must point to the affected field. Do not show nonfunctional actions. Test 100%, 125%, 150% scaling and common counter monitor sizes on each target OS.

## Release verification boundary

The repository now includes a Windows/macOS CI definition that tests database workflows, packages the Python backend, checks startup/HTTP assets/persistence across restart, and builds unsigned development installers. This workflow has not run: the workspace has no connected deployment of this repository to a CI runner. No executable artifact, code-signing result, notarization result or supported-OS UI validation is claimed. Production qualification additionally needs pharmacy workflow acceptance, printer/scanner testing, current jurisdictional tax/drug-record review, restore drills, and a migration reconciliation dataset.


Company/year configuration, classified standalone ledger creation, balanced opening entry and forward-only period locks are implemented for one company per database. Invoice parties still use text and are not yet linked to those ledger IDs. Multi-company operation, financial-year rollover and billwise opening allocation remain outstanding. Do not infer full ledger-master integration from the setup screen.
