# Goal

Migrate BASIS serially to a strict typed hexagonal Django/PostgreSQL monolith, preserving data and behavior. Architecture precedes functional acceptance. No predefined-program feature is included.

# Context

2026-10-19: ARCH-01 is integrated at 3fd8978; ARCH-02 at main/2f3c95ebefedfcc082cdc074aaafefd4efc1aaa5, independently checked with PostgreSQL18.4/124 tests/zero skips and receipt/HEAD hashes. MAM-823 is Done. ARCH-03/MAM-824 is In Progress with a local candidate; ARCH-04 has not started. See [current handoff](HANDOFF_ARCH03_2026-10-19.md).

The original baseline is 08dcd02 with111 tests (108 SQLite passes, three PostgreSQL-only races). Existing user changes remain seed.py168 additions/56 deletions and manage.py mode only. No repository AGENTS.md was found; supplied global working agreements apply.

# Constraints

Preserve tables, app labels, migrations, URLs/JSON, owner authorization, CSRF, IndexedDB queues and history. No production, paid calls, live SMTP or functional changes. Keep seed.py/manage.py outside architecture commits. Do not modify ACLs, bypass execution policy or use alternate Git indexes/checkouts; no stash/reset/clean.

# Affected areas

basis/modules/{accounts,athletes,catalog} typed domain/application/adapters and public contracts; narrow athlete/billing enrollment ports; explicit bootstrap composition/UoW. Existing forms, views, serializers, model hooks and the explicit linking command delegate through compatibility bindings. Legacy calculations and generic read adapters remain for ARCH-05/09, with all six exact legacy typing frontiers documented rather than silencing migrated code.

# Implementation steps

1. Completed: architecture epic and ten serial stages, blockers for31 open functional tickets preserving four Done tickets; contracts, controls and baseline (ARCH-01).
2. Completed: session execution, repository/UoW, web/offline delegation and PostgreSQL integration (ARCH-02).
3. Current: ARCH-03 identity/profile/catalog candidate implemented; local gates pass. Review [plan](architecture/ARCH-03-PLAN.md) and [evidence](architecture/ARCH-03-VERIFICATION.md).
4. Operator executes scripts/Complete-Arch03.ps1: native capture self-test, repeated checks, temporary Docker PostgreSQL139 tests with zero skips, stopped container, explicit manifest/source hashes, dedicated branch and fast-forward main. No push.
5. Independently check returned SHA, logs, receipt, source/HEAD hashes and committed completeness. Only then mark MAM-824 Done and begin ARCH-04. Continue each later stage in order with its own reviewed commit and integration evidence.

# Required skills

task-planning, safe-git-workflow, verify-before-complete.

# Validation

VERIFIED local ARCH-03:39 pure tests without Django/DB/network, mypy core52/Django68 files, eight Import Linter contracts, AST/inventory, Ruff, Django check/no migrations, SQLite139 with three PostgreSQL-only skips, PowerShell parser zero syntax errors. Shared fake/Django identity transaction contract and15 new integration tests are included. Logs/receipt: .cache/arch03-local. Every claim uses VERIFIED / FAILED / NOT RUN.

# Risks

NOT RUN: candidate PostgreSQL139 without skips, native process-capture self-test, main integration and remote CI. Child PowerShell here refused scripts by execution policy; no bypass attempted. Git writes/Docker access require the user's external session. SQLite does not establish concurrency correctness. Preserve failures and logs, diagnose the exact gate, and do not claim closure from local-only checks.
