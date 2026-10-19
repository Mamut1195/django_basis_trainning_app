# ARCH-04 verification - 2026-10-19

Candidate on main/ddcf178, not committed. MAM-825 In Progress; ARCH-05 not started.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED | unittest discover:48 tests without Django/DB/network |
| Core strict typing | VERIFIED | mypy-core.ini:56 files, no plugin |
| Django strict typing | VERIFIED | mypy-django.ini:74 files |
| Architecture/public/inventory | VERIFIED | AST checker including type-only imports |
| Import Linter | VERIFIED | eight kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django | VERIFIED | check succeeds |
| Schema | VERIFIED | makemigrations --check --dry-run: no changes |
| SQLite regression | VERIFIED |148 discovered,145 pass; three PostgreSQL-only skips |
| Diff hygiene | VERIFIED | Reviewed26-file manifest; Git diff check with cr-at-eol passes |
| PowerShell syntax | VERIFIED | Native parser reports zero errors for both scripts |
| Native capture self-test / PostgreSQL | NOT RUN | External operator must require148 tests, zero skips and stop its own Docker container |
| Main integration / remote CI | NOT RUN | Explicit external commit and independent readback required |
| Production / LIVE providers | NOT RUN | User confirms no production; no infrastructure activation is part of this stage |

The same planning repository contract runs against memory and Django: typed prescription creation without fabricated results, rollback-only preview and revision preserving original history while excluding past/executed schedules. Nine new Django tests include detailed strength prescriptions/frozen measured RM, foreign RM partial-write rollback, actual-zero rejection, owner-scoped calendar/revision, source mutation isolation and manual forms/reschedule conflicts. Existing139 scenarios remain in regression.

Plan source is separate from PlanDefinition; no program feature is added. AI JSON count/year bounds remain in its adapter; manual empty drafts remain valid. Existing validation hooks enforce fields/FKs using the same pure business rules. Six exact typing frontiers remain pending, with no new silent import or Any exception. Existing coach proposal acceptance policy stays in a thin legacy bridge until ARCH-07. No migration/table/app-label/URL/JSON changes.

Original seed.py168 additions/56 deletions and manage.py mode are preserved outside the manifest. Operator command scripts/Complete-Arch04.ps1 repeats checks, performs the stderr/nonzero-exit capture self-test, runs temporary Docker PostgreSQL18.4, then creates a dedicated branch and fast-forwards main with only the explicit reviewed files. It writes ARCH-04-RESULT.json and .cache/arch04-integration.json and does not push. Do not mark Done before actual logs, hashes and main are checked.

Final local check run: all nine checks VERIFIED in .cache/arch04-local/receipt.json, with separate stdout/stderr logs and actual exit codes. Pure log confirms48 tests/OK; SQLite log confirms148 tests/OK(skipped=3). Receipt binds normalized source hashes to the26-file explicit manifest. Only ARCH-04-RESULT.json is intentionally absent until the external PostgreSQL run succeeds. No new follow_imports override was added. ARCH-03 Done and ARCH-04 In Progress were read back from Linear.

## Final integration readback - 2026-10-19

VERIFIED main/20cc32ca25a905cbb20a3e6707d92ae74797c573, run92a87ed71d6947898ade23e1be0a24cd. Actual PostgreSQL logs show148 tests and standalone OK, no omissions. Receipt checks all exit0, container_stopped true. All normalized source hashes match working tree and HEAD, and all26 manifest files exist in the commit. MAM-825 marked Done only after independent readback; MAM-826 started with user-authorized moderate parallel delegation. Earlier candidate/pending notes are historical.
