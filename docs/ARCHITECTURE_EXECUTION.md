# Goal

Complete the serial migration to a strict typed hexagonal Django/PostgreSQL monolith before functional acceptance. The final architecture, rather than legacy persistence structure, is authoritative. No predefined-program feature is included.

# Context

ARCH-01 through ARCH-07 are integrated. Current main:105ac188be24fbd960a1bf6941dbafa3104455ee. ARCH-07 independently verified199 PostgreSQL/no skips, stopped owned container,53 manifest paths and normalized tree/HEAD hashes; run524117c46a6149878edce8c22d124277. MAM-828 Done. ARCH-08/MAM-829 In Progress with two implementers and primary orchestration. See architecture/ARCH-08-PLAN.md.

Original baseline08dcd02 discovered111 tests. Unrelated user changes remain seed.py168 additions/56 deletions and manage.py mode only; exclude them from architecture commits. No repository AGENTS.md was found; supplied global agreements apply.

# Constraints

ADR-002 supersedes the original final-schema compatibility rule: no production exists, and the user authorizes reorganizing apps/models/tables/migrations to achieve the proposed architecture. ARCH-09 must remove daily_trainning_app, place ORM models in final module persistence adapters and remove temporary bridges. ARCH-10 verifies the final structure from an empty temporary database. Keep stage08 schema unchanged only to bound its delivery. Preserve unrelated user work and do not unnecessarily delete local data.

Preserve business behavior, owner authorization, CSRF, URLs/JSON and offline operations during extraction. No live providers, paid calls, SMTP or production. Do not modify ACLs, bypass execution policy, use alternate Git indexes/checkouts, stash/reset/clean or overwrite unrelated work. Git/Docker completion uses the external operator script when session access is blocked.

# Affected areas

ARCH-08: typed synchronization operation/receipt/replay coordinator, deferred source conversion, injected training recorder/snapshot codecs, explicit account/auth/UoW composition, Django receipt persistence, canonical JSON and web adapters, fully typed legacy services facade. Primary owns public IDs/exports, strict scope/inventory/CI, docs/scripts and independent parity verification. Final legacy package/model/app/migration relocation belongs to ARCH-09.

# Implementation steps

1. Completed ARCH-01..07 serial integration gates; preserve evidence and Done states.
2. Core/receipt executor implements pure operation policy, transaction/receipt ports, persistence and fake/real contracts/races. Wire/web executor implements canonical hashing/deferred conversion, historical snapshot codec, HTTP and typed services bindings. Two disjoint implementers; primary orchestrates/reviews/contracts/configuration/evidence only.
3. Freeze and jointly verify core/Django strict types, architecture/public/inventory/import, Ruff, pure tests, Django/no migrations/static and full regression. Compare exact legacy canonical/result/error behavior on a temporary database; keep offline assets/queue schema unchanged.
4. Prepare scripts/Complete-Arch08.ps1 and explicit manifest/counts. External verification repeats gates on an owned temporary Docker PostgreSQL18.4, requires every test/no skips, stops container and records source hashes before a scoped commit and fast-forward main; no push.
5. Read back SHA/logs/receipt/stopped-container/source and HEAD hashes/committed completeness. Only then mark MAM-829 Done and begin ARCH-09 final structure removal. ARCH-10 verifies full acceptance including empty-database migration.

# Required skills

task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates and verifies; two authorized agents implement.

# Validation

Per stage record VERIFIED / FAILED / NOT RUN, actual exit codes and log paths. Required: strict core/Django typing without broad exceptions, AST/public/inventory and Import Linter boundaries including type-only imports, Ruff, pure tests, common fake/Django contracts, Django system check and expected migrations, complete temporary PostgreSQL regression including concurrency. Verify final ARCH-08 counts from actual logs before publishing scripts/receipt.

# Risks

Receipt lookup/replay must precede authorization and late payload/revision/child conversion, while IDs and canonical digest stay before replay under the account lock. Preserve numeric and Unicode JSON hashing, owner scope, stale/completed conflict precedence, cached child IDs/order/Decimal scales and exact web errors. Outer receipt failure must roll back an inner committed execution. Avoid foreign ORM/adapter imports; inject existing training adapters in bootstrap. Remote CI and real-browser/device offline acceptance remain NOT RUN unless independently executed.

## ARCH-08 candidate gate

Two disjoint implementers finished; primary independently verified105 pure tests, strict89/140 files, eight import contracts, AST/Ruff/Django/no migrations/static,218 SQLite tests with five PostgreSQL-only skips,23 differential cases/zero differences,31-file completeness/stable source hashes and native PowerShell syntax. Run scripts/Complete-Arch08.ps1 externally for Docker PostgreSQL218/no skips and explicit scoped main integration. MAM-829 stays In Progress; ARCH-09 waits for SHA/logs/receipt/hash readback. Then remove daily_trainning_app and complete the final architecture under ADR-002.
