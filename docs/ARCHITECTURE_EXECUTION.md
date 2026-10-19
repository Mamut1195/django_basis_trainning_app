# Goal

Migrate BASIS serially to a strict typed hexagonal Django/PostgreSQL monolith, preserving data and behavior. Architecture precedes functional acceptance. No predefined-program feature is included.

# Context

2026-10-19: ARCH-01..04 integrated and verified; main/20cc32ca25a905cbb20a3e6707d92ae74797c573, PostgreSQL148 tests/no skips with receipt/log/HEAD readback. MAM-825 Done. ARCH-05/MAM-826 local candidate built by two executors under primary orchestration, awaiting external PostgreSQL/main. ARCH-06 has not started. [Current handoff](HANDOFF_ARCH05_2026-10-19.md).

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

## Current stage - ARCH-05

Two authorized executors finished disjoint metric and progress/trekking scopes; primary merged contracts, strict scope, docs and evidence. Integrated61 pure tests, mypy65/87, eight import contracts, AST, Ruff, Django/no migrations and158 SQLite (three PostgreSQL-only skips) pass. Differential comparison against exact HEAD baseline checks2028 strength/sport/pace/load cases with zero differences. See ARCH-05 plan/verification/handoff. External scripts/Complete-Arch05.ps1 must verify158 PostgreSQL/no skips and integrate the commit before MAM-826 Done/ARCH-06. Prior stage candidate notes below/above are historical; original user work is preserved.
