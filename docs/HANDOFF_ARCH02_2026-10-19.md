# BASIS — handoff ARCH-02, 2026-10-19

Resume update: the user subsequently authorized continuing and external operator steps. Current verification and the single completion command are in [ARCH-02-VERIFICATION.md](architecture/ARCH-02-VERIFICATION.md). The stop instruction and partial test counts below describe the earlier handoff; the current combined SQLite suite has since passed (124 tests, three PostgreSQL skips). Docker and Git completion remain pending external execution.

## Stop requested

The user requested a handoff and to stop while they leave the session and repair the environment. Preserve all work. Do not continue implementation/tests, start infrastructure, commit or begin ARCH-03 in this session.

Workspace: `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app`.
Branch `main`, HEAD `3fd8978`, preceded by `21a8ab3`; baseline `08dcd02`.
ARCH-01 is integrated through those two architecture commits. Its missing tests/inventories/docs were confirmed present in 3fd8978. Do not ask the user to repeat ARCH-01.

## Tracking and user work

Project P-MAM-12; epic MAM-821. ARCH-01/MAM-822 Done after integration/readback. ARCH-02/MAM-823 In Progress, local implementation without commit/integration. ARCH-03…10/MAM-824…831 remain Backlog with serial dependencies. The 31 open functional issues remain blocked by the epic; four historical Done preserved.

Preserve `seed.py` (pre-existing 168 additions/56 removals) and `manage.py` (pre-existing mode change only). Neither was changed/staged/committed by this task. Do not include either in architecture commits. No reset, stash, clean, force push, ACL changes or alternate index/repository to bypass restrictions.

Git status may show unchanged files as modified because the sandbox cannot refresh the index. A byte comparison against HEAD confirmed untouched tracked basis files are identical. Inspect actual diff/blob contents. Preserve legacy training/views.py CRLF; avoid repository-wide normalization.

## Local ARCH-02 implementation

- `basis/modules/training/domain/execution.py`: immutable session/prescription/block/set/interval state; enumerated metric names and Decimal/text values; owner/revision/completed guards and prescription copying.
- `basis/modules/training/application/execution.py`: StartSession, ReadSession, RecordSession, FinishSession, SessionMutation; specific repository/authorization/ID ports, injected clock and explicit-commit UoW. Account lock before session lock on record. Deferred typed changes source preserves conflict precedence before malformed payload decoding.
- `basis/modules/training/adapters/django.py`: existing ORM/tables/model validation; transactional child replacement; rollback without commit, on exceptions, and across nested transactions.
- `basis/modules/training/adapters/wire.py`: compatible JSON conversion, Decimal and None/zero distinctions; ignore client block IDs/order on writes as before; preserve stored IDs/order on reads.
- `basis/bootstrap/training.py`: explicit composition and temporary compatibility entry points.
- `basis/modules/training/public.py`: explicit exports.
- `training/services.py`: start/snapshot/record delegate execution rules. Canonical hash, account lock, receipts and outer transaction remain until ARCH-08; session and receipt still atomic together.
- `training/views.py`: existing result forms reuse migrated revision/completed guard; routes/form behavior retained.
- Pure tests: `tests_architecture/test_execution.py`; shared repository/UoW contract: `tests_architecture/repository_contract.py`; real tests: `basis/modules/training/adapters/tests.py`.
- CI includes adapter test label. `mypy-django.ini` has six explicit pending-legacy follow_imports=silent frontiers: training.models/domain/access/services, daily_trainning_app.models/strength_metrics. Symbols are analyzed; legacy bodies are NOT certified migrated. No global ignore/Any exemption. `scripts/architecture_check.py` rejects wildcard/global/frontier entries outside legacy-pending.json. Remove entries as their stages migrate them.

Plan: `docs/architecture/ARCH-02-PLAN.md`. No schema change, paid provider call, production deployment or successor work.

## Verification and interrupted candidate

VERIFIED before the final two compatibility tests:

- Pure suite: 25 pass (15 architecture + six execution + four shared fake repository/UoW tests), without Django/DB/network.
- Adapter suite: 11 pass on temporary SQLite. Includes the same four repository/UoW contracts, owner checks, zero/absence, completion, invalid-child rollback, outer rollback when receipt fails, retry/409 and nonconsecutive stored block order.
- Original suite after initial legacy wiring: 111 discovered, 108 pass, three PostgreSQL concurrency tests skipped. Subsequent refinements require final combined rerun.
- Strict mypy: core 40 files and Django 47 files, zero errors; last successful checks include deferred conversion.
- AST/eight Import Linter contracts passed after initial wiring; Ruff passed. Final aggregate gates still pending.

