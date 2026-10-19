# ARCH-04 - planning and versions

## Goal
Extract goals, cycles, scheduling/rescheduling, private-plan creation and versioning into typed domain/application ports and Django adapters. Manual and AI inputs share a PlanDefinition separated from provenance. No programs catalog, publication or UI.

## Context
ARCH-03 is integrated at main/ddcf178d6a5c8c4793e3672a95dbf64fdffe2b91. Receipt/logs139 PostgreSQL tests, zero skips, stopped container and all source/HEAD hashes were independently checked. MAM-824 Done, MAM-825 In Progress. Existing seed.py/manage.py user changes are excluded.

## Constraints
Keep labels/tables/migrations, forms/URLs/JSON, owner authorization and model validation messages. Manual empty draft plans remain valid; proposal-specific366-day and cycle/session count limits stay in the proposal adapter. Preserve lock order and proposal acceptance/idempotency in the current coach bridge until ARCH-07. Versioning copies all cycles and only future/unexecuted schedules, leaving old prescriptions/results intact. No invented actual values; absence and zero remain distinct.

## Affected areas
training domain/application/adapters/public and bootstrap/planning; shared GoalId/CycleId/LineageId; legacy model clean hooks/forms/views/services/proposals as narrow compatibility adapters. Existing execution block data and codecs are reused within the same module.

## Implementation steps
1. Typed plan definition, cycle/schedule/goal data, immutable snapshot/results and pure date/hierarchy/prescription/version policies. NewTypes for IDs. Explicit commands/ports for creation, preview, revision, goals, cycles, schedule/reschedule and calendar.
2. Django repository reads/writes stable tables, maps definitions and uses real full_clean/save hooks. Explicit UoW/clock/authorization injection. Model clean delegates shared pure policies with unchanged error mapping.
3. Proposal wire adapter validates external shape/counts and converts to the same definition as manual forms; preserve error categories. Current accept_proposal keeps its proposal lock/state and delegates private creation. Validation preview always rolls back. Existing revision wrapper delegates typed case.
4. Wire manual forms, rescheduling/revision and goals without changing UI/errors. Keep generic read querysets and admin compatibility for ARCH-09, expose typed owner-scoped calendar reads.
5. Pure/fake and real-adapter tests: shared definition, hierarchy/ranges, source isolation, prescribed/actual zero, revisions and executed/past exclusion, immutable old records, rollback, owners and revision conflicts. Full regression, strict typing/import/lint/Django/migrations.
6. Prepare external Docker PostgreSQL and Git integration command only after the full local candidate is reviewable. Independently check returned main SHA/receipt/logs/hashes before Done or ARCH-05.

## Required skills
task-planning, safe-git-workflow, verify-before-complete.

## Validation
Core isolated from Django/DB/network; both strict mypy scopes, AST/public rules, eight import contracts, Ruff, Django check/no migrations, full temporary SQLite and PostgreSQL regression. Record VERIFIED/FAILED/NOT RUN and preserve logs.

## Risks
Legacy proposals accept loose JSON and have distinct validation categories; conversion must preserve valid payload behavior and partial manual drafts. Historical metric/reference hooks remain for ARCH-05. No new global typing exclusions. External operator handles Git/Docker; no ACL/execution-policy bypass or destructive recovery.
