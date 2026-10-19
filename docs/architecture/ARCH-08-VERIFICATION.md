# ARCH-08 verification - 2026-10-19

Candidate based on main/105ac188be24fbd960a1bf6941dbafa3104455ee, with ARCH-07 integrated and Done. ARCH-08/MAM-829 remains In Progress. Two implementers delivered disjoint core/receipts and wire/web scopes; primary coordinated contracts, reviewed and independently verified the aggregate. No ARCH-08 PostgreSQL result or commit is claimed.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED |105 tests, including14 sync cases; no Django/DB/network |
| Core strict typing | VERIFIED |89 source files, no Django plugin |
| Django strict typing | VERIFIED |140 files, including newly certified training/services.py |
| AST/public/inventory | VERIFIED | Type-only imports checked; pending legacy inventory reduced by1 |
| Import Linter | VERIFIED | eight kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django checks / schema | VERIFIED | Zero issues; makemigrations --check --dry-run: no changes |
| SQLite regression | VERIFIED |218 tests,213 passed and five PostgreSQL-only skips |
| Static assets | VERIFIED | collectstatic --noinput |
| Differential parity | VERIFIED |23 cases against exact integrated coordinator, zero differences; unchanged offline assets |
| PowerShell syntax | VERIFIED | Native parser: zero errors in both scripts |
| Scope/source stability | VERIFIED |31-file manifest; tested normalized hashes stable; original seed.py/manage.py excluded |
| PostgreSQL / native capture execution | NOT RUN | External gate requires218 tests/no skips and stopped owned container |
| Main integration / remote CI | NOT RUN | Actual commit/receipt/log/hash readback still required |
| Real browser/device offline acceptance | NOT RUN | API/wire compatibility is verified; real browser/device acceptance remains ARCH-10 |
| Providers / production | NOT RUN | No provider requests, paid calls or activation |

Actual stdout/stderr and exit codes for all ten combined gates are in `.cache/arch08-local/receipt.json`. The independent `.cache/check_arch08_parity.py` loads exact `HEAD:training/services.py`, uses a new SQLite test database, synthetic accounts and controlled clock, and compares outcomes, persisted session snapshots and receipt digests/results. It covers18 operation cases and5 replay/queued-completion scenarios, including expired access, later current-state changes, malformed late data, different-payload reuse, stale/completed conflicts and original client child IDs across queued revisions. [Parity receipt](ARCH-08-PARITY.json). The offline JavaScript/template content is unchanged from the integrated baseline.

## Implementation and contracts

Sync now owns typed operation identity, digest/receipt values and explicit transaction coordination. Its source port splits identity/hash, revision/shape and session-change conversion around the original guards. Execution rules remain in training through its public contract. Receipt persistence owns only SyncReceipt and receives snapshot encoder/decoder by injection; bootstrap alone connects account locks, commercial authorization, training execution and codecs. Core contracts contain no ORM, HTTP, Any, free JSON or opaque serialized payload.

The exact order remains account lock, identifier parsing/canonical hashing, receipt lookup/digest replay, authorization, top-level shape/revision validation, training owner/revision guards, deferred child conversion, session persistence, receipt persistence and outer commit. Duplicate owner locks and authorization inside the existing training case remain. Replay returns the saved result even after access expires or the current session changes/completes. Canonical hashing retains sorted compact JSON, default ASCII escaping and numeric/null distinctions. Existing400/403/409 details, account queue scope, session authentication and CSRF remain unchanged.

Five shared fake/Django receipt contracts cover owner/mutation scope, commit, uncommitted/exception rollback and frozen snapshots with block IDs/order, Decimal scales, missing values and zero. Fourteen pure tests also cover source/guard ordering, conflicting digests and rollback after a real Training case commits inside an outer fake UoW. Eleven Django receipt tests include rollback of both new and existing session/children after receipt-save failure, original snapshot replay, owner-independent keys, and a new PostgreSQL-only competing-revision race. The existing same-mutation race remains in regression. Eight wire/HTTP cases cover raw canonicalization/deferred conversion, snapshot fidelity, exact existing IndexedDB envelope including created, replay and web security/errors.

## Typing boundary and remaining legacy

One new precise third-party exception is registered here: `basis/modules/sync/adapters/web.py:9` ignores only `import-untyped` for DRF PermissionDenied. The installed DRF package lacks typing metadata; this HTTP adapter preserves its existing exception/detail response without importing it into core or suppressing adapter-body analysis. No global or wildcard exclusion was added. ARCH-06's separate local DRF authorization import exception remains unchanged.

training/services.py is now fully in strict scope and leaves pending inventory. Its retained compatibility helpers are typed; a narrow Callable cast preserves the still-untyped legacy Block.save override and real validation behavior. The only remaining exact silent mixed legacy frontiers are training.models and daily_trainning_app.models. Keep existing SyncReceipt/Conflict compatibility aliases until ARCH-09, including the original receipt-save mock seam. No schema or offline asset change was made. ADR-002 still requires removing daily_trainning_app and reorganizing final models/apps/schema/migrations in ARCH-09, with empty-database/final acceptance in ARCH-10.

## Integration gate

Run scripts/Complete-Arch08.ps1 externally. It checks main/base/empty index, self-tests native stderr/nonzero capture, repeats controls, uses its own temporary Docker PostgreSQL18.4 without host volumes, requires218 tests/zero skips, stops the container, records source hashes and commits only31 manifest paths on arch/08-sync before fast-forwarding main without push. Receipt: ARCH-08-RESULT.json; integration: .cache/arch08-integration.json. Independent SHA/logs/receipt/stopped-container/source-and-HEAD hash/completeness readback is required before MAM-829 Done or ARCH-09.
