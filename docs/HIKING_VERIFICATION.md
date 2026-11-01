# MAM-819 hiking verification

2026-11-01. Candidate recovered from commits `2554c75330c4680b015ca68fa0849fe32ba75e35`, `ddf3eeffa741ac621393aa2a7ea8f5524af01139` and `debefc91e25082209745bac8ac6edad8b9de1b5a` onto `f2b51ba`; no commit or publication performed here.

Commands ran from the isolated integration worktree using the root project's `.venv-win/Scripts/python.exe`. Django tests used `DJANGO_SETTINGS_MODULE=config.test_settings`, `DATABASE_URL=sqlite:///:memory:`, `DJANGO_DEBUG=1`, a synthetic `DJANGO_SECRET_KEY`, and `AI_ENABLED=0`.

- VERIFIED: `python manage.py test tests.regression.test_hiking tests.regression.test_endurance tests.regression.test_domain basis.modules.training.adapters.test_metrics --noinput` — 32 tests passed.
- VERIFIED: `python -m unittest discover -s tests_architecture` — 226 tests passed.
- VERIFIED: `python manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.training.adapters.test_player basis.modules.sync.adapters.test_wire --noinput` — 587 tests passed, 66 skipped. The opt-in browser test was separately run as described below.
- VERIFIED: `python -m mypy --config-file mypy-core.ini` and `python -m mypy --config-file mypy-django.ini` — 127 and 401 source files respectively, no issues.
- VERIFIED: `ruff check .` and `ruff format --check` over the CI-listed Python paths — 409 files formatted, no lint errors.
- VERIFIED: `git diff --cached --check` on the recovered candidate.
- VERIFIED: `python manage.py test tests.regression.test_hiking_browser --noinput`, with `BASIS_HIKING_BROWSER=1`, a local output directory and local Chromium executable — 1 test passed. Chromium 153.0.8010.12; report at `.cache/mam819-20261101/evidence/browser-report.json` in the root project. Disconnected edit persisted in IndexedDB without a server write, inconsistent elevation was rejected on reconnect, and corrected data was acknowledged and saved once. No JavaScript errors or delivered external responses were recorded.

The browser test deliberately blocks service workers. It exercises the local outbox flow and is not physical-device or complete PWA/service-worker acceptance. Those remain separate work (MAM-632/MAM-638). PostgreSQL and remote CI are not established by these local SQLite checks. No production activation was performed.

The hiking rule uses exact equality for manually supplied ascent, descent and endpoint altitudes when all four are present; partial values remain optional. It does not infer missing values or apply an invented tolerance. This may reject independently rounded observations and warrants explicit product review.
