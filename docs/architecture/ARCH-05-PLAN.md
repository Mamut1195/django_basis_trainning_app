# ARCH-05 - metrics and multisport

## Goal
Extract strength calculations, measured sport variables, pace/load, progress/adherence and trekking into strict typed pure domain/application contracts and Django adapters. Keep existing behavior, precision, optional values, historical RM references and public formats.

## Context
ARCH-04 integrated main/20cc32ca25a905cbb20a3e6707d92ae74797c573; run92a87ed71d6947898ade23e1be0a24cd independently checked148 PostgreSQL tests/no skips/stopped container,26 files and all tree/HEAD hashes. MAM-825 Done, MAM-826 In Progress. User confirms no production and authorizes moderate parallel delegation with primary agent orchestrating. Existing seed.py168 additions/56 deletions and manage.py mode remain excluded.

## Constraints
No formula/rounding, RM-as-of/history, units, HTTP/JSON, schema/labels/migration, CSRF or ownership changes. Missing remains distinct from zero. No new sport/program/provider features. Preserve report ordering/labels and current adherence replacement-version cutoff. Read/query adapters may stay in compatibility boundaries until ARCH-09; business arithmetic/policies must be pure. No new global typing exclusions or free JSON in core.

## Affected areas
basis training domain/application/adapters/bootstrap/public, existing daily strength/domain/model and training domain/model/form/service/view bridges. Dedicated pure and real adapter tests. Architecture docs, explicit manifest and external verification/integration scripts. The legacy inventory only shrinks when a complete file is certified.

## Implementation steps
1. Agent metrics owns pure strength/sport definitions and validation, Decimal arithmetic/pace/internal load, legacy strength_metrics.py and training/domain.py bridges, both existing model files and training/forms.py. It must preserve measured-reference persistence policy and wire pure trekking model hooks supplied by the second agent.
2. Agent progress owns typed progress/adherence/trekking read/write use cases and Django repositories/presentation, bootstrap/progress, training/services.py report bridges and training/views.py trekking writes. It supplies stage invariant hooks to the metrics owner; it does not edit that owner's files. Aggregation consumes typed values/records and controlled clock; no ORM in core.
3. Orchestrator owns public export merging, shared identifiers/configuration/CI, docs/tracker/manifest/operator scripts and integration verification. Two parallel executors, one deliverable; no ARCH-06 work. Executors report exact tests/errors and coordinate via messages before shared-boundary changes.
4. Verify pure tests/fake+real contracts, Decimal/null/zero/range/finite cases, effort eligibility, report/adherence across versions, hiking totals without double count, owner-scoped trek/stages and rollback. Run full baseline regression, strict scopes, architecture/import/Ruff/Django/no migrations; inspect bounded diff and unchanged user work.
5. Prepare the external Docker PostgreSQL/main integration command only after a reviewable candidate. Done requires actual receipt/logs, all tests with no skips, stopped owned container, source/HEAD hashes and main commit readback. Do not start ARCH-06 before that gate.

## Required skills
task-planning, safe-git-workflow, verify-before-complete. Only the two explicitly authorized agents execute source changes; primary coordinates integration, checks and evidence.

## Validation
Core must run/import without Django/DB/network. Strict mypy core and Django scopes, static/public boundaries including type-only imports, eight Import Linter contracts, Ruff, Django checks and no migrations. Full temporary SQLite and PostgreSQL suites. Every item VERIFIED/FAILED/NOT RUN; preserve logs and receipts.

## Risks
Legacy validators accept loose external dictionaries/numeric inputs; preserve coercion/error mapping in adapters and give typed values to core. Strength overflow/quantization, nonmaximal RM, blocked references and mixed protocols cannot change. Report order and historical adherence are observable. Shared workspace means explicit file ownership; no overlapping edits or Git mutations by workers. Environment Git/Docker restrictions remain; no ACL or execution-policy bypass, discard/stash/reset/clean.
