# ARCH-03 verification - 2026-10-19

Candidate on main/2f3c95e, not committed. MAM-824 remains In Progress. ARCH-04 has not started.

| Check | Status | Evidence |
|---|---|---|
| Pure domain/application | VERIFIED | unittest discover: 39 tests, no Django/DB/network |
| Core strict typing | VERIFIED | mypy-core.ini: 52 files; no plugin |
| Django strict typing | VERIFIED | mypy-django.ini: 68 files |
| Layer/public and inventory | VERIFIED | scripts/architecture_check.py |
| Import Linter | VERIFIED | 8 kept, zero broken |
| Ruff | VERIFIED | ruff check . |
| Django checks | VERIFIED | manage.py check |
| Schema stability | VERIFIED | makemigrations --check --dry-run: no changes |
| Regression SQLite | VERIFIED | 139 discovered, 136 passed, 3 PostgreSQL-only concurrency skips |
| Diff hygiene | VERIFIED | Git diff with cr-at-eol, preserving historical CRLF files |
| PostgreSQL candidate | NOT RUN | External Docker script must require all 139 tests with zero skips |
| Native capture self-test | NOT RUN | Child PowerShell refused scripts under its execution policy; no bypass attempted |
| Script syntax | VERIFIED | Native PowerShell parser: zero errors in both scripts |
| Main integration | NOT RUN | External completion script; independent receipt/HEAD readback required |
| Remote CI / LIVE mail / production | NOT RUN | No external mail, paid calls or production changes |

Shared identity contract runs against memory and Django: inactive three-row enrollment, rollback on mail error, read-versus-confirm activation. Additional tests cover exact expiry of fixed windows; denied-attempt counting; non-enumerating resend/recovery; expired/mismatched signed claims; original Django one-use recovery token; hashed registration; explicit linking without verification; owner-scoped writes; zero/null observations; immutable RM; catalog staff policy/archive/protected delete and malformed JSON without coercion.

Existing web/private/offline/history scenarios remain in the full regression, including CSRF, foreign owners, partial updates, as-of RM references, retry/conflict and outer receipt rollback. Strength formulas, snapshot references, generic read querysets and Django model registration remain at documented compatibility boundaries for ARCH-05/09; this stage introduces no tables or programs feature.

The six exact legacy typing frontiers remain pending. Protocol casts in athlete/catalog persistence are signature bridges to real full_clean/save hooks; no new silent-import override or Any exception was added. Existing seed.py (168 additions/56 deletions) and manage.py mode change are excluded from the integration manifest.

External command: scripts/Complete-Arch03.ps1. It checks the reviewed base and empty index, runs its stderr/nonzero-exit self-test, repeats all local gates, creates its own PostgreSQL 18.4 Docker container with no host volume, requires139 successful tests/no skips, stops the owned container in finally, checks source hashes and integrates only the explicit manifest on a dedicated branch. Logs remain in .cache/arch03; receipt becomes docs/architecture/ARCH-03-RESULT.json. No push.

Final local run: all nine checks VERIFIED in .cache/arch03-local/receipt.json. Separate stdout/stderr logs preserve actual native exit codes; the SQLite log confirms Ran139 tests / OK(skipped=3), and pure log confirms Ran39 / OK. Normalized source hashes are bound to the explicit50-file manifest. Native PowerShell parsing found zero errors; executing the script self-test externally remains required. Linear readback confirms MAM-823 Done and MAM-824 In Progress after appending this candidate's evidence.

## Final integration readback

VERIFIED main/ddcf178d6a5c8c4793e3672a95dbf64fdffe2b91; run ac42bce0ac9a4fc795271b758fbf0959. Actual PostgreSQL logs confirm139 tests and standalone OK, no skips. Receipt has all checks exit0 and container_stopped true; all normalized source hashes match working tree and HEAD; all50 manifest files exist in the commit. MAM-824 marked Done only after this check, then MAM-825 started. Earlier pending notes are historical.
