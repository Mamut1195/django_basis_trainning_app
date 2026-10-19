# Goal

Extract offline operation validation, idempotency receipts, revisions and conflict coordination into strict typed sync cases. Preserve canonical hashing, retry/409 behavior and existing IndexedDB queues. Session changes and receipt must commit or roll back together through explicit Django UoW.

# Context

ARCH-07 independently verified in main/105ac188be24fbd960a1bf6941dbafa3104455ee:199 PostgreSQL tests/no skips, stopped container,53 committed files and all normalized tree/HEAD hashes; run524117c46a6149878edce8c22d124277. MAM-828 Done; ARCH-08/MAM-829 In Progress. Legacy training/services.py sync_session locks the account, parses IDs, hashes original payload, checks receipts, authorizes and validates shape, then delegates execution and stores a receipt. API maps owner scope/CSRF/errors/conflict. Execution already exposes typed Training.record_from and preserves revision/owner guards before deferred payload conversion.

# Constraints

Keep exact sorted compact JSON SHA256 canonicalization (including default ensure_ascii/numeric distinctions), owner-scoped mutation keys and original result snapshots. Replay must happen before current entitlement and late shape/revision/body validation, while identifier validity still precedes replay. Keep account then session lock order, current repeated owner/auth guards, new revision zero, immutable completed sessions, conflict-current payload and valid old queued bodies. No Any/free JSON/HTTP/ORM/opaque serialized payload in core; dataclass commands/results and concrete Protocol ports with deferred boundary conversion.

No schema, queue schema, asset behavior or feature changes. ADR-002 still requires final daily_trainning_app removal and app/model/schema/migration reorganization in ARCH-09; stable schema here is temporary staging. Preserve unrelated seed.py/manage.py. Use temporary databases, no providers/credentials/production, Git writes/ACL changes/execution-policy bypass, stash/reset/clean or history rewriting.

# Affected areas

sync domain/application/adapters/public, explicit bootstrap/sync, narrow public training execution/receipt-snapshot contracts as needed, account lock and billing authorization composition, legacy services facade and sync API handler, tests and verification/CI metadata. Training rules stay in training; sync does not query foreign ORM or import foreign adapters. Receipt persistence owns only SyncReceipt. Original receipt JSON stays at adapters; replay returns a typed recorded session snapshot without reconstructing current database state.

# Implementation steps

1. Core/receipt executor owns sync/domain/operations.py, application/operations.py, adapters/receipts.py, shared fake/Django transaction/receipt tests. Define exact contracts with sibling early: typed mutation identity/digest, deferred source identity/revision/changes port, synchronization command/result, receipt repository and training record port using training.public types. Core locks owner inside outer UoW before source identity conversion, checks saved digest/result before authorization/late validation, records execution and receipt in one UoW. Receipt JSON codec implemented via injected typed boundary conversion, never importing training adapters from sync.
2. Wire/web executor owns sync/adapters/wire.py and web.py, bootstrap/sync.py, training/services.py facade, sync section training/views.py and any narrow training-owned snapshot decoder/recorder bridge. Own canonical/HTTP/queue compatibility and regression tests. Preserve raw payload hash and deferred conversion guards; use explicit bootstrap to inject own-module training adapter implementations. Fully type the remaining services helpers/wrappers without changing them, or report concrete frontier blockers; remove no used compatibility symbol silently. Do not edit core/receipt files/public/config.
3. Primary orchestrates and reviews; owns shared identifier/public export integration, strict scope/inventory/CI, documentation/scripts and independent differential checks. Two implementers only, disjoint files, no children. Existing account lock/billing authorization public contracts are reused.
4. Verify pure replay/different-payload/late validation/owner and revisions, shared fake/Django receipt commit/rollback/frozen-result/owner contracts, actual rollback after receipt-save failure (including an inner committed execution), PostgreSQL same-mutation and competing revision races, HTTP session/CSRF/400/403/409, decimals/dates/missing/zero and unchanged old queue format. Preserve all199 regression tests. No real browser/device claims from API-only tests.
5. Joint strict core/Django typing, AST/public/inventory/import, Ruff, Django/no unexpected migrations/static, full SQLite and temporary Docker PostgreSQL. Prepare reviewed manifest/external scripts, require zero skips on PostgreSQL and stopped owned container, then independent main SHA/log/receipt/hash/completeness readback before Done or ARCH-09.

# Required skills

task-planning, safe-git-workflow, verify-before-complete. Primary orchestrates; two authorized agents implement.

# Validation

Use VERIFIED/FAILED/NOT RUN and actual stdout/stderr/exit codes. Core tests import without Django/settings/network. Compare exact baseline canonical digests/results/errors on a temporary database; test source/hash stability after freeze. Expose no provider/credential content or private foreign-owner snapshot. Validate unchanged offline asset bytes and explicitly distinguish browser/device coverage left to ARCH-10.

# Risks

Eager JSON decoding before receipt lookup changes replay behavior; parsing changes numeric-string/zero semantics and conflict precedence. Encoding a stored snapshot from current rows loses original receipt history. Nested execution commit must still roll back if outer receipt save fails. Returning a domain SessionState must preserve child IDs/order and decimal/date wire values. Existing services helpers remain compatibility symbols even where current callers have moved; certify them without unrelated business changes and defer retirement to ARCH-09. Record newly discovered legacy defects in functional tickets rather than silently fixing them.
