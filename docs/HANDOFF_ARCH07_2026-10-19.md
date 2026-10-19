# ARCH-07 coach migration candidate

## State

main/c5cc0c17d7f3070c81950a89ea8ccbdcdde696e6 contains verified ARCH-06:180 PostgreSQL/no skips, stopped container,43 committed files and normalized source/HEAD hashes; run136ec5dcf05f42d5b705540d62a6b9ad. MAM-827 Done. ARCH-07/MAM-828 has a locally verified candidate from two implementers and primary orchestration. No ARCH-07 commit/main integration or PostgreSQL result yet. ARCH-08 must wait.

Local evidence:91 pure tests, mypy85 core/129 Django files, eight import contracts, AST/public/inventory, Ruff, Django/no migrations, static collection and199 SQLite tests (195 pass, four PostgreSQL-only skips). Differential40 cases against exact legacy context/request/settlement show zero differences. Evidence: architecture/ARCH-07-VERIFICATION.md, ARCH-07-PARITY.json and .cache/arch07-local/receipt.json. Provider tests use fakes/MockTransport only; no LIVE or paid requests.

## Next operation

From external PowerShell in this repository:

```powershell
& '.\scripts\Complete-Arch07.ps1'
```

Use `-Port 55441` if loopback55440 is occupied. The script checks base/staged scope, self-tests native process capture, repeats gates on an owned temporary Docker PostgreSQL18.4 database without host volumes, requires199 tests/zero skips and a stopped container, writes the receipt, commits only the53-file manifest and fast-forwards main. It never pushes or activates production. Preserve a failed gate's logs; do not bypass it with ACL/execution-policy changes, alternate indexes, stash/reset/clean or force operations.

Return the final main SHA or error. Independent coordinator readback must compare SHA, actual logs, receipt/integration run, stopped container, complete manifest and normalized worktree/HEAD hashes before MAM-828 Done and ARCH-08. Receipt: docs/architecture/ARCH-07-RESULT.json; logs: .cache/arch07/<run>; integration: .cache/arch07-integration.json. Remote CI, PostgreSQL candidate acceptance, native capture execution and main integration are NOT RUN in this session.

## Scope and preservation

Typed context/proposals/jobs/budgets and their ports live under coach, with public account locking, billing entitlement and athlete/catalog/training projections. DeepSeek is an injected adapter. Legacy httpx.Client patch compatibility, frozen JSON/message byte counts, provider ambiguity, lock order, quota/period behavior and original proposal JSON remain preserved. New PostgreSQL test claims distinct jobs while both worker locks are held. Existing functional tickets MAM-635/MAM-818 record malformed provider-response findings without silent fixes or closure.

Keep original seed.py168 additions/56 deletions and manage.py mode outside the delivery. No schema change was made in this stage. ADR-002 still requires final removal of daily_trainning_app and relocation/reorganization of models/apps/schema/migrations in ARCH-09, followed by empty-database and full behavior acceptance in ARCH-10. Architecture precedes functional acceptance; all35 functional IDs/history and epic blockers remain.
