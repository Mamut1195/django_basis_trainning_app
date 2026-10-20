# ARCH-09 handoff

ARCH-08 is already integrated:24f98532112230640e8a5346dad5e55dcb52627e;218 PostgreSQL/no skips; run fe03da62e81f444facf4eadf1baf0b70,31 source/HEAD hashes checked. MAM-829 Done. Repeating Complete-Arch08 correctly rejects a main later than its reviewed ARCH-07 base. Do not modify that guard or undo the commit.

ARCH-09/MAM-830 implements ADR-002: seven final business applications,28 models and new initial migrations; typed web/API/admin and commands; retired runtime packages. Three disjoint executors implemented persistence, web and bindings; primary orchestrates, reviews and independently verifies.

Local independent gates VERIFIED:111 pure, mypy95/229,8 import contracts, AST/Ruff/Django/no drift/static,224 SQLite tests (five PostgreSQL-only skips),45 route/offline/export compatibility,170 files and61 explicit deletions. Execute from the repository in external PowerShell:

```powershell
& '.\scripts\Complete-Arch09.ps1'
```

The script requires main at24f9853 and an empty index. It verifies using an owned disposable Docker PostgreSQL18.4 container (port55440; override -Port if occupied), requires zero skips, stops it, verifies every source/deletion and commits only the explicit manifest on arch/09-final-modules before fast-forwarding main. seed.py/manage.py are excluded. No push or provider activation. Docker remains unavailable to the assistant process; no credential/ACL/execution-policy changes are requested.

Return the two VERIFIED lines including the main SHA. Primary must inspect actual logs/receipt/container cleanup, manifest/committed absence of retired source and normalized tree/HEAD hashes before marking Done or starting ARCH-10. On error preserve output/logs, do not alter guards, discard work, force history or rerun an already integrated stage. If main already contains this delivery, read it back instead.

Final local evidence: docs/architecture/ARCH-09-VERIFICATION.md, ARCH-09-COMPATIBILITY.json, ARCH-09-FILES.json. Strict coverage/tooling limits: ARCH-09-TYPING.md. Remote CI/browser-device/provider acceptance stays separately NOT RUN until actually executed. ARCH-10 remains pending final architecture and web/offline acceptance after ARCH-09 main readback.
