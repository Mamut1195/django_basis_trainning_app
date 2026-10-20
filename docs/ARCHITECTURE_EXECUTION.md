# Goal

Finish the strict typed hexagonal Django/PostgreSQL monolith before functional acceptance. ADR-002 authorizes the final module schema and removal of daily_trainning_app; predefined programs remain future work.

# Context

ARCH-01..08 are integrated. Current main337f12d8d6b78d52c77c3e7e821ab2af1351cdc8 contains the structural ARCH-09 delivery, verified224 PostgreSQL/no skips. ARCH-09/MAM-830 was reopened after the user and source audit identified remaining business writes in web/admin, validation deferred to persistence and old configuration naming. The new remediation is a separate candidate; prior PostgreSQL evidence does not certify its bytes. ARCH-10/MAM-831 is In Progress for acceptance, not complete. Preserve user seed.py edits and manage.py working-tree mode; manage.py content is now in scope to activate config.

# Constraints

Domain/application independent of Django/providers/HTTP/ORM. Cross-module public typed contracts only. Explicit bootstrap injection, no mandatory event bus/generic CRUD repository. Preserve routes/JSON/exports/offline queue/auth/CSRF/owner behavior. Seven final app labels and new initial migrations are authorized under ADR-002, on disposable databases only. No original DB mutation, live provider/paid/SMTP calls, ACL changes, execution-policy bypass, destructive Git recovery or history rewriting.

# Affected areas

ARCH-09 remediation:28 models across seven module adapters, initial migrations/AppConfigs, actual typed web/admin/command cases, pure policies and concrete public read projections. config owns settings/URLs/ASGI/WSGI. tests/regression preserves all111 baseline scenarios under strict typing; old training source is retired. See architecture/ARCH-10-PLAN.md, architecture/ARCH-10-AUDIT.md and architecture/ENTRYPOINTS.md for the approved corrections and evidence.

# Implementation steps

1. Three authorized executors implement disjoint persistence, web and operational bindings. Primary orchestrates/reviews/public exports/configuration/evidence, not business implementation.
2. Verify pure and real repository/transaction/model contracts, owner/CSRF/web compatibility, all baseline test scenarios, unchanged offline assets and stable external export tags. Fresh initial migrations and final content types/permissions must work on empty DBs.
3. Independently freeze/check strict core+Django/DRF typing, AST/public/inventory and import contracts, Ruff, Django/no drift/static and SQLite regression. Publish exact manifest including deletions and actual counts/evidence.
4. External Complete-Arch09-Remediation verifies fresh disposable Docker PostgreSQL/all races with zero skips and real browser acceptance, binds all runtime/test/config/asset source hashes and retired-path absence, stops owned processes/container, stages only reviewed scope, commits and fast-forwards main. Preserve manage.py original index mode100755. Assistant Docker access remains denied. Do not close on a working tree or user summary alone; the old Complete-Arch09 script is historical and must not be rerun on the remediation.
5. Read back SHA/logs/receipt/stopped container/hashes/all committed additions/deletions. Mark ARCH-09 Done only then. ARCH-10 separately verifies final architecture plus complete web/offline acceptance and reconciles Linear/documentation before closing the epic.

# Required skills

task-planning, safe-git-workflow, verify-before-complete, systematic-debugging for reproduced failures.

# Validation

Record VERIFIED/FAILED/NOT RUN using actual logs and exit codes. No silent model frontiers, global missing-import exclusions or new Any escapes. Retain all baseline tests and user changes. PostgreSQL zero-skips and main readback required. Browser/device and remote CI evidence must not be inferred from API/unit tests. Stage scripts02..08 are historical evidence after final package relocation; use the current stage script.

# Risks

App-label changes affect permissions/admin/export internals; external export-v1 tags stay compatible. Final deletion manifests verify absence instead of attempting to hash deleted files. User seed.py remains inactive and imports the retired application; seed_demo is the current supported demo command. Ignored compiled caches are not tracked source or registered apps; no bypass of rejected cleanup is attempted. ARCH-10 acceptance remains pending after ARCH-09 delivery.
