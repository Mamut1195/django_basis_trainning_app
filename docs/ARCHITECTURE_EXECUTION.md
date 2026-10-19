# Goal

Complete the serial migration to a strict typed hexagonal Django/PostgreSQL monolith before functional acceptance. The final architecture, rather than legacy persistence structure, is authoritative. No predefined-program feature is included.

# Context

ARCH-01 through ARCH-05 are integrated. Current main: e3ffcf66deb3e8138dfa57d6773a400c3a87426e. ARCH-05 independent readback verified158 PostgreSQL tests/no skips, stopped owned container,39 manifest paths and normalized tree/HEAD source hashes; run5979be3c5b6447c6bbeee21f4e6cd0a7. MAM-826 Done. ARCH-06/MAM-827 In Progress with two implementers and primary orchestration. See architecture/ARCH-06-PLAN.md.

Original baseline08dcd02 discovered111 tests. Unrelated user changes remain seed.py168 additions/56 deletions and manage.py mode only; exclude them from architecture commits. No repository AGENTS.md was found; supplied global agreements apply.

# Constraints

ADR-002 supersedes the original final-schema compatibility rule: no production exists, and the user authorizes reorganizing apps/models/tables/migrations to achieve the proposed architecture. ARCH-09 must remove daily_trainning_app, place ORM models in final module persistence adapters and remove temporary bridges. ARCH-10 verifies the final structure from an empty temporary database. Keep stage06 schema unchanged only to bound its delivery. Preserve unrelated user work and do not unnecessarily delete local data.

Preserve business behavior, owner authorization, CSRF, URLs/JSON and offline operations during extraction. No live providers, paid calls, SMTP or production. Do not modify ACLs, bypass execution policy, use alternate Git indexes/checkouts, stash/reset/clean or overwrite unrelated work. Git/Docker completion uses the external operator script when session access is blocked.

# Affected areas

ARCH-06: billing domain/application and specific ports, Django repositories/receipts/authorization, public athlete profile lookup, Polar and webhook adapters, explicit billing bootstrap, legacy access/billing/web/command bridges. Primary owns public export integration, strict scope/inventory, CI, documentation and operator evidence. Final schema/app relocation belongs to ARCH-09.

# Implementation steps

1. Completed ARCH-01..05 serial gates; preserve their evidence and Done states.
2. Core executor implements commercial rules, access, transactional cases/repositories and pure/shared persistence tests. Polar/web executor implements typed provider transport, signature decoding and legacy HTTP/command binding. They agree contracts directly; no overlapping file ownership or extra executors.
3. Primary reviews contracts and behavior, runs combined architecture/type/lint/Django/regression checks, and prepares exact manifest plus external scripts/Complete-Arch06.ps1. Core tests must run without Django or network; provider tests use fakes/MockTransport only.
4. External verification repeats gates on temporary Docker PostgreSQL18.4, requires every test/no skips, stops owned container, binds source hashes and commits only manifest files on a dedicated branch before fast-forwarding main. No push.
5. Independently read back SHA, logs, receipt, committed scope and source hashes. Mark MAM-827 Done only then; ARCH-07 waits for that gate. Continue ARCH-07 coach, ARCH-08 sync, ARCH-09 final legacy removal, ARCH-10 full acceptance in order.

# Required skills

task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates and verifies; two authorized agents implement.

# Validation

Per stage record VERIFIED / FAILED / NOT RUN, actual exit codes and log paths. Required: strict core/Django typing without broad exceptions, AST/public/inventory and Import Linter boundaries including type-only imports, Ruff, pure tests, common fake/Django contracts, Django system check and expected migrations, complete temporary PostgreSQL regression including concurrency. Verify final ARCH-06 counts from actual logs before publishing scripts/receipt.

# Risks

For billing, retain pending reconciliation after provider failure, inclusive-start/exclusive-end access, first-seen trial history, cached checkout, server-owned product parameters and bounded provider request while holding the existing billing lock. Legacy training.billing.polar_request patches must still prevent network in old tests. Do not replace webhook durable phases with a single transaction that rolls back the pending flag. Session restrictions are infrastructure limits, not passing evidence. Remote CI/live providers remain unverified unless independently executed.
