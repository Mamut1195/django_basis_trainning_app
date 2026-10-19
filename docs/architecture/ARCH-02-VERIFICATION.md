# ARCH-02 / MAM-823 — verification and external completion

Current base: local `main/3fd8978`. ARCH-01 is integrated. ARCH-02 implementation remains uncommitted until the external completion command succeeds and its SHA is checked. The user's latest instruction resumes work and authorizes asking them to run required Git/PowerShell steps externally.

## Confirmed on the current Python candidate

| Status | Check | Result |
| --- | --- | --- |
| VERIFIED | Architecture AST/inventory | No violations, including type-only imports and exact pending-legacy typing frontiers |
| VERIFIED | Pure tests | 25 pass without Django/database/network |
| VERIFIED | Core mypy | 40 source files, zero errors, no Django plugin |
| VERIFIED | Django mypy | 47 source files, zero errors |
| VERIFIED | Import Linter | Eight contracts kept, zero broken |
| VERIFIED | Ruff | No errors |
| VERIFIED | Django check | Zero issues |
| VERIFIED | makemigrations --check --dry-run | No changes detected |
| VERIFIED | Combined SQLite regression | 124 discovered, 121 pass, three PostgreSQL concurrency tests skipped; includes both final compatibility tests and all 13 adapter tests |
| VERIFIED | External PowerShell scripts | Parsed without syntax errors before native invocation was attempted; final parse repeated after review |
| NOT RUN | External-script runtime self-test | Local execution policy prevents running the .ps1; escalation fails helper setup. It runs first in the operator completion script |
| NOT RUN | PostgreSQL regression | Must run all 124 with zero skips using the Docker script |
| NOT RUN | Git commit/main integration | Only operator completion can perform writes in this environment |
| NOT RUN | Remote CI and real browser/offline devices | No claim from SQLite or server tests |

No new product behavior or schema is intended. Six exact legacy modules remain outside strict body checking while their symbols support the typed adapters; they are explicitly listed in mypy-django.ini and legacy-pending.json. The checker prevents broadening to global/wildcard exceptions. Legacy model validation and access checks still run through two documented typed bridges. Later module stages must remove those bridges/frontiers.

## Operator command

Run in external PowerShell from the same Windows account that integrated ARCH-01:

```powershell
& 'C:\Users\Jonnathan\Mamut system\django-basis-trainning-app\scripts\Complete-Arch02.ps1'
```

The command first checks main/base and that the index has no pre-existing staged changes. It tests stdout/stderr capture against real success/failure exits, then repeats architecture/types/lint/Django checks, creates a uniquely named PostgreSQL 18.4 Docker container bound only to 127.0.0.1:55440, and runs the full regression. It requires 124 successful tests with zero skips. The container uses no host/production volume and is stopped in finally; --rm removes that container and its anonymous volumes. No paid provider or production service is activated.

The scripts use hidden native processes with separate stdout/stderr logs and real ExitCode checks. Normal Django stderr no longer becomes a PowerShell NativeCommandError. This mechanism still requires its runtime self-test to pass externally; local syntax validation is not proof of runtime success.

Source hashes are taken before/after verification, with strict UTF-8/BOM/CRLF normalization so ordinary Git newline conversion does not invalidate equivalent source. Runtime inputs, both operator scripts and the explicit file manifest are bound to the receipt. The expected manifest is `ARCH-02-FILES.json`; seed.py/manage.py are excluded. A passing result is written to `ARCH-02-RESULT.json`, and logs/failed receipts remain under `.cache/arch02/<run-id>/`.

Only after successful checks and container cleanup does the completion script create `arch/02-execution`, stage the explicit manifest, check staged scope/whitespace/file completeness and source hashes, commit, and fast-forward main. It preserves existing user edits and stops at errors without reset/stash/clean/history rewriting. No push occurs. Integration receipt: `.cache/arch02-integration.json`. Return its printed main SHA to Codex for independent readback and Linear closure. Do not start ARCH-03 until this verification/integration is confirmed.

Docker behavior follows the [official run reference](https://docs.docker.com/reference/cli/docker/container/run/) and [official PostgreSQL image documentation](https://github.com/docker-library/docs/blob/master/postgres/README.md).

## Final integration readback, 2026-10-19

VERIFIED after external execution: main/2f3c95ebefedfcc082cdc074aaafefd4efc1aaa5. Receipt docs/architecture/ARCH-02-RESULT.json, run b218c860b7314a47b5d6b1803c666836: PostgreSQL 18.4, 124 tests, zero skips, stopped container. Actual logs contain Ran 124 tests and standalone OK. All receipt source hashes match both the working tree at readback and HEAD blobs with its documented UTF-8/line-ending normalization. ARCH-02/MAM-823 is Done; ARCH-03/MAM-824 is In Progress. Earlier pending-state notes above are historical.
