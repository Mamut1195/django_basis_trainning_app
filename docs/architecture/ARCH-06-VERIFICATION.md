# ARCH-06 verification - 2026-10-19

Local candidate based on main/e3ffcf66deb3e8138dfa57d6773a400c3a87426e. MAM-827 remains In Progress; no ARCH-06 commit/main integration or PostgreSQL result is claimed. Two implementers delivered disjoint core/persistence and Polar/web scopes; primary coordinated contracts, reviewed behavior and independently ran combined checks.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED |72 tests, including11 new billing tests; no Django/DB/network |
| Core strict typing | VERIFIED |70 files, no Django plugin |
| Django strict typing | VERIFIED |102 files; access/billing facades and reconciliation command now explicitly certified |
| Architecture/public/inventory | VERIFIED | AST including type-only imports; pending inventory reduced by3 |
| Import Linter | VERIFIED | eight kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django checks | VERIFIED | check: zero issues |
| Schema | VERIFIED | makemigrations --check --dry-run: no changes in this stage |
| SQLite regression | VERIFIED |180 discovered,177 passed; three PostgreSQL-only concurrency skips |
| Static assets | VERIFIED | collectstatic --noinput |
| PowerShell syntax | VERIFIED | Native parser: zero errors in both scripts |
| Source stability | VERIFIED | Normalized source hashes unchanged during final combined run |
| Linear scope amendment | VERIFIED | Epic/project and ARCH-09/10 updated and read back; ARCH-06 remains In Progress |
| PostgreSQL / native process-capture self-test | NOT RUN | External scripts require all180 Django tests/no skips and stop owned container |
| Main integration / remote CI | NOT RUN | External reviewed commit and independent readback still required |
| LIVE providers / production | NOT RUN | No provider call, payment or production activation |

Ten combined local checks, actual exit codes and separate stdout/stderr are recorded in `.cache/arch06-local/receipt.json`. A preliminary run overlapped the implementers' final fixture correction and TransactionTestCase addition; its transient failure and179-test discovery are preserved in `.cache/arch06-local-inflight`. The final frozen candidate passed180 tests as above; this is the acceptance run for local checks.

## Implementation and behavior

Commercial values/policies and typed checkout, portal, reconciliation and access cases now live under billing domain/application. Persistence is behind specific repository/receipt ports, a narrow public athlete identity projection and explicitly composed UoW/clock/provider dependencies. Core webhook results express business outcomes; the web adapter maps them to existing200/422/503 responses. The signature adapter authenticates bytes before creating an application command. No ORM/HTTP/free JSON enters core contracts.

Access retains inclusive start/exclusive end, pending reconciliation denial and read/export availability after expiry. Checkout retains server-selected USD5 monthly/exclusive tax/native7-day trial, verification before account creation, cached links and trial history. Reconciliation retains identity/product scope, existing billing row locks across bounded provider GET and raw ISO-string ordering of subscriptions. Calendar errors are deferred until selecting the relevant subscription and date, preserving the old behavior for ignored subscriptions. Checkout/portal URL validation and payloads are unchanged.

Shared memory/Django repository tests cover explicit commit, owner isolation, uncommitted creation and exceptions even after requesting commit. New real persistence tests cover partial-save checkout rollback and durable webhook failure/retry/replay. A TransactionTestCase runs without an outer test transaction: the provider observes pending state/receipt inside the reconciliation transaction; after its failure and rollback the outer code is again in autocommit and the previously committed marker/receipt remain persisted.

Nine provider and six web/command tests use injected fakes and HTTPX MockTransport only. They verify payloads,30-minute default/absent invalid expiry, URL allowlist, numeric-string rejection, raw period ordering, ignored calendar errors, bounded20-second transport/no retry, generic errors, signature, unlinked identities, unknown events, pending durability/retry/replay, reconciliation command and login/CSRF. The original `training.billing.polar_request` patch seam remains effective; no network call occurs in regression.

## Boundaries and final structure

Three fully typed compatibility entry points leave the pending inventory: training/access.py, training/billing.py and the reconciliation command. Three exact mixed legacy frontiers remain: training.models, daily_trainning_app.models and training.services. One local DRF import exception is recorded in [typing exceptions](ARCH-06-TYPING-EXCEPTIONS.md); no broad exclusion was added.

ADR-002 records the user's updated goal: ARCH-09 removes daily_trainning_app and reorganizes final models/apps/schema/migrations; ARCH-10 verifies the final structure from an empty temporary database. Keeping the schema stable in this stage is temporary staging, not final acceptance. Original seed.py168 additions/56 deletions and manage.py mode are excluded from the43-file manifest and integration.

## External integration gate

Run scripts/Complete-Arch06.ps1 from external PowerShell. It checks main/base/empty index, self-tests native stderr and failing exit capture, repeats gates, runs all180 tests on an owned temporary Docker PostgreSQL18.4 container without host volumes, checks zero skips, stops the container and records source hashes/receipt. It commits only the explicit43-file manifest on arch/06-billing and fast-forwards main without push. Receipt: ARCH-06-RESULT.json; integration: .cache/arch06-integration.json. Only actual SHA/logs/hashes/committed completeness readback can close MAM-827 or start ARCH-07.

## Main integration readback - 2026-10-19

Earlier local-candidate/NOT RUN integration notes are historical. VERIFIED main/c5cc0c17d7f3070c81950a89ea8ccbdcdde696e6,180 PostgreSQL tests/no skips, actual logs standalone OK, every gate exit0, owned container stopped. ARCH-06-RESULT.json and .cache/arch06-integration.json agree on run136ec5dcf05f42d5b705540d62a6b9ad. All43 manifest paths exist in HEAD and every recorded normalized source hash matched both tree and HEAD before starting ARCH-07. MAM-827 Done. Remote CI/LIVE providers remain NOT RUN.
