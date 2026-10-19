# ARCH-07 verification - 2026-10-19

Local candidate based on main/c5cc0c17d7f3070c81950a89ea8ccbdcdde696e6. ARCH-06 is integrated and Done. ARCH-07/MAM-828 remains In Progress; no ARCH-07 commit or PostgreSQL result is claimed. Two implementers delivered exclusive jobs/budget and context/provider/proposals scopes; the primary coordinated contracts, reviewed behavior and independently verified the aggregate.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED |91 tests, including13 jobs and6 proposal tests; no Django/DB/network |
| Core strict typing | VERIFIED |85 files, no Django plugin |
| Django strict typing | VERIFIED |129 files, including three newly certified compatibility entry points |
| Architecture/public/inventory | VERIFIED | AST including type-only imports; pending inventory reduced by3 |
| Import Linter | VERIFIED | eight kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django checks | VERIFIED | zero issues |
| Schema | VERIFIED | makemigrations --check --dry-run: no changes in this stage |
| SQLite regression | VERIFIED |199 tests,195 passed and four PostgreSQL-only skips |
| Static assets | VERIFIED | collectstatic --noinput |
| Differential compatibility | VERIFIED |40 cases:8 context/roundtrip,12 request serialization/errors,20 settlement values/errors; zero differences against exact integrated baseline |
| PowerShell syntax | VERIFIED | Native parser: zero errors in completion and verification scripts |
| Diff/scope | VERIFIED |53-file manifest; original seed.py/manage.py excluded |
| PostgreSQL / native capture execution | NOT RUN | External gate requires all199 tests/no skips and stopped owned container |
| Main integration / remote CI | NOT RUN | Actual commit/receipt/log/hash readback still required |
| LIVE providers / production | NOT RUN | No network provider request, paid call or activation |

Ten aggregate gates and actual stdout/stderr/exit codes are recorded in `.cache/arch07-local/receipt.json`. Sources are hash-bound to the explicit manifest and must remain unchanged for external verification. The differential script `.cache/check_arch07_parity.py` reads exact `HEAD:training/ai.py` at the baseline SHA and uses a new SQLite test database, a fixed clock and synthetic owned/private accounts. It compares serialized context/message strings and settlement database state/errors, including partial token capture, wrong counts, incomplete answers, NULL answers and unexpected top-level JSON. See [parity receipt](ARCH-07-PARITY.json).

## Extracted behavior

Coach context is a real typed snapshot of public athlete, catalog and training projections, with Decimal/date/optional values. JSON freezing and HTTP serialization stay in adapters; core accepts no free JSON, ORM, request or opaque serialized context. Original message/system prompts, key insertion order, numeric/date conversion and UTF-8 byte budget remain unchanged. Other modules expose narrow public contracts; account and billing locks are composed explicitly rather than querying foreign models from coach.

Typed jobs coordinate enqueue, claim, settle and stale quarantine. Keep fund/account/billing/usage enqueue locks and fund/account/job/usage settlement locks, idempotency before entitlement/budget, exact reservations/rates/rounding, trial lifetime/monthly global fund and paid-period separation. Raw selected-plan spelling and delayed validation are preserved, including string zero versus absent numeric zero. Timeout/crash retains reservation and never retries. Period or trial-month rollover releases the reservation without a provider call. The PostgreSQL claim test uses two connections and a barrier while row locks remain held, requiring distinct jobs via skip_locked; it remains NOT RUN until the external PostgreSQL gate.

Shared fake/Django job repository contracts cover owner/ID preservation, explicit commit, uncommitted/exception rollback and claim-once behavior. Additional cases cover quotas, byte-budget failure rollback, rollover, stale quarantine, partial response capture and double-settlement prevention. Six real job repository tests include one PostgreSQL-only claim race. Thirteen edge tests exercise frozen/authorized context, provider MockTransport/payloads, definite versus ambiguous errors, malformed response phases, circuit breaker and proposal lifecycle. Existing personal/global budget races and offline concurrency regression remain included.

Proposal create/edit/reject/accept are typed cases using the common ARCH-04 PlanDefinition/planning contract. Persistence adapters bind original incoming JSON per operation, verify it matches the validated definition and retain exact optional-key omission/numeric spelling. Accepted replay remains idempotent, owner/version guards are preserved, edited content rolls back on stale versions and no execution/results are invented. Already accepted/rejected content is not newly decoded during status-only operations. Web bindings delegate these rules rather than duplicating them.

## Legacy findings and boundaries

Two provider-response defects were confirmed and recorded in existing functional tickets MAM-635/MAM-818 without changing their states: valid usage plus content=null causes NOT NULL/IntegrityError, rolling back settlement and retaining running state/reservation; truthy non-object top-level JSON escapes with AttributeError, leaving running state for later quarantine. This migration explicitly preserves both with tests instead of silently changing accounting/retry behavior. Functional remediation waits until architecture acceptance.

training/ai.py, training/proposals.py and process_ai_jobs.py now enter explicit strict Django scope and leave the pending inventory. Three existing mixed silent legacy frontiers remain: training.models, daily_trainning_app.models and training.services. No new third-party typing exception or broad exclusion was added; ARCH-06's precise DRF exception remains unchanged. Generic template/admin/query integration and final app registration belong to ARCH-09. ADR-002 requires daily_trainning_app removal and permits final app/schema/migration reorganization there; ARCH-10 verifies the final empty-database structure.

## Integration gate

Run scripts/Complete-Arch07.ps1 externally. It verifies main/base/empty index, self-tests native stderr/nonzero capture, repeats all controls, creates its own temporary Docker PostgreSQL18.4 without host volumes, requires199 tests/zero skips, stops the container, binds source hashes and commits only53 manifest paths on arch/07-coach before fast-forwarding main without push. Receipt: ARCH-07-RESULT.json; integration: .cache/arch07-integration.json. Done and ARCH-08 require independent SHA/logs/receipt/stopped-container/normalized tree-and-HEAD hashes and completeness readback. No unrelated user work is staged.
