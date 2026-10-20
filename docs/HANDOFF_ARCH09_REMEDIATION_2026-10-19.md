# Resume BASIS architecture remediation

## Current authority

main337f12d8d6b78d52c77c3e7e821ab2af1351cdc8 is the first structural ARCH-09 delivery. MAM-830 was reopened after confirmed architectural bypasses; MAM-831 acceptance remains open. The corrected candidate now has active config, retired old packages, actual typed business cases/ports/UoW and strict tests/regression. See docs/architecture/ENTRYPOINTS.md and ARCH-10-AUDIT.md.

## Operator command from repository PowerShell

```powershell
& '.\.venv-win\Scripts\python.exe' '.\scripts\arch09_remediation.py' complete
```

This runs the final manifest/gates, disposable Docker PostgreSQL18.4, real browser and exact scoped commit/fast-forward main. Return the final VERIFIED line/SHA or exact failure. Logs/receipts remain under .cache/arch09-remediation and .cache/arch09-remediation-launch. No push and no original DB mutation.

If services passed and Git alone failed, after reviewing the retained error use:

```powershell
& '.\.venv-win\Scripts\python.exe' '.\scripts\arch09_remediation.py' complete --resume
```

Resume never assumes success: it checks the original receipt/logs/cleanup, frozen source hashes and main/candidate state. Do not modify base guards, sources or test counts to force a pass. No reset/stash/clean/force/ACL/execution-policy changes.

## Protected work

seed.py is the user's pre-existing edit and must remain excluded. manage.py content now activates config and belongs to this delivery; preserve original index mode100755 and do not change its working-file mode. Retired seed imports are not an installed application; seed_demo is the supported gated development fixture.

## Independent continuation after operator success

Read main SHA/parent, integration receipt, PostgreSQL actual test summary with zero skips and stopped owned container;14 browser checks/cleanup; all positive/deleted manifest paths and normalized index/HEAD/runtime hashes; manage.py100755; protected seed hash. Only then reconcile MAM-830 Done and complete MAM-831/epic acceptance. Preserve35 functional ticket IDs/history/states and their existing dependencies; remove only architecture blockers when epic acceptance is proved. Remote CI, physical device and live providers require their own evidence and remain NOT RUN here.
