# ARCH-05 verification - 2026-10-19

Candidate on main/20cc32ca25a905cbb20a3e6707d92ae74797c573, not integrated. MAM-826 In Progress; ARCH-06 not started. Two executors completed disjoint implementation; primary orchestrated contracts/configuration, source review and independent integration verification.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED |61 tests, no Django/DB/network |
| Core strict typing | VERIFIED | mypy-core.ini65 files, no Django plugin |
| Django strict typing | VERIFIED | mypy-django.ini87 files including two certified legacy facades |
| Architecture/public/inventory | VERIFIED | AST checker including type-only imports; pending inventory reduced by2 |
| Import Linter | VERIFIED | eight kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django checks | VERIFIED | check passes |
| Schema | VERIFIED | makemigrations --check --dry-run: no changes |
| SQLite regression | VERIFIED |158 discovered,155 pass; three PostgreSQL-only skips |
| Differential arithmetic/errors | VERIFIED |1326 strength +562 sport +50 pace +90 load cases; zero differences from exact HEAD baseline |
| Diff and explicit manifest | VERIFIED |39 files; normalized source hashes unchanged; original EOL/user files preserved |
| PowerShell syntax | VERIFIED | Native parser: zero errors in both scripts |
| PostgreSQL / native capture self-test | NOT RUN | External command must require all158 tests/no skips and stop owned Docker container |
| Main integration / remote CI | NOT RUN | Explicit external commit and independent readback required |
| Production / LIVE providers | NOT RUN | No activation or provider call; user confirms no production |

All nine local gates are recorded with separate stdout/stderr logs and actual exit codes in .cache/arch05-local/receipt.json. The differential script .cache/check_arch05_parity.py reads exact integrated baseline source from Git and compares values/errors with current compatibility adapters, using three Decimal contexts and malformed/optional/numeric cases. Results are recorded in ARCH-05-PARITY.json. It found two fractional-duration rounding differences before acceptance; original Decimal string conversion was restored and boundary regressions also preserve missing-value short circuit. No formula, metric version, rounding policy or intentional behavior change.

Shared memory/Django progress contract verifies committed trips/readback without invented measurements. Added integration covers interval non-double-counting, first-observed sport/protocol order, timezone-aware replacement-date cutoff and completed history, owner-scoped trip/stage reads/writes, valid cycle hierarchy, HTTP forms, transaction rollback, loose numeric/error precedence and unsaved model conversions. Pure tests cover overflow/finite/ranges/effort eligibility, historical RM matching/frozen absence and typed sports/trekking invariants. Existing148 scenarios remain in the158-test full regression.

Two complete facades, training/domain.py and daily_trainning_app/strength_metrics.py, now enter strict Django scope and leave legacy-pending.json. Four exact legacy frontiers remain: training.models, training.access, daily_trainning_app.models, training.services. No new silent import, Any exception or broad exclusion. Model/query/form/view wrappers stay infrastructure pending later cleanup; historical RM reference queries and partial-save semantics remain stable. All new core values/ports avoid Django/ORM/HTTP/free JSON.

Original seed.py168 additions/56 deletions and manage.py mode are excluded. scripts/Complete-Arch05.ps1 repeats all gates, self-tests native stderr/nonzero exits, creates temporary PostgreSQL18.4 Docker without host volume, requires158 successful tests/no skips, stops the owned container, hashes reviewed sources, commits only explicit scope on arch/05-metrics and fast-forwards main. It writes ARCH-05-RESULT.json and .cache/arch05-integration.json, without push. Done requires actual main SHA, logs, receipt/source/HEAD hashes and completeness readback. ARCH-06 waits for that gate.

Final readback: nine canonical local gates succeeded; source hashes unchanged after tests and bound to39-file manifest. Four legacy typing frontiers remain. Only expected external ARCH-05-RESULT.json is missing before PostgreSQL. Original user diff remains seed.py168 additions/56 deletions and manage.py mode.
