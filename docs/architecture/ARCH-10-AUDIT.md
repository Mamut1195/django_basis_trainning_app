# ARCH-10 independent architecture audit

Reviewed integrated ARCH-09 main `337f12d8d6b78d52c77c3e7e821ab2af1351cdc8`. Audit date: 2026-10-20 UTC. No original database, provider, SMTP or production system is used.

## Verified starting evidence

- Architecture AST/public/type-only-import/inventory check: VERIFIED, exit 0.
- Pure suite: VERIFIED, 111 tests, zero skips; includes imports under Python `-I -S` without Django/settings/site packages.
- Strict core mypy: VERIFIED, 95 source files, exit 0.
- Original regression method inventory: all 111 original `training/tests` test methods from `08dcd020ad9e7ae2809b4a2376c8ae4cddd6b36e` remain under the same class/method names; none removed. This establishes retained scenarios, not equivalence of every assertion or functional-ticket acceptance.
- Full current mypy: temporarily NOT VERIFIED because ARCH-10 config already references the browser executor's not-yet-created `scripts/acceptance_browser.py`. Re-run after source freeze.

## Confirmed findings and approved resolution before edits

1. **Inter-module display lookup bypass in athlete admin.** `basis/modules/athletes/adapters/admin.py` reads `obj.exercise.nivel_fatiga` directly in both admin display helpers. Catalog owns that field. Extend catalog's existing typed presentation contract with a fatigue scalar projection, implement it within catalog, compose it in bootstrap, and replace both foreign-model dereferences without changing displayed values or missing-value fallback.
2. **Foreign persistence schema in training form.** `basis/modules/training/adapters/forms.py` filters an automatically generated foreign RM queryset through `user__account_id` and `fecha_registro`. Move the exact owner/date/order-aware field construction to the athlete adapter, compose its framework field in bootstrap, and inject it into the training form. Publish only a typed read-choice contract, never ORM or HTTP types. Preserve `ModelChoiceField`, field presentation, submitted-value validation, and existing error messages.
3. **Planning validation depends on persistence implementation.** `Planning.add_cycle`, `schedule` and `reschedule` currently delegate cycle/date validation to repository/model hooks. Keep typed repository read contexts for plan/parent/cycle data and invoke existing pure `validate_cycle` / `validate_schedule` before writes in the application. Keep owner lookup and authorization/revision error ordering, adapter model validation as a storage guard, and existing HTTP error translation. A permissive fake writer must prove invalid inputs never reach repository writes without Django.

The primary explicitly approved these corrections as architecture completion. They are not new product features or schema changes. Implementation ownership is limited to the named public read projections, admin/form composition, planning contexts/repository/application/fakes/tests and this audit evidence. Root owns public exports and aggregate gates.

## Acceptance still outstanding

Final full typing/import/Ruff/Django tests, empty migrations/registry checks, actual browser/offline acceptance and fresh PostgreSQL concurrency/regression remain to be recorded after the corrections. Physical-device, live-provider and remote-CI acceptance are separate and NOT RUN by this audit.


## Scope extension approved after complete entry-point review

The first three corrections pass strict core/runtime typing and 13 targeted Django tests. A complete entry-point review then confirmed additional architectural bypasses; the primary reopened ARCH-09 instead of accepting package relocation alone.

Before the following edits, the agreed implementation is:

- Preferences and billing read-time default provisioning enter typed application workflows with explicit UoW. Preserve existing authenticated read access without commercial write authorization.
- Private RM/workout/preference commands validate through pure policies and typed repository read contexts before writes. Workout calculation receives a dated/frozen measured-reference projection and returns typed derived metrics; model hooks remain a defensive storage validation path using the same pure rules.
- Athlete and catalog admin save/delete/bulk-delete/inline-save hooks invoke typed administrative cases, staff authorization, own persistence adapters and explicit UoW. Administrative profile handling deliberately supports unlinked profiles and retains existing admin permissions and validation; do not impose athlete commercial access on administrative operations.
- Serializer normalization and positive-RM checks share existing pure policies, preserving their current outward messages.
- The development-only `seed_demo` bootstrap is an explicit operational fixture exception, gated by DEBUG, DEVELOPMENT_ACCESS and generated/environment-provided credentials. It is not a normal application write entry point. Auth-framework password/session plumbing remains a framework adapter responsibility.

No schema change, provider execution or original database operation is authorized by these corrections. Remaining direct training-view mutation workflows are assigned to a separate executor; their status must be included before final acceptance.


## Resolution evidence from this audit pass

| Finding | Implemented resolution | Evidence |
| --- | --- | --- |
| Catalog display dependency in athlete admin | Public `ExerciseNames.fatigue` read projection, catalog-owned adapter and bootstrap binding | Both admin displays tested with real data and injected projection; archived values retained |
| Foreign RM selection schema in training form | Public `RMChoices` eligibility port; athlete-owned field adapter; bootstrap composition | Private owner/date filtering, descending measured-date ordering, original label/required state and invalid-choice code tested |
| Planning writes rely on persistence policy | Typed cycle/schedule creation contexts; pure validation and latest-version guard before writes | Permissive writer tests reject invalid cycle/schedule/reschedule before mutation; shared fake/Django out-of-cycle contract |
| Private plan creation lacks core authorization/ownership | Authorized `create`; rollback-only `preview`; private validated-creation helper; typed goal-owner projection and previous `PlanHeader.owner` guard | Permission denied despite permissive writer; preview without commercial access rolls back; foreign goal/previous rejected |
| Read views provision rows directly | Athlete preferences and billing `ensure` use explicit case UoWs, without commercial guards | Pure read-provisioning tests preserve unverified/read-only access and avoid gateway calls |
| Private athlete policy exists only in model hooks | Typed RM/workout contexts, immutable/reference policies, pure metric computation before writes; model hooks remain defensive validation | Permissive fake tests cover positive/immutable RM, foreign/future references, frozen absent reference, zero/overflow, computed Decimal metrics and invalid preferences |
| Native admin bypasses typed cases | Concrete profile/RM/workout administrative commands and catalog cases; staff/model-permission authorizers; own repositories and UoWs | Five actual Django tests: unlinked age-16 profile with add-only staff permission; private-workout metric/reference derivation; permission denial; protected bulk-delete rollback; profile inline write |
| Catalog muscle limits exist only in model hook | `validate_exercise` called before catalog persistence; own field error translated unchanged | Permissive catalog writer rejects 31 names or 81-character names; accepts the original 30/80 boundary |
| Reconciliation failure writes directly in command | `Billing.mark_pending(OwnerBilling)` and explicit UoW | Pure missing/existing-account and no-provider tests; operational own-schema candidate selection remains a read adapter |

