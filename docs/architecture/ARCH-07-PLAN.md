# Goal

Extract coach context, token/cost policy, reservations/settlement, durable jobs and proposal acceptance into strict typed hexagonal cases. DeepSeek becomes an adapter; acceptance uses the common ARCH-04 planning definition. Preserve valid behavior, quotas, ownership, frozen context, provider ambiguity and existing transport seams without live calls.

# Context

ARCH-06 independently verified in main/c5cc0c17d7f3070c81950a89ea8ccbdcdde696e6:180 PostgreSQL/no skips, stopped container,43 committed files and all normalized tree/HEAD hashes; run136ec5dcf05f42d5b705540d62a6b9ad. MAM-827 Done, ARCH-07/MAM-828 In Progress. Legacy training/ai.py contains context construction, HTTP payload/budget validation, enqueue, settle, process_one and stale quarantine. training/proposals.py contains planning wrappers and atomic acceptance; views also edit/reject proposals. Original seed.py/manage.py stay excluded.

# Constraints

Keep current URLs/JSON/HTML, commands, provider request payloads/system prompts, token limits/rates/rounding, lock order (fund/account/billing/usage; settlement's existing fund/account/job/usage), idempotency and owner authorization. An ambiguous timeout/crash must retain reservation and never retry. Preserve per-account lifetime trial and monthly global fund, trial/paid separation and period invalidation before provider call. No Any/free JSON/ORM/HTTP in core interfaces; context and provider results use typed immutable dataclasses. JSON conversion remains in adapters. Other business data must be obtained through public contracts, not direct foreign ORM imports. Explicit UoW, Decimal and distinct IDs.

No provider requests, paid calls, credentials read or logged, migrations or functional features. This stage keeps the current schema only to bound extraction; ADR-002 requires final app/schema/migration reorganization and daily_trainning_app removal in ARCH-09. Use temporary databases. No Git writes/ACL changes/execution-policy bypass, stash/reset/clean, unrelated edits or history rewriting.

# Affected areas

coach domain/application/adapters and public contracts, explicit bootstrap/coach, narrow public billing/account locking contracts and public athlete/catalog/training context/planning projections, legacy ai/proposal facades, coach/proposal web bindings and process_ai_jobs command. Existing forms/admin/query reads are either delegated where relevant or recorded as remaining ARCH-09 integration; do not leave business edit/reject/accept rules duplicated in views.

# Implementation steps

1. Core/jobs executor owns coach/domain/jobs.py, coach/application/jobs.py, coach/adapters/jobs.py and related job wire persistence helper if needed; narrow accounts lock and billing locked entitlement public-contract implementations; pure/shared fake-Django budget/job tests. This executor sends exact DTO/port/usecase/factory signatures to the sibling early. No provider/web/proposals/context/legacy-ai/bootstrap edits.
2. Context/provider/proposals executor owns coach domain/application context/prompts/proposal files (not jobs.py), corresponding adapters, public athlete/catalog/training context/planning projection implementations, bootstrap/coach.py, training/ai.py and training/proposals.py facades, coach/proposal view sections and process_ai_jobs command. It preserves training.ai.httpx.Client mock seam, frozen JSON shape, request byte counting/default string conversion and existing provider/response semantics. Sends root all public export/identifier requests. Coordinate selected-plan context injection and typed provider/settlement/proposal result conversion before dependent work.
3. Primary only orchestrates/reviews/contracts public exports/shared IDs/config/inventory/CI/docs/scripts. Two implementers only, exclusive files, no children. Core/application tests run without Django/network; no stringified free JSON or generic object payload is used to bypass core typing.
4. Verify quotas/reservation/settlement parity, unknown-vs-zero and authorized context, fake/real repository commit/rollback/owner contracts, provider MockTransport one-call/timeout/invalid usage/model block, proposal question/edit/reject/idempotent acceptance/version guard through ARCH-04. Preserve all180 regression tests; PostgreSQL tests must exercise concurrent personal/global caps and skip_locked job claims without partial writes. Cross-review before source freeze.
5. Joint mypy core/Django, AST/public/inventory/import contracts, Ruff, Django/no unexpected migrations/static, full temporary SQLite/PostgreSQL regression. Local typing exceptions must be precise and documented. Prepare reviewed manifest and external Docker/main completion script. Done only after independent main SHA/receipt/log/hash/completeness readback. ARCH-08 waits for this gate.

# Required skills

task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates; two authorized agents implement.

# Validation

Record VERIFIED/FAILED/NOT RUN with actual logs/exit codes. Preserve existing training.ai exports and mocked HTTP call seam so regression never reaches DeepSeek. Provider contracts use fakes/MockTransport; costs and answers never justify real provider calls. Freeze sources before final combined verification and bind receipt to reviewed files.

# Risks

Snapshot serialization affects UTF-8 byte budget; changing dictionary key insertion order or Decimal/date stringification can change accepted context limits. Settlement must preserve partially captured usage/answer on malformed choices, ambiguous reservations and blocking policy. Lock ordering and account/billing ownership cannot be hidden inside foreign ORM adapters. Existing settlement locks and replay ordering must remain. Plan creation/validation must be shared with manual planning and preserve accepted historical versions. Any discovered legacy behavior defect must be documented rather than silently changed.
