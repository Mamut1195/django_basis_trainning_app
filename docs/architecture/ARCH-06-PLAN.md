# ARCH-06 - billing

## Goal
Extract commercial policy, access, checkout/portal, authoritative reconciliation and webhook receipt workflow into strict typed core ports/cases and Django/Polar/web adapters. Preserve current behavior and operational commands; no live provider call or payment.

## Context
ARCH-05 integrated main/e3ffcf66deb3e8138dfa57d6773a400c3a87426e. Independent readback verified158 PostgreSQL/no skips, stopped container,39 files and all tree/HEAD hashes; run5979be3c5b6447c6bbeee21f4e6cd0a7. MAM-826 Done, MAM-827 In Progress. User authorizes two executors with primary orchestration, confirms no production. seed.py168 additions/56 deletions and manage.py mode remain excluded.

## Constraints
ARCH-06 keeps the current schema/labels/migrations to bound this delivery. This is temporary: the user's 2026-10-19 scope amendment requires ARCH-09 to remove daily_trainning_app and reorganize models/apps/schema/migrations into the final basis modules; historical persistence structure is no longer a compatibility requirement. Preserve URLs/JSON/statuses/CSRF, expired read/export access, owner scope, cached checkout, trial history and unique customer IDs. Product remains server-selected USD5 monthly, exclusive tax and native7-day trial. No provider requests, paid calls or credential inspection in verification. Preserve bounded GET under billing row lock and existing ambiguous error handling. Webhook receipt, needs_reconciliation and later result are deliberately separate commits: a provider failure must retain pending flag and unprocessed receipt. Don't replace this with one transaction that rolls the flag back. Preserve existing training.billing.polar_request mocking seam to prevent network in baseline tests.

## Affected areas
basis billing domain/application/adapters/public and bootstrap/billing; narrow public athlete billing-profile read port/adapter rather than importing another business module's ORM; legacy billing/access/model/web/management bridges and existing authorization composition. Public exports/IDs/config/CI/docs and operator scripts are coordinated centrally.

## Implementation steps
1. Billing core executor owns domain values/policies, typed commands/results/Protocols, explicit-UoW cases, billing Django persistence/authorization, narrow athlete profile lookup implementation, training/access.py and BillingAccount model hooks, existing training/athlete authorization adapters and their composition roots except bootstrap/billing.py. It supplies exact public contract/DTO/repository/factory requirements early.
2. Polar/web executor owns typed HTTPX/provider conversion and URL/signature adapters, bootstrap/billing.py, training/billing.py facade, billing web action/webhook section of training/views.py and reconcile_billing command; it preserves patch seam and existing error translations. No edits to the other executor's model/access/domain/repository files.
3. Primary merges public exports/shared identifiers, strict-scope/inventory/CI and documentation/operator evidence; no business implementation by primary. Two executors only and one serial delivery. Coordinate DTOs before dependent implementation. Core cannot receive ORM/HTTP/Any/free JSON.
4. Pure commercial/access/period-boundary tests with controlled time and fake gateways; shared fake/Django receipt/repository transaction contracts; provider mock transport contracts/no real network; webhook invalid signature, replay/unknown type/unlinked ID/failure/retry and pending flag; authoritative cancellation/trial/product identity and rollback. Preserve request payloads and exact selection/cutoff behavior, including raw ISO ordering where used by legacy reconciliation.
5. Joint strict mypy, architecture/public/inventory/import, Ruff, Django/no migrations and full temporary SQLite/PostgreSQL regression. Certify fully migrated facades only and reduce pending inventory, no broad exceptions. Document any local third-party typing boundary precisely if unavoidable.
6. Prepare external Docker PostgreSQL/main integration only after a reviewable candidate. Done requires main SHA, actual logs/receipt, all tests/no skips, stopped owned container, source/tree/HEAD hashes and committed completeness. ARCH-07 waits for this gate.

## Required skills
task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates; two authorized executors own disjoint source scopes.

## Validation
Never call Polar even with sandbox settings. Existing tests patch training.billing.polar_request; new adapters must preserve that injection path or explicitly use MockTransport. No secrets in errors/logs. Core pure tests without Django/DB/network; strict core/Django typing and public-only collaboration, common transaction contracts, full regression/concurrency, no unexpected migration. VERIFIED/FAILED/NOT RUN evidence.

## Risks
Webhook pending-marker durability, period-start inclusive/end exclusive, first-seen paid trial history, checkout reuse and server-owned payloads are observable. Provider response dictionaries need careful typed conversion without changing valid behavior or selection order. Avoid cross-module ORM imports, circular bootstrap imports or bypassing test mocks. Shared workspace mandates exclusive file ownership. Git/Docker session restrictions remain; no ACL or execution-policy bypass, alternate indexes, stash/reset/clean or production.
