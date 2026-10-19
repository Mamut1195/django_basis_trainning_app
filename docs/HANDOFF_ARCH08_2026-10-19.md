# ARCH-08 offline synchronization candidate

## State and evidence

main/105ac188be24fbd960a1bf6941dbafa3104455ee contains verified ARCH-07:199 PostgreSQL/no skips, stopped container,53 files and normalized tree/HEAD hashes; run524117c46a6149878edce8c22d124277. MAM-828 Done. ARCH-08/MAM-829 has a local candidate from two implementers with primary orchestration; no ARCH-08 commit or PostgreSQL result yet. ARCH-09 must wait for that gate.

VERIFIED:105 pure tests; strict mypy89 core/140 Django files; eight import contracts; AST/public/inventory; Ruff; Django/no migrations; static collection;218 SQLite tests (213 passed, five PostgreSQL-only skips); native script syntax;31-file completeness/source hash stability. Independent23-case differential with exact baseline coordinator has zero differences; offline.js/template content is unchanged. Evidence: architecture/ARCH-08-VERIFICATION.md, ARCH-08-PARITY.json and .cache/arch08-local/receipt.json.

## Next operation

From external PowerShell in this repository:

```powershell
& '.\scripts\Complete-Arch08.ps1'
```

Use `-Port 55441` if loopback55440 is occupied. The script checks reviewed base/staged scope, self-tests native process capture, repeats controls on its own temporary PostgreSQL18.4 Docker database without host volumes, requires218 tests/no skips and stopped container, records hashes/receipt, commits only the31-file manifest and fast-forwards main without push. Keep errors/logs for diagnosis; do not bypass gates, alter ACL/execution policy, use alternate indexes, stash/reset/clean or force operations.

Return final main SHA or error. Coordinator must independently compare main SHA, actual logs, receipt/integration run, stopped owned container, complete manifest and normalized tree/HEAD source hashes before marking MAM-829 Done and starting ARCH-09. Receipt: docs/architecture/ARCH-08-RESULT.json; logs: .cache/arch08/<run>; integration: .cache/arch08-integration.json. PostgreSQL candidate, native capture execution, main integration and remote CI are NOT RUN here.

## Implementation and limits

Core coordination preserves account locking, raw canonical hash, receipt replay before authorization/late conversion, revision/owner/conflict guards and outer session+receipt commit/rollback. Receipt snapshots retain IDs/order/Decimal scales/missing/zero and never reconstruct from current database state. Existing queue envelope, schema, API/CSRF and403/409 behavior remain. Real browser/device testing is NOT RUN; API/wire tests do not replace final ARCH-10 acceptance. One new local DRF import typing exception is documented in verification; no broad exclusions.

training/services.py now joins strict scope; only training.models and daily_trainning_app.models remain exact silent legacy frontiers. Keep original seed.py168 additions/56 deletions and manage.py mode outside the delivery. No schema changes or providers/production calls occurred. ARCH-09 now must deliver the final architecture: remove daily_trainning_app, relocate responsibilities and persistence into basis module adapters and reorganize apps/schema/migrations as needed under ADR-002. Use temporary databases and preserve unrelated local work. ARCH-10 verifies the final structure from an empty database and full web/offline behavior. Functional tickets retain IDs/history and remain blocked by the architecture epic.
