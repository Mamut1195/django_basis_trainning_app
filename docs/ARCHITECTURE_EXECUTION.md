# Goal

Complete the serial migration to a strict typed hexagonal Django/PostgreSQL monolith before functional acceptance. The final architecture, rather than legacy persistence structure, is authoritative. No predefined-program feature is included.

# Context

ARCH-01 through ARCH-06 are integrated. Current main: c5cc0c17d7f3070c81950a89ea8ccbdcdde696e6. ARCH-06 independent readback verified180 PostgreSQL tests/no skips, stopped owned container,43 manifest paths and normalized tree/HEAD source hashes; run136ec5dcf05f42d5b705540d62a6b9ad. MAM-827 Done. ARCH-07/MAM-828 In Progress with two implementers and primary orchestration. See architecture/ARCH-07-PLAN.md.

Original baseline08dcd02 discovered111 tests. Unrelated user changes remain seed.py168 additions/56 deletions and manage.py mode only; exclude them from architecture commits. No repository AGENTS.md was found; supplied global agreements apply.

# Constraints

ADR-002 supersedes the original final-schema compatibility rule: no production exists, and the user authorizes reorganizing apps/models/tables/migrations to achieve the proposed architecture. ARCH-09 must remove daily_trainning_app, place ORM models in final module persistence adapters and remove temporary bridges. ARCH-10 verifies the final structure from an empty temporary database. Keep stage07 schema unchanged only to bound its delivery. Preserve unrelated user work and do not unnecessarily delete local data.

Preserve business behavior, owner authorization, CSRF, URLs/JSON and offline operations during extraction. No live providers, paid calls, SMTP or production. Do not modify ACLs, bypass execution policy, use alternate Git indexes/checkouts, stash/reset/clean or overwrite unrelated work. Git/Docker completion uses the external operator script when session access is blocked.

# Affected areas

ARCH-07: coach context/prompt/proposal and budget/job domain/application, typed ports, Django persistence and DeepSeek adapters, narrow public account locks/billing entitlement/athlete/catalog/training context and common planning gateway, explicit bootstrap, legacy ai/proposals/web/worker bindings. Primary owns public export integration, strict scope/inventory, CI, documentation and operator evidence. Final app/schema relocation belongs to ARCH-09.

# Implementation steps

1. Completed ARCH-01..06 serial gates; preserve their evidence and Done states.
2. Jobs executor implements cost/quotas, enqueue/settle/claim/quarantine, lock ports and transaction/concurrency tests. Context/provider/proposal executor implements typed context projections, frozen JSON/HTTP adapters, proposal lifecycle using common planning and legacy web/command bindings. They agree contracts directly; no overlapping file ownership or extra executors.
3. Primary reviews contracts and behavior, runs combined architecture/type/lint/Django/regression checks, and prepares exact manifest plus external scripts/Complete-Arch07.ps1. Core tests must run without Django or network; provider tests use fakes/MockTransport only.
4. External verification repeats gates on temporary Docker PostgreSQL18.4, requires every test/no skips, stops owned container, binds source hashes and commits only manifest files on a dedicated branch before fast-forwarding main. No push.
5. Independently read back SHA, logs, receipt, committed scope and source hashes. Mark MAM-828 Done only then; ARCH-08 waits for that gate. Continue ARCH-08 sync, ARCH-09 final legacy removal, ARCH-10 full acceptance in order.

# Required skills

task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates and verifies; two authorized agents implement.

# Validation

Per stage record VERIFIED / FAILED / NOT RUN, actual exit codes and log paths. Required: strict core/Django typing without broad exceptions, AST/public/inventory and Import Linter boundaries including type-only imports, Ruff, pure tests, common fake/Django contracts, Django system check and expected migrations, complete temporary PostgreSQL regression including concurrency. Verify final ARCH-07 counts from actual logs before publishing scripts/receipt.

# Risks

For coach, preserve fund/account/billing/usage enqueue lock order and original fund/account/job/usage settlement locks. Keep reservations for ambiguous timeout/crash, per-account lifetime trial/monthly global fund, rollover invalidation and one provider call without retry. Preserve exact frozen context/message JSON byte size, partial token capture on malformed responses and raw proposal JSON on edit/accept. Original training.ai.httpx.Client patch seam must remain effective. Provider contracts use MockTransport only. Independent legacy differential now verifies40 context/request/settlement cases without differences. Session restrictions are infrastructure limits, not passing evidence. Remote CI/live providers remain unverified unless independently executed.

## ARCH-07 candidate gate

Two implementers finished; primary independently verified91 pure tests, strict85/129 files, eight import contracts, AST/Ruff/Django/no migrations/static,199 SQLite tests with four PostgreSQL-only skips,40 differential cases/zero differences,53-file completeness and stable source hashes. The external scripts/Complete-Arch07.ps1 now repeat gates on Docker PostgreSQL18.4 before explicit commit/main integration. See HANDOFF_ARCH07_2026-10-19.md. MAM-828 stays In Progress and ARCH-08 waits for main/receipt/log/hash readback.