Final local checks before the last layer correction: full 147-test pure suite VERIFIED; core mypy 105 files VERIFIED; complete strict mypy 266 files VERIFIED; complete Django suite 240 tests OK with five PostgreSQL-only skips. The Django run is recorded in `.cache/arch10-audit-final.stdout.log` and `.cache/arch10-audit-final.stderr.log`. Django check and migration drift check passed on `sqlite:///:memory:`. These are local SQLite results, not a PostgreSQL acceptance claim.

Import Linter then correctly found an indirect domain-to-application cycle: athlete domain workout orchestration imported training public, whose manual application port imports athlete public for type checking. The repair keeps athlete result/context values in domain and moves cross-module metric orchestration to `athletes.application.workouts`. This maps the existing public training result to a local immutable `WorkoutMetrics` projection; it does not duplicate formulas or relax import checks. All eight Import Linter contracts passed after this separation. The public `calculate_workout` export was relocated to the application helper and `WorkoutMetrics` remains an immutable domain projection. Final checks below were repeated after this exact correction; no import-contract exclusion was added.

## Registry, history and accepted infrastructure boundaries

An empty in-memory installation was verified with 28 module models and 38 total tables: accounts 1, athletes 7, catalog 2, training 10, billing 2, coach 5 and sync 1. No retired app is registered. The registered business admin models are the original three athlete and two catalog models. `seed_demo`, `link_legacy_profile`, `reconcile_billing` and `process_ai_jobs` resolve from their final module adapters. No migration drift or Django check issue was found.

`PlanDefinition`, its cycles/schedules/blocks and metric values are frozen dataclasses with immutable tuples. The definition has no program/proposal/provider provenance dependency; manual and accepted AI creation now use the same authorized creation path. Preview is an explicitly non-committing validation workflow. Source mutation and old-version execution preservation remain covered by the existing shared and real repository tests. No predefined-program catalog or publication feature is implemented or implied.

Django owns authentication/session/password/token mechanics, admin form/model-field validation, permissions/content types, relational widget representation and migration schema operations. Such framework plumbing is not an alternative business workflow. Persisted model hooks retain defensive field/FK/integrity validation and invoke the same pure policies used by cases. `seed_demo` remains the explicitly gated development-fixture exception. Protected `seed.py` and standalone backup tooling remain explicitly inventoried outside the strict runtime scope; their existence does not register an old application.

No open PostgreSQL, browser/device, live-provider or remote-CI gate is closed by this document. Final aggregate checks, browser source binding and main readback belong to the primary acceptance gate.


## Final audit-source freeze and repeated checks

All confirmed findings above are resolved in the frozen source examined by this audit. The auditor implemented the explicitly approved corrections; the primary must still perform independent final acceptance and source/main readback.

| Final command | Actual result |
| --- | --- |
| `python -m unittest discover -s tests_architecture` | VERIFIED: 147 tests, OK, zero skips |
| `python -m mypy --config-file mypy-core.ini` with isolated audit cache | VERIFIED: 106 source files, zero errors; no Django plugin |
| `python -m mypy --config-file mypy-django.ini` with isolated audit cache | VERIFIED: 267 source files, zero errors |
| `lint-imports --config .importlinter --no-cache` | VERIFIED: all 8 contracts; 272 files / 1175 dependencies |
| `python scripts/architecture_check.py` | VERIFIED: layers, public/type-only boundaries, retired packages and strict inventory |
| Full final Django labels under `config.test_settings`, temporary in-memory SQLite | VERIFIED: 240 tests, OK; 5 PostgreSQL-only skips, 12.220 seconds |
| `python -m ruff check .` | VERIFIED: all checks passed |
| `manage.py check --settings=config.test_settings` | VERIFIED: zero issues |
| `manage.py makemigrations --check --dry-run --settings=config.test_settings` | VERIFIED: no changes detected |

The repeated full Django command covers `tests.regression`, `basis.bootstrap.tests`, billing adapter persistence/Polar contracts, training metric boundary tests and sync wire tests. Final logs: `.cache/arch10-audit-final.stdout.log` and `.cache/arch10-audit-final.stderr.log`. Original 111 regression scenarios are now under the final strict `tests/regression` namespace, not an old runtime application. Runtime configuration is `config/`; retired application/configuration packages are absent after the user's explicit cleanup.

The browser executor was notified BEGIN/END around the last imported-code correction. Its earlier browser receipt is not attributed to the final bytes; the primary must bind a repeat browser acceptance to these final sources. PostgreSQL five-race execution, final browser proof, commit integration and main readback remain separate acceptance gates. Physical-device, paid-provider, production and remote-CI evidence remain NOT RUN by this audit.
