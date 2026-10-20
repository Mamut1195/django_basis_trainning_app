# ARCH-09 remediation: review and acceptance

Status: candidate prepared on main337f12d8d6b78d52c77c3e7e821ab2af1351cdc8; NOT integrated. MAM-830 and MAM-831 remain In Progress. The first ARCH-09 commit is a verified structural delivery, not proof of the completed architecture. Its 224-test PostgreSQL receipt remains historical and unchanged.

## Implemented correction

- config/settings.py, test_settings.py, urls.py, asgi.py and wsgi.py are active. No compatibility configuration package remains. The user removed both old cache-only directories; independent Test-Path returned False for basis_trainning_app and daily_trainning_app.
- All seven business modules own domain/application/adapters/public contracts, persistence models and initial migrations. Cross-module reads use typed public projections; bootstrap alone connects implementations.
- Manual training writes now use typed commands, pure guards and concrete repositories/UoW. Planning authorization, ownership, cycle/schedule validation and latest-version checks run before persistence. Athlete RM/workout/preference policy works with permissive fakes. Staff/admin single, inline and bulk writes enter concrete cases; protected bulk deletion rolls back atomically. Billing read provisioning and reconciliation failure marking enter cases.
- Workout metric orchestration belongs to athletes.application.workouts; immutable local domain DTOs prevent an indirect domain/application cycle. Eight Import Linter contracts remain active, including type-only dependencies.
- Original regression tests moved to tests/regression and entered strict scope. All111 original scenarios and assertion-call counts are preserved per file. Runtime, config, public contracts and migrated tools have no global missing-import exclusions.
- Existing logout defect was recorded in MAM-632 before correction. Logout now awaits a real CSRF POST acknowledgement before local purge, cross-tab notification and navigation; errors retain local pending data. It is the only documented functional correction needed for valid browser acceptance.

See ENTRYPOINTS.md for reviewed chains and ARCH-10-AUDIT.md for findings, fixes and accepted framework/development-fixture boundaries. Predefined programs remain future work; manual and AI plan creation share the typed PlanDefinition contract.

## Evidence before external PostgreSQL/integration

VERIFIED by implementation audit:147 pure tests;240 Django SQLite tests with five PostgreSQL-only skips; strict mypy106 core/267 full files;8 import contracts; AST/public/layout/inventory; Ruff; Django check; no migration drift. Operational runner tests are additional and final aggregate counts are recorded below when frozen.

VERIFIED independently: all344 raw source hashes and receipt hash of final Edge run9f1edf3e2e91409c9189102b6c327922 match. Fourteen real checks passed, including offline reload, fractional persisted results, ordered two-operation outbox, completion/revision3, historical replay,409,CSRF403, actual logout POST/other tab, local purge and cross-account404/403. Browser and owned server closed. Zero JS errors and external responses.17 exact-host Kaspersky injected scripts were aborted and explicitly classified; every other external request remains a failure. No AV/system configuration changed.

Tracked browser proof: ARCH-10-BROWSER-RESULT.json. Original detailed logs/screenshots remain under .cache/browser-acceptance/9f1edf3e2e91409c9189102b6c327922. Regression proof: ARCH-10-REGRESSION-PARITY.json.

VERIFIED whitespace preflight for106 changed/new candidate files before final runner tests/docs were added, including untracked files. It exposed a harmless Git CRLF-warning handling bug, fixed through command-scoped core.autocrlf=false for no-index checks; actual whitespace errors still fail. The complete runner repeats preflight on final scope before expensive services.

## External operation

Use scripts/Complete-Arch09-Remediation.ps1. The old Complete-Arch09 and earlier stage scripts are historical and refer to retired paths. The new script checks the explicit remediation manifest, all runtime/tests/config/assets/templates and changed sources, then fresh owned loopback Docker PostgreSQL18.4, zero skipped tests,14 real browser checks and stopped processes/container. It captures native stdout/stderr and exit codes separately. Only reviewed paths are staged; seed.py stays excluded, manage.py content is included while its original index executable mode100755 is preserved. No push.

If Git fails after verification, retain index/branch/evidence. Explicit -Resume requires the original successful receipt, unchanged source/protected hashes, exact logs,14 browser checks and the reviewed base/candidate ancestry. It continues Git without rerunning paid/unnecessary services or weakening hashes. It never resets, stashes, discards, force-merges or changes Git trust globally.

NOT RUN at candidate review: PostgreSQL on these bytes, Git integration/readback, remote CI, physical-device and live-provider acceptance. The first two are required before closing architecture tickets. No original database, production, SMTP or paid provider is used.

## Final independent local aggregate

VERIFIED:166 pure tests (including19 runner contracts), strict mypy108 core/267 Django files,8 import contracts,AST/layout/inventory,Ruff,Django check,no migration drift,static assets,native argv/stderr/exit handling and240 Django SQLite tests (five PostgreSQL-only skips). Final aggregate captured native exit codes separately; after the last test-only console-capture change,pure/core/Ruff were rerun successfully. Git recovery is simulated unit evidence,not a real commit. See ARCH-09-REMEDIATION-LOCAL-RESULT.json.

The PowerShell wrappers parse successfully; local execution was NOT RUN because the existing session disables PS scripts. No policy was changed. Canonical CLI from PowerShell:

```powershell
& '.\.venv-win\Scripts\python.exe' '.\scripts\arch09_remediation.py' complete
```

If services pass and Git fails,use the same CLI with --resume. External PostgreSQL/browser/commit and independent main readback remain required.
