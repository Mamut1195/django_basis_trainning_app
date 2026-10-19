# ARCH-02 implementation plan

## Goal
Migrate scheduled-session start, typed state reads, result updates and completion without changing web/offline contracts.

## Context
ARCH-01 is integrated on main through 3fd8978. Only pre-existing seed.py and manage.py changes remain. Existing services own account locking, canonical hashing and receipts; views use those services and ORM forms.

## Constraints
Keep app labels, schema, URLs, JSON fields/Decimal representations, owner filtering, revision and completed-session conflicts. Keep outer sync transaction and account-before-session locks. Do not migrate sync coordination or sport calculations early. Preserve previous user edits.

## Affected areas
basis/modules/training domain/application/adapters/public, basis/bootstrap/training, tests_architecture and adapter tests; thin delegations in training/services and training/views. Documentation and roadmap.

## Implementation steps
1. Immutable session/prescription/block/set/interval dataclasses, typed metric names/values, commands, errors and specific repository ports.
2. Inject clock, ID source, write authorization, repository and explicit-commit UoW into start/read/record cases.
3. Django adapter retains model validation, replaces child rows transactionally and keeps legacy wire codec at boundary. Legacy sync still owns hash/receipts/outer atomic and delegates execution rules.
4. Wire legacy entry points; completed/revision rules shared by ORM form writes through a typed guard.
5. Pure tests with fakes; repository/UoW contract tests including missing commit, exceptions, nested rollback, ownership, retries, receipts and JSON/Decimal compatibility; full regression and strict checks.
6. Review, branch/commit/integrate if environment permits; otherwise prepare exact native integration script, keep ticket In Progress and do not begin ARCH-03.

## Required skills
Task planning, safe Git workflow, verification before complete.

## Validation
Strict mypy core without Django and adapters with django-stubs; AST/Import Linter, Ruff, pure tests and Django SQLite regression, check and migration dry-run. PostgreSQL concurrency is separate evidence, never inferred from SQLite.

## Risks
Existing model methods and access function are untyped. Keep small, documented typed callable bridges in the persistence adapter; actual model validation must still execute. These bridges are temporary until later module/legacy migration. Do not suppress mypy globally. Git writes remain denied in Codex even with escalation; user native integration may be needed.
