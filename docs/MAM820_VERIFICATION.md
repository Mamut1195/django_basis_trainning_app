# MAM-820 — verificación local provisional

Base d0e76d3888e3bb984978006a99801e186952630e. Candidato sin commit; integración final con main y CI pendientes. Variables Django: config.test_settings, SQLite temporal en memoria, DEBUG=1, clave sintética, AI_ENABLED=0. Comandos desde este worktree usando Python de .venv-win del proyecto raíz.

| Criterio | Evidencia | Estado |
|---|---|---|
| Etapas hiking, orden/fechas, propiedad y jornada única | dominio trekking, modelos TrekStage, tests_architecture/test_progress.py y basis/bootstrap/tests/test_progress.py | VERIFIED en pruebas existentes; cambios posteriores validados localmente como abajo |
| Totales de jornadas completadas sin intervalos/pernoctas/traslados duplicados | domain/progress.py summarize_trip; tests/regression/test_training_contract.py y tests_architecture/test_progress.py | VERIFIED en suite enfocada y arquitectura |
| Mochila por bloque/jornada, pernocta opcional y recuperación | test_training_contract.py, test_trekking_820.py, detalle y edición web | VERIFIED local |
| Corrección de metadatos conserva recorrido y sesión; aislamiento y exportación | test_trekking_820.py | VERIFIED local |
| Cambios de fecha o último hiking rechazan sin recibo; reemplazo válido y reparación aceptados | test_trekking_820.py | VERIFIED SQLite |
| Revalidación tardía en formularios de alta/corrección | test_trekking_820.py | VERIFIED SQLite con error simulado |
| Concurrencia entre fechas de etapas | test_trekking_820.TrekkingConcurrencyTests | NOT RUN en SQLite (skip has_select_for_update); requiere CI PostgreSQL |
| Vista y recursos locales | test_trekking_820_browser.py; captura .cache/mam820-evidence/trekking-mobile.png | VERIFIED Chromium local 390x844; service workers bloqueados, no aceptación PWA |

Antes del fix, `python manage.py test tests.regression.test_trekking_820 --noinput` ejecutó 2 tests y falló ambos: fecha invertida y cambio del último hiking devolvieron HTTP 200. Después del fix `python manage.py test tests.regression.test_trekking_820 basis.bootstrap.tests.test_progress tests.regression.test_training_contract --noinput` ejecutó inicialmente 24 tests, OK con 1 omitido (PostgreSQL). Tras etiquetas humanas y smoke incluido, se ejecutaron 26, OK con 1 omitido. `python -m unittest discover -s tests_architecture`: 228 OK tras el ajuste del doble en memoria. `mypy-core.ini` y `mypy-django.ini`: OK (130 y 411 archivos). `ruff check .` y `ruff format --check` sobre rutas CI: OK 420 archivos; `git diff --check` OK. Smoke con BASIS_TREK_BROWSER=1 y Chromium local: 1 OK, sin errores JS y recursos estáticos observados HTTP 200. La captura fue inspeccionada: el aviso de offline corresponde al bloqueo deliberado de service workers.

Alcance de integridad: servicios oficiales web/sync usan bloqueo por cuenta y validan estado final; modelos Session.save y Block.save aplican guardas correspondientes. Operaciones SQL administrativo y QuerySet.update/delete no son vías oficiales protegidas por este cambio. No se ejecutó suite completa, PostgreSQL ni CI sobre el árbol combinado con MAM-625. No se activó producción ni se probaron dispositivos físicos; éstos no son requisito añadido al registro manual de este ticket.

## Revalidación local 2026-11-02

Candidato conservado sobre `d0e76d3888e3bb984978006a99801e186952630e`, sin incorporar MAM-625. Entorno comprobado: Python 3.13.7, Django 5.2.18 y mypy 1.19.1 del `.venv-win` del checkout principal. Todas las pruebas Django usaron `config.test_settings`, SQLite en memoria, `AI_ENABLED=0` y clave sintética; sin servicios externos.

- **VERIFIED:** `manage.py test tests.regression.test_trekking_820 basis.bootstrap.tests.test_progress tests.regression.test_training_contract --noinput`: 25 pruebas, OK, una omitida (concurrencia PostgreSQL).
- **VERIFIED:** `python -m unittest discover -s tests_architecture`: 228 pruebas, OK.
- **VERIFIED:** mypy core 130 y Django 411 archivos; Ruff check; Ruff format --check 413 archivos; Import Linter ocho contratos; `git diff --check`.
- **VERIFIED:** `python scripts/architecture_check.py` con excepción `safe.directory` temporal al proceso. Primer intento falló por propiedad Git, sin cambio de configuración global.
- **VERIFIED:** smoke opt-in `tests.regression.test_trekking_820_browser`, una prueba Chromium, recursos estáticos 200 y sin errores JS. Capturas nuevas en `.cache/mam820-evidence-20261102/`; se inspeccionaron ambas en viewport 390×844: detalle y etapa legibles. El aviso offline corresponde a service workers bloqueados deliberadamente; no es aceptación PWA.
- **NOT RUN:** concurrencia en PostgreSQL, suite sobre árbol combinado con MAM-625, CI remoto y aceptación en dispositivos físicos. Esta evidencia no acredita integración ni cierre del ticket.

### PostgreSQL desechable — 2026-11-02

**VERIFIED:** la misma batería focal (`tests.regression.test_trekking_820 basis.bootstrap.tests.test_progress tests.regression.test_training_contract`) ejecutó 25 pruebas en PostgreSQL 18.4 desechable, OK sin omisiones. Incluye `TrekkingConcurrencyTests`: dos escrituras concurrentes dan 200 y 400, mantienen orden válido y un recibo. Se utilizó la instancia aislada de coordinación en localhost, base dedicada de prueba, `config.test_settings`, IA deshabilitada y clave sintética; Django creó y destruyó su base de test. Esta ejecución sustituye únicamente el estado NOT RUN de concurrencia PostgreSQL indicado arriba; siguen pendientes árbol combinado y CI remoto.

**VERIFIED:** `manage.py makemigrations --check --dry-run` no detectó cambios en SQLite.
