# Marg reference investigation

REA skill: reverse-engineer-anything, installed with rea-agents 6.8.0.

## Observed executable facts

- PE32 x86; .NET CLI metadata absent.
- REA import inspection: 4 imported DLLs, 46 imported functions.
- REA resource inspection: 17 resources. Payload contents and runtime behavior are not established.
- Main executable SHA-256: 55488c500463a5b46fcea23e46299a0806319bcd6c42b29716f5177184ef987f.

## Configuration reference

Source SHA-256: 2dcc656d9ad3fd915cc156783fe36a39df09796909fbd2d09653a17b020d9bfb. 2790 records declared; 2790 active labeled records indexed using an independent read-only DBF reader. This is not a REA behavior trace.

| Type | Group | Indexed labels |
|---|---|---|
| CONTROLS | Inventory Setup Body | 380 |
| CONTROLS | Inventory Setup General | 348 |
| CONTROLS | Inventory Setup Header | 267 |
| CONTROLS | General Setup | 243 |
| CONTROLS | Inventory Setup Footer | 215 |
| CONTROLS | Batch Setup | 194 |
| CONTROLS | International Setings | 177 |
| SELF98 | Invoice Format | 168 |
| CONTROLS | VAT Setup | 96 |
| CONTROLS | Calculations | 90 |
| CONTROLS | Manufacturing Setup | 72 |
| POWERS | Advance /General Controls | 56 |
| CONTROLS | Sms Setup | 55 |
| CONTROLS | Krishi Mandi | 51 |
| POWERS | Transaction & Rates | 46 |
| POWERS | Utility | 41 |
| CONTROLS | Bed/Service | 30 |
| POWERS | Accounts | 29 |
| POWERS | Company /Adminstration | 27 |
| CONTROLS | PAYMENT GATEWAY | 25 |
| CONTROLS | E-Mail Setup | 21 |
| CONTROLS | THIRD PARTY SETUPS | 20 |
| POWERS | Masters /Rates & Discount | 20 |
| CONTROLS | Manufacturing ISO Form No. | 19 |
| POWERS | Add-ons /Paid Features | 19 |
| CONTROLS | Traders Cenvat Setup | 18 |
| POWERS | Printing | 18 |
| POWERS | Reports | 18 |
| SNSPGS | Stock & Sales | 8 |
| POWERS | Books | 6 |
| POWERS | Final Reports | 6 |
| CONTROLS | Marg on Net | 2 |
| POWERS | Stocks | 2 |
| POWERS | Daily Reports | 1 |
| POWERS | Marketing / Merge Reports | 1 |
| ###### | Authorisation Required | 1 |

## Limits and next investigations

Ghidra 12.1.4 and a full JDK 21 are now configured and verified by REA. The existing CLI supports the static inspections completed here. A native decompiler alone may inspect only the launcher if business logic resides in another runtime/payload. No complete feature recovery is claimed.

Next trace targets: sale price and tax basis; batch selection; expiry constraints; pack conversion; return linkage; supplier claims; permissions; printing; prescription registers. For each, retain the exact artifact identity, observed input/output, reference location, inferred rule, unresolved cases, and an independently written acceptance test. No source or graphical assets from Marg are incorporated into our application.

## Ghidra trace results

- Official Ghidra 12.1.4 archive verified against published SHA-256 ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db.
- Reproducible launcher: `tools/rea.sh`; provider readiness retained in analysis/ghidra-readiness.json.
- Overview: 50 procedures, 86 Ghidra-defined strings. Counts cover discovered entities, not all business logic.
- Entry function at 0x116d000: static instructions resolve resource/file APIs, obtain resource bytes, write pfdapi584.dll, load it, and resolve/call GettempPathB. Evidence: analysis/ghidra-entry.json. No execution was performed.
- Literal vfp9r.dll trace: four references across functions 0x40118a and 0x401452. Evidence: analysis/ghidra-foxpro-trace.json.
- Function 0x401452 checks VisualFoxProRuntime.9 and runtime file locations, including the Windows system directory. Evidence: analysis/ghidra-runtime-loader.json. This is runtime discovery, not a sales rule.
- Resource GIF/140 is an 81,920-byte PE DLL. Extracted read-only using REA resource offsets; SHA-256 952b802581234d34ba761cc2f8bc594bab7a93bd0fae25d1f5e7f9e9633a99ab. Source offsets and hashes are retained in analysis/derived/resource-140.provenance.json.
- REA export inspection reports GettempPathB at 0xa001fd0, matching the loader's requested export name. Export presence alone does not verify runtime invocation.

Business-rule coverage remains unverified. These traces establish a launcher/runtime structure and must not be presented as recovered accounting, GST or pharmacy workflows.

### Embedded DLL handoff

REA/Ghidra inspected GettempPathB at 0xa001fd0 (analysis/ghidra-embedded-loader.json). The static function constructs initialization strings, reads the module filename and command line, tests an automation/embedding argument, calls several unresolved helpers, checks a vfp9memmgr.dll path, and initializes memory/object state. Protection-related strings are present. Their presence is not a full account of protection or licensing behavior. No patches, target execution, activation bypass, or feature-rule recovery were performed. Next static questions concern the unresolved helper roles; runtime workflow observations remain necessary to validate actual pharmacy behavior.
