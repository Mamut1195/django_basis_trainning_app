# ARCH-06 typing boundary

`basis/modules/billing/adapters/authorization.py` has one local `# type: ignore[import-untyped]` on the import of `rest_framework.exceptions.PermissionDenied`. The installed DRF package has no typing marker or stubs. This adapter preserves the existing HTTP/API exception class and message; the independent core does not import DRF. The suppression applies only to the untyped third-party import and does not suppress analysis of the adapter body. No global missing-import or silent-import exception was added.

`standardwebhooks` provides typing metadata and requires no exception. HTTPX is typed. The compatibility facades `training/access.py`, `training/billing.py` and the reconciliation command now join explicit strict Django scope and leave the pending legacy inventory. Three exact existing mixed legacy modules remain silent frontiers until their own migration: `training.models`, `daily_trainning_app.models` and `training.services`.
