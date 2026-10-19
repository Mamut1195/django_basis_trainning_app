# ARCH-06 candidate and final architecture amendment

## Current state

main/e3ffcf66deb3e8138dfa57d6773a400c3a87426e contains verified ARCH-05,158 PostgreSQL tests/no skips. ARCH-06/MAM-827 has a locally verified candidate from two implementers with primary orchestration. No ARCH-06 commit/main integration or PostgreSQL result yet. ARCH-07 must wait.

User explicitly authorizes removing daily_trainning_app in ARCH-09 and reorganizing apps/models/schema/migrations; no production exists. ADR-002 and Linear epic/project, ARCH-09 and ARCH-10 contain the new scope. Do not preserve the legacy package solely for old migrations. Do preserve unrelated user edits and use temporary databases for schema tests.

## Verified candidate

72 pure tests; strict mypy70 core/102 Django files; eight import contracts; AST/public/legacy inventory; Ruff; Django checks/no migration changes; static collection;180 SQLite tests with three PostgreSQL-only skips; native PowerShell parser zero errors; source hashes stable. Evidence: architecture/ARCH-06-VERIFICATION.md and .cache/arch06-local/receipt.json. Preliminary in-flight logs remain separately preserved. New tests cover provider mocks, exact payloads, webhook signatures/replay/durable pending retry, UoW/owner isolation, access and checkout policy. No LIVE provider calls or credentials exposed.

## Next operation

From the repository's external PowerShell session:

```powershell
& '.\scripts\Complete-Arch06.ps1'
```

Optional `-Port 55441` if the default loopback55440 is occupied. The script refuses an unexpected base, staged work, scope/hash changes, nonzero native exits, test skips or cleanup failure. It self-tests capture, uses its own temporary PostgreSQL18.4 Docker container without host volumes, then commits the43-file explicit manifest and fast-forwards main without push. Do not bypass a failed gate or change ACL/execution policy to recover automatically. Keep errors/logs for diagnosis.

Expected final messages:180 PostgreSQL tests, zero skips, receipt architecture/ARCH-06-RESULT.json and an ARCH-06 main SHA. Return the SHA or error. The coordinator must independently check logs, receipt/integration run, stopped container, manifest completeness and normalized tree/HEAD hashes before marking MAM-827 Done and starting ARCH-07.

## Preservation and limits

seed.py168 additions/56 deletions and manage.py mode remain outside the delivery. Do not stash, reset, clean, force-push, rewrite history or discard unknown files. Current Git/Docker session restrictions are worked around only through the external operator workflow. Remote CI, PostgreSQL candidate acceptance, native capture execution and main integration are NOT RUN in this session. Final schema/package relocation remains ARCH-09, acceptance ARCH-10. Functional tickets retain IDs/history and epic blockers.