The last command was deliberately interrupted. Its edits DID execute: two more adapter tests exist (stale invalid body returns 409 before decoding; temporary offline block IDs/order ignored on writes), and the file was formatted. Do not claim the interrupted command's tests/checks passed. Expected final adapter count: 13; combined Django count: 124. These counts are expectations, not evidence.

NOT RUN/NOT VERIFIED: final aggregate regression/checks on the stopped tree; PostgreSQL concurrency; browser/offline device flows; remote CI; ARCH-02 commit/integration. Keep MAM-823/epic open.

## Environment blockers

1. Git ref writes remain denied even with escalation. User external PowerShell successfully integrated ARCH-01. Do not repeatedly retry blocked transport/permissions.
2. PostgreSQL 18.4 exists via Scoop (`initdb`, `pg_ctl`, `psql`). Temporary cluster ONLY at `.cache/arch02-pgdata`, role basis_arch02, port 55439. No original database used.
3. Sandbox startup fails restricted-token errors 87/3; escalated execution fails `helper_unknown_error: setup refresh had errors`.
4. User ran `.cache/Verify-Arch02-Postgres.ps1` externally: server/CREATE DATABASE worked; server stopped in finally. PowerShell ErrorActionPreference=Stop plus native stderr redirection treated normal Django `Creating test database...` as NativeCommandError. This is a verification-HARNESS failure, not proof tests failed/passed. Log is empty and no receipt exists. Script hardcodes old 122-test expectation: DO NOT reuse unchanged.
5. User explicitly prefers Docker next. Docker CLI 29.5.3 exists. Sandbox cannot access Docker config/engine named pipe; escalation fails helper setup. A Docker verification script was PLANNED but NOT CREATED. Next session must use actual process ExitCode and separate stdout/stderr (e.g. Start-Process -WindowStyle Hidden -Wait with RedirectStandardOutput/RedirectStandardError, correct quoting), rather than treating stderr as failure. Prefer Docker after environment repair.
6. At handoff inspection: no temporary postmaster.pid; no postgres/pg_ctl processes; no Docker container created by task. Do not stop unrelated processes.
7. While writing this handoff, exec_command also began failing CreateProcessAsUserW with Access denied (Windows error 5). This compounds the existing environment blocker; no product failure is inferred.

## Resume

1. Read this handoff, project instructions, plan, current diff and live Linear. Recheck HEAD and preserve seed/manage. Repair supported session permissions without modifying managed ACLs or bypassing boundaries.
2. Review deferred conversion and two newest compatibility tests. Check generated Spanish strings for encoding damage. Existing roadmap already contains some encoding damage; do not silently broaden into unrelated cleanup.
3. Run the local gates below with a temporary database. Never use the original DB.
4. Use Docker PostgreSQL 18.4 in a dedicated temporary container/database on loopback-only unused port, without a production volume. Capture exit code/logs, run all expected 124 Django tests with zero concurrency skips, bind evidence to source hashes, stop only owned test infrastructure.
5. Update docs/ROADMAP/Linear to actual results. Create arch/02-execution, commit only task files, inspect staged diff, integrate/verify main. Only then close ARCH-02 and start ARCH-03. If Git stays blocked, leave In Progress and exact external integration instructions.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'basis_trainning_app.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
.venv-win/Scripts/python.exe scripts/architecture_check.py
.venv-win/Scripts/python.exe -m unittest discover -s tests_architecture
.venv-win/Scripts/python.exe -m mypy --config-file mypy-core.ini
.venv-win/Scripts/python.exe -m mypy --config-file mypy-django.ini
.venv-win/Scripts/lint-imports.exe --no-cache
.venv-win/Scripts/ruff.exe check .
.venv-win/Scripts/python.exe manage.py check
.venv-win/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv-win/Scripts/python.exe manage.py test training.tests basis.modules.training.adapters.tests --noinput
```

All implementation files remain in the working tree. No ARCH-02 archive/manifest/commit was produced; the failed long exec write did not create its proposed archive. Do not infer recoverable artifacts that are not present.
