# Goal

Migrate BASIS serially to a strict typed hexagonal Django/PostgreSQL monolith, preserving data and behavior. Architecture precedes functional acceptance. No predefined-program feature is included.

# Context

2026-10-19: ARCH-01/02/03 integrated and verified; main/ddcf178d6a5c8c4793e3672a95dbf64fdffe2b91, PostgreSQL139 tests/zero skips with receipt/log/HEAD hash readback. MAM-824 Done. ARCH-04/MAM-825 is a locally verified planning candidate awaiting external PostgreSQL/main integration. ARCH-05 has not started. [Current handoff](HANDOFF_ARCH04_2026-10-19.md).

The original baseline is 08dcd02 with111 tests (108 SQLite passes, three PostgreSQL-only races). Existing user changes remain seed.py168 additions/56 deletions and manage.py mode only. No repository AGENTS.md was found; supplied global working agreements apply.

# Constraints

Preserve tables, app labels, migrations, URLs/JSON, owner authorization, CSRF, IndexedDB queues and history. No production, paid calls, live SMTP or functional changes. Keep seed.py/manage.py outside architecture commits. Do not modify ACLs, bypass execution policy or use alternate Git indexes/checkouts; no stash/reset/clean.

# Affected areas

basis/modules/{accounts,athletes,catalog} typed domain/application/adapters and public contracts; narrow athlete/billing enrollment ports; explicit bootstrap composition/UoW. Existing forms, views, serializers, model hooks and the explicit linking command delegate through compatibility bindings. Legacy calculations and generic read adapters remain for ARCH-05/09, with all six exact legacy typing frontiers documented rather than silencing migrated code.

# Implementation steps

1. Completed: architecture epic and ten serial stages, blockers for31 open functional tickets preserving four Done tickets; contracts, controls and baseline (ARCH-01).
2. Completed: session execution, repository/UoW, web/offline delegation and PostgreSQL integration (ARCH-02).
3. Completed: ARCH-03 identity/profile/catalog integrated and independently checked. Current ARCH-04: typed planning/versions candidate, local gates pass. Review [plan](architecture/ARCH-04-PLAN.md) and [evidence](architecture/ARCH-04-VERIFICATION.md).
4. Operator executes scripts/Complete-Arch04.ps1: native capture self-test, repeated checks, temporary Docker PostgreSQL148 tests with zero skips, stopped container, explicit manifest/source hashes, dedicated branch and fast-forward main. No push.
5. Independently check returned SHA, logs, receipt, source/HEAD hashes and committed completeness. Only then mark MAM-825 Done and begin ARCH-05. Continue each later stage in order with its own reviewed commit and integration evidence.

# Required skills

task-planning, safe-git-workflow, verify-before-complete.

# Validation

VERIFIED local ARCH-04:48 pure tests without Django/DB/network, mypy core56/Django74 files, eight Import Linter contracts, AST/inventory, Ruff, Django check/no migrations, SQLite148 with three PostgreSQL-only skips, PowerShell parser zero syntax errors. Shared fake/Django planning contract and9 new integration tests are included. Logs/receipt: .cache/arch04-local. Every claim uses VERIFIED / FAILED / NOT RUN.

# Risks

NOT RUN: candidate PostgreSQL148 without skips, native process-capture self-test, main integration and remote CI. Child PowerShell here refused scripts by execution policy; no bypass attempted. Git writes/Docker access require the user's external session. SQLite does not establish concurrency correctness. Preserve failures and logs, diagnose the exact gate, and do not claim closure from local-only checks.

## Current stage - ARCH-04

ARCH-03 is now integrated at main/ddcf178 and MAM-824 Done, verified139 PostgreSQL/no skips. ARCH-04/MAM-825 local planning implementation is pending external integration. Its plan/verification and current handoff are docs/architecture/ARCH-04-PLAN.md, ARCH-04-VERIFICATION.md and HANDOFF_ARCH04_2026-10-19.md. Local48 pure tests,56/74 typed files, eight import contracts, Ruff, Django/no migrations,148 SQLite with three PostgreSQL-only skips. Follow scripts/Complete-Arch04.ps1 and independently check its returned receipt/SHA before ARCH-05. Earlier ARCH-03 candidate notes are historical. User confirms no production and authorizes autonomous progress; preserve unrelated seed.py/manage.py and session security boundaries.
