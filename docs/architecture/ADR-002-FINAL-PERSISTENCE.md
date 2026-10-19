# ADR-002 - Final persistence structure (2026-10-19)

## Decision

The user confirms there is no production and explicitly prioritizes the proposed architecture over preserving legacy persistence structure. This supersedes ADR-001's requirement to retain existing Django app labels, tables and historical migrations as a final constraint.

ARCH-09/MAM-830 must remove `daily_trainning_app`, move its responsibilities to the appropriate `basis.modules` business areas, and register Django persistence models in the final module adapters. Apps, table names, migration dependencies, settings, admin, commands, URLs and imports may be reorganized as required. Temporary compatibility bridges and duplicated implementations must be removed. A legacy package kept solely for historical migration compatibility does not satisfy acceptance.

The business architecture remains a Django/PostgreSQL monolith with independent typed domain/application, public module contracts and explicit composition in bootstrap. No new functional feature or predefined-program catalog is added.

## Execution and acceptance

ARCH-06 through ARCH-08 may retain the current schema to keep deliveries bounded; that is a staging choice rather than the final design. Before structural work in ARCH-09, inventory model ownership, relations, app registration, migration dependencies, templates/static resources, commands, admin and active imports, and document the schema/data strategy. Do not discard unrelated user edits or unnecessarily delete local data. Exercise schema rebuilds only on temporary databases.

ARCH-09 acceptance requires no remaining package or active imports for `daily_trainning_app`, coherent final model registration and relationships, and successful migration from an empty temporary database. ARCH-10/MAM-831 additionally verifies full regression, strict typing, architecture boundaries, commands/admin and web/offline behavior on the final structure. Existing functional scenarios remain regression requirements.

## Tracking

Recorded and independently read back in Linear epic MAM-821 and tickets MAM-830/MAM-831 on 2026-10-19. MAM-827 records that the current ARCH-06 schema stability is temporary. Historical evidence and original decisions remain records of their own time; this ADR governs the final structure.
