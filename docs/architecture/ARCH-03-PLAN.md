# ARCH-03 — identity, athletes and catalog

## Goal
Extract existing identity, profile/preferences, basic wellness/measurements/sport profile, catalog and legacy RM/workout operations behind strict typed use cases. Preserve existing web/API behavior and data.

## Context
ARCH-02 is integrated at main/2f3c95e. Its receipt, logs and all source hashes were independently checked: 124 PostgreSQL tests pass, zero skips, container stopped. Only seed.py and manage.py are unrelated user changes; retain them.

## Constraints
Keep Django authentication, password validation/hashing/reset tokens, CSRF, form/DRF error translation, URLs, JSON, labels, tables and migrations. No SMTP LIVE, paid providers, production, functional features or seed publication. Historical metric calculations stay in existing persistence until ARCH-05; do not invent results or change as-of reference behavior.

## Affected areas
basis modules accounts/athletes/catalog domain/application/adapters/public and explicit bootstrap composition. A narrow billing public enrollment port initializes the existing empty billing account during registration; it does not migrate billing policy. Shared IDs and a bootstrap transaction adapter avoid importing another module's adapters. Thin compatibility bindings in current views/forms/serializers and the explicit legacy linking command; legacy ORM stays registered as-is.

## Implementation steps
1. Pure dataclasses/errors/policies, specific Protocol ports and typed commands/results for each area. Cross-module enrollment uses public contracts, never another module's ORM/adapter.
2. Accounts: inactive registration, verification GET/POST separation and 24-hour signed claim adapter, resend without enumeration, recovery through Django's existing password reset adapter, shared rate-window policy, explicit legacy linking with unchanged ownership checks.
3. Athletes: owner-scoped profile, preferences, sport profile, wellness and measurement commands; immutable measured RM and historical workout commands. Keep all current model validation and derivation through documented typed infrastructure bridges.
4. Catalog: authenticated read/staff-write policy and classification/exercise commands, preserving archive/protected-delete and serializer formats. Existing querysets/serializers are compatibility web adapters until ARCH-09; move their persistence operations into typed adapters/use cases.
5. Wire current entry points, preserve form/DRF validation and owner selection. Add pure and adapter/web tests, including rollback and cross-account checks. Run full strict/lint/import/Django/SQLite gates.
6. Prepare a Docker PostgreSQL/verification/integration operator command, as authorized by user. Mark Done only after its commit/receipt/logs and main are independently checked. Do not start ARCH-04 early.

## Required skills
task-planning, safe-git-workflow, verify-before-complete; systematic-debugging only if an unexplained failure appears.

## Validation
Core importable with -I -S, strict mypy without plugin; adapters strict with django-stubs and exact pending-legacy frontiers. Common repository/UoW contracts plus pure policies, two-account web/API, signed/expired/mismatched claims, registration mail rollback and password recovery non-enumeration. Full existing regression and PostgreSQL concurrency; check no unexpected migration. All verification states are explicit.

## Risks
Legacy Django forms/serializers are dynamic and partially untyped; keep their behavior at boundary, convert to dataclasses before use cases and document temporary callable/model-save bridges. Never silence migrated modules globally. Git/Docker writes are blocked in this Codex environment; user will execute the reviewable external completion script. Preserve exact working changes and report actual, not assumed, checks.
