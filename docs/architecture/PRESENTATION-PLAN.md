# Presentation and readability implementation

## Goal
Complete ARCH-09 presentation ownership and composition boundaries, preserving behavior.
## Context
Starting main: 717cc1b. ARCH-09 MAM-830 and ARCH-10 MAM-831 remain In Progress.
## Constraints
Preserve original 111 regression methods, 28 models, export-v1, URLs, offline privacy and all pre-existing edits. No schema, production, provider or TypeScript changes.
## Affected areas
basis/bootstrap, module adapters, templates, assets, config, architecture gates, developer tooling and CI.
## Implementation steps
1. Independent formatting/tooling commit (Ruff 100 columns; djLint/Prettier two spaces).
2. Move technical infrastructure to basis/adapters/{web,django}; keep factories in bootstrap. Move module input conversion to its owner.
3. Module templates to adapters/templates/<area>, common templates to technical web app. Common static to static/basis; vendor remains vendor.
4. Split training web by planning/execution/strength/intervals/progress/trekking; split training and athlete persistence by coherent responsibility with one registry definition.
5. Shared form/error/notice/loading components and feature partials; accessibility/mobile review.
6. Typed owner-selected export readers, defensive shared history policy, expanded boundaries and regression coverage.
7. Full strict/static/schema/PostgreSQL and browser acceptance; record actual results and reconcile Linear.
## Required skills
Task planning, safe Git workflow, verify before complete. Systematic debugging for reproduced failures.
## Validation
Pinned format checks, Ruff, both strict mypy configurations, import contracts, AST checks, pure tests, complete PostgreSQL regression without skips, 28-model registry and empty migrations, template origins/reset/HTMX/export ownership, real browser offline/replay/conflicts/CSRF/logout/account separation, desktop/mobile/light/dark/keyboard.
## Risks
Django model package discovery, Cotton formatting and namespacing, password reset template collisions, CSS cascade, SW stale shell. Historical evidence stays unchanged. Pre-existing file content hashes are recorded locally in .cache/presentation-original.json.
