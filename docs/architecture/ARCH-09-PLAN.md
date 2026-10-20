# Goal

Complete ADR-002: remove the daily_trainning_app package and the training runtime application. Keep a Django monolith whose seven business modules own their typed persistence and web adapters. No production database exists; create the final schema through fresh initial migrations on disposable databases.

# Context

ARCH-08 is already integrated at 24f98532112230640e8a5346dad5e55dcb52627e. Its receipt records 218 PostgreSQL tests, zero skips, run fe03da62e81f444facf4eadf1baf0b70. The repeated Complete-Arch08 invocation correctly stopped at its reviewed-base guard. Do not change that guard or repeat the integration. Preserve unrelated seed.py contents and manage.py mode.

# Constraints

Domain/application remain framework-free. Cross-module imports, including type imports, use public contracts only. ORM foreign-key strings are persistence relationships, not permission to import another module's adapters. Cross-module lookups and business validation use narrow typed public ports wired in bootstrap. No Any, global missing-import exclusions or silent model frontiers. Shared remains pure; Django utilities belong in bootstrap. Do not move the legacy application wholesale into bootstrap.

Keep route names, web/API behavior, JSON, offline assets/queues, commands and the 218 existing regression scenarios. Model/app labels and tables deliberately change under ADR-002. No new functionality, provider calls, original-database migration, production activity or Git-history rewriting. Baseline regression tests may remain in the unregistered training/tests namespace as an explicit shrinking legacy test inventory; no production compatibility shims remain there.

# Affected areas

Each module registers basis.modules.<area>.adapters.apps.<Area>Config, label basis_<area>, models in adapters/models.py and fresh adapters/migrations. Accounts owns RateWindow. Athletes owns User (athlete profile), AthleteSettings, SportProfile, Measurement, Wellness, UserExerciseRM and WorkoutData. Catalog owns Classification and Exercise. Training owns Goal, TrainingPlan, Cycle, PlannedSession, Session, Block, StrengthSet, Interval, TrekTrip and TrekStage. Billing owns BillingAccount and WebhookReceipt. Coach owns UsagePeriod, TrialFund, AIJob, PlanProposal and AIServiceState. Sync owns SyncReceipt.

Bootstrap owns explicit wiring, shared Django model/form/request helpers, root routes and multi-module read composition. Module adapters own forms, views, API, admin and operational entry points. The project settings package remains configuration infrastructure. Protected seed.py is outside application runtime and outside this delivery.

# Implementation steps

1. Persistence executor owns the seven model modules, AppConfigs, initial migrations, bootstrap/persistence.py, existing repository/bootstrap model-import rewrites and deletion of old model/migration files. Use typed public athlete RM lookup injected by bootstrap for cross-module validation. Preserve validation ordering and numeric conversion behavior. Own module admin registrations can be supplied after coordinating with the web executor.
2. Web executor owns module forms/views/API/admin, bootstrap/web_framework.py and bootstrap/web.py read composition, routes, legacy regression-test import/mock rewrites, and deletion of old forms/views/API/admin files. Split by business area; foreign read data arrives through typed public ports/DTOs. Preserve authentication, CSRF, owner filters and responses. Do not edit existing bootstrap repository files, settings, public exports or strict configuration without coordination.
3. Binding executor owns relocation/retirement of already typed access, billing, ai, proposals, services, domain and strength-metrics facades, plus middleware, context processors, brand, API error translation, management commands and template tags. New input adapters are legitimate module bindings; remove unused duplicate implementations rather than moving unused shims. Bootstrap may compose operational multi-area work. Coordinate final names with web executor; no old runtime training imports remain.
4. Primary orchestrates, reviews boundaries and evidence, integrates public exports, settings, strict configuration/inventory, CI, documentation, migration verification and explicit added/deleted-file manifests. Independent workers do not create commits, touch user changes, call providers or spawn children.
5. Run pure and Django regression tests, strict core/Django/DRF typing, AST/public/import/inventory contracts, Ruff, Django checks and migration drift. Prove empty-database installation, owner/transaction behavior and all PostgreSQL races on a disposable Docker database. Check offline assets and route compatibility. Prepare deletion-aware external verification/integration scripts; close only after independently checking the resulting commit on main.

# Required skills

task-planning, safe-git-workflow, verify-before-complete; systematic-debugging for reproduced failures. Three implementers maximum plus primary orchestration, as authorized by the user.

# Validation

Record VERIFIED, FAILED or NOT RUN with actual commands, logs and exit codes. No silent model frontier or active legacy imports. Inspect source and HEAD hashes, explicit deletions, initial migrations, scope and protected files. PostgreSQL must have zero skips and the owned container must be stopped. Browser/device, remote CI and real providers are separate evidence and must not be inferred from backend tests.

# Risks

Fresh app labels affect permissions, admin URLs, serializers and content types. Dynamic auth relations, ModelForm generics and DRF typing require real type coverage. Foreign-key validation must not bypass public boundaries; splitting read views must preserve ordering and missing-versus-zero semantics. Test patch paths must follow actual call sites. The final deletion manifest must verify absence instead of hashing deleted files. Do not use the old legacy-schema migration script on an original database.
