# ARCH-03 resume - 2026-10-19

ARCH-02 is integrated at main/2f3c95ebefedfcc082cdc074aaafefd4efc1aaa5 and MAM-823 is Done. Its PostgreSQL receipt/logs/source hashes were independently verified. MAM-824 is In Progress; the ARCH-03 candidate is local. Do not start ARCH-04 before the next integration is checked.

Read docs/architecture/ARCH-03-PLAN.md and ARCH-03-VERIFICATION.md. Local checks: 39 pure tests, core52/Django68 typed files, eight import contracts, Ruff, Django checks/no migrations; SQLite139 with three PostgreSQL-only skips. Shared fake/Django identity transaction contract and 15 new integration tests are included.

Git writes and Docker engine access remain unavailable to Codex; user explicitly agreed to run necessary PowerShell commands externally. Do not repeatedly retry, modify ACLs, bypass execution policy, use alternate indexes/checkouts, stash/reset/clean, or touch original data. Child PowerShell here refused scripts under its execution policy. Keep that runtime gate explicit.

Once syntax/local checks are recorded, the external operator command is:

```powershell
& 'C:\Users\Jonnathan\Mamut system\django-basis-trainning-app\scripts\Complete-Arch03.ps1'
```

This command requires main at the reviewed ARCH-02 base and an empty index. It runs a process-capture self-test, all gates and PostgreSQL18.4 Docker139 tests with zero skips; stops its own container; then stages only ARCH-03-FILES.json, commits on arch/03-identity and fast-forwards main. No push. seed.py/manage.py remain excluded and preserved. Logs and integration receipt stay in .cache/arch03 and .cache/arch03-integration.json.

After the operator returns the SHA: read actual logs/receipt, require139 tests/no skips/stopped container, verify every normalized source hash against the current tree and HEAD blobs, check commit completeness and only then mark MAM-824 Done and begin ARCH-04. On failure, preserve logs/tree and diagnose the exact failed gate; no destructive recovery.
