# MAM-628 / BASIS-014: Hoy y reproductor de sesión

## Alcance y estado de entrega

Validación local heredada del 26 de octubre de 2026 (Ecuador; recibos UTC del 27), sesión MAM-628f, snapshot directo v6. Rama `ticket/MAM-628-hoy-reproductor`, base `00fc7185355b05f34874c4cefb4a4c8c16b05793`. Continuación MAM-628g autorizada por `prompt-finish4.md`, snapshot directo v7. Se conservan los 13 archivos heredados. Riesgo 2; MATH_VERIFY OFF, METHOD_REGISTRY NONE: no se modifican ecuaciones, métricas deportivas, modelos ni migraciones.

- Hoy prioriza una ejecución propia en curso y ofrece objetivo y check-in.
- Registro rápido por serie: repeticiones, carga, RPE y RIR reales separados de prescripción y referencia anterior privada. Ausente no equivale a cero; no se autocompletan observaciones.
- Autoguardado serializado con revisión y confirmación HTTP; edición/deshacer compensatorio, errores recuperables y cierre explícito parcial. Se reutilizan casos de uso, autorización, CSRF y validaciones existentes.
- Temporizador por deadline, por cuenta/pestaña, recuperable tras recarga y salto del reloj. Navegación local entre series.
- Borrador recuperable de pestaña opcional que requiere revisión/envío explícito. No es la cola offline de BASIS-018/MAM-632 ni una promesa de durabilidad.
- Se reutilizan composiciones Cotton y estilos/tokens existentes; no se modifican app.js, base.html, service worker ni CSS compartido.

**La implementación y los gates locales no equivalen a aceptación independiente, integración en main ni cierre del ticket.** La ruta de workers Systems es incompatible con la prohibición explícita de subagentes: `scoped_executor_allowed=false`. Los recibos directos incluyen comandos, hashes, versiones, PID y salidas, pero **no son registros sellados de Systems**. Revisión semántica y visual independiente: **BT2/BT3 PENDING**; revisor externo **NOT RUN**.

## Diagnóstico y formato heredados

El script heredado ya contenía `stale.clock.fast_forward(1000)` inmediatamente después de editar `stale_form`, para disparar el debounce de 800 ms con el reloj pausado. Se conserva ese avance, la aserción exacta «La sesión cambió» y las confirmaciones de guardado. El log histórico `gate-player-acceptance-5.txt` permanece **FAILED**: mostraba «Sin cambios pendientes» al esperar confirmación. En MAM-628f pasaron una reproducción sin cambios y la corrida final; **la causa del fallo histórico no quedó reproducida y no se atribuye a una corrección especulativa**. Se añadieron etapas, traceback redactado y límites explícitos sin relajar aserciones.

Prettier histórico fallaba por CRLF en ocho archivos compartidos ajenos. Solo se aplicó `--write` a player.js y timer.js. La validación finish3 ejecutó los argumentos exactos de `npm run format:check` en una copia LF bajo `.cache/mam628-prettier-lf-*`: todos los assets/config sin cambios coincidieron con `git show :ruta` tras normalizar CRLF a LF. No se editaron esos ocho originales ni la configuración Git. El gate acredita formato de contenido LF como checkout Linux, no un CI completo ni un PASS sobre los originales CRLF.

## Resultados históricos finish3 (antes del merge)

Estos resultados corresponden al árbol previo al merge, no certifican por sí solos el candidato posterior. Los recibos y logs se conservan en `C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628`, con prefijo `gate-finish3-`. El resumen es `evidence-finish3-summary.json`.

| Gate | Estado histórico | Evidencia / resultado |
| --- | --- | --- |
| Ruff check | VERIFIED | `gate-finish3-ruff-check.txt` |
| Ruff format --check | VERIFIED | `gate-finish3-ruff-format.txt`; 387 archivos |
| mypy core / Django | VERIFIED | `gate-finish3-mypy-core.txt`, `gate-finish3-mypy-django.txt`; 122 / 379 archivos |
| architecture_check | VERIFIED | `gate-finish3-architecture.txt` |
| tests_architecture | VERIFIED | `gate-finish3-architecture-tests.txt`; 203 pruebas |
| lint-imports | VERIFIED | `gate-finish3-lint-imports.txt`; 8 contratos, 0 rotos |
| djLint | VERIFIED | `gate-finish3-djlint.txt`; 0 archivos a actualizar |
| Prettier LF equivalente a CI | VERIFIED | `gate-finish3-prettier.txt`, `prettier-finish3-lf-manifest.json` |
| manage.py check | VERIFIED | `gate-finish3-django-check.txt`; 0 incidencias |
| makemigrations --check --dry-run | VERIFIED | `gate-finish3-migrations.txt`; sin cambios |
| Suite Django SQLite | VERIFIED | `gate-finish3-tests-sqlite.txt`; 704 pruebas, 63 skipped; 42.071 s |
| Suite Django PostgreSQL 18.4 | VERIFIED | `gate-finish3-tests-postgres.txt`; 704 pruebas, 1 skipped; 216.474 s |
| player_acceptance | VERIFIED | `gate-finish3-player-acceptance.txt`; complete, matriz 390/768/1440 × light/dark |
| PostgreSQL inicio / identidad / parada | VERIFIED | `gate-finish3-pg-start.txt`, `gate-finish3-pg-identity.txt`, `gate-finish3-pg-stop.txt`; detenido |

Las omisiones SQLite incluyen pruebas que requieren bloqueos PostgreSQL. La omisión restante PostgreSQL es el navegador running opt-in (`BASIS_RUNNING_BROWSER=1`), no la aceptación del reproductor. Advertencias: staticfiles ausente y override de DATABASES en pruebas existentes.

La aceptación genera siete PNG y `browser-finish3-player-acceptance/result.json`. Verifica guardado real, recarga, deshacer, ausencia/cero, errores, navegación, deadline, teclado, error de red, recuperación explícita, conflicto, cierre parcial y aislamiento. JS errors=0, external requests=0, browser_closed=true, server_stopped=true. Los service workers se bloquean deliberadamente; esto no certifica la cola offline.

## Comandos y límites finish3

Desde la raíz del worktree: `.venv-win/Scripts/python.exe` 3.13.7, Node 22.19.0, Playwright 1.64.0, Chromium headless shell 153.0.8010.12 (revisión 1243), sin instalar dependencias. `DJANGO_SETTINGS_MODULE=config.test_settings`, `DJANGO_DEBUG=1`, `AI_ENABLED=0`; proveedores y SMTP deshabilitados. SQLite: `.cache/mam628-finish3.sqlite3`; PostgreSQL: `postgresql://postgres@127.0.0.1:55628/mam628`.

El runner directo `basis-runs/MAM-628/finish3_gates.py` ejecuta sin stdin, con salida al log y timeout global de 180 s por gate o 300 s por suite. Solo puede terminar el árbol de su propio PID hijo en timeout. Navegador: 10 s por acción, 15 s navegación/lanzamiento, aserciones de 5 s y migración de 90 s; servidor/navegador se cierran en finally. No hubo timeout en la corrida final.

El Python absoluto se abrevia como `python` en esta lista:

```text
ruff-check: python -m ruff check .
ruff-format: python -m ruff format --check basis config tests tests_architecture scripts/architecture_check.py scripts/browser_smoke.py scripts/acceptance_browser.py scripts/ux_acceptance.py scripts/cotton_acceptance.py scripts/verify_environment.py scripts/backup_db.py scripts/healthcheck.py scripts/verify_operations.py scripts/verify_gunicorn_logging.py deploy/gunicorn_config.py scripts/player_acceptance.py
mypy-core: python -m mypy --config-file mypy-core.ini
mypy-django: python -m mypy --config-file mypy-django.ini
architecture: python scripts/architecture_check.py
architecture-tests: python -m unittest discover -s tests_architecture
lint-imports: .venv-win/Scripts/lint-imports.exe
djlint: python -m djlint basis --check
prettier: python "C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/prettier_lf.py"
django-check: python manage.py check
migrations: python manage.py makemigrations --check --dry-run
tests-sqlite: python manage.py test --noinput
tests-postgres: python manage.py test --noinput
player-acceptance: python -B -m scripts.player_acceptance --output "C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/browser-finish3-player-acceptance" --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

Ruff format incluye la lista de CI más `scripts/player_acceptance.py`. Las suites completas incluyen los 11 nuevos PlayerTests en ambas bases. Cada recibo `.json` registra comando, entorno, paquetes, hashes de ejecutable/runner/snapshot, timestamps, PID, exit, fuentes antes/después y hash del log. La evidencia externa no se sube al repositorio ni sustituye la revisión independiente.

PostgreSQL desechable se inició con `pg_ctl -D .cache/mam628-pg -l .cache/mam628-pg.log -o "-p 55628" -w -t 60 start` y se detuvo con `pg_ctl -D .cache/mam628-pg stop -m fast -w -t 30`, usando `C:/Users/Jonnathan/scoop/apps/postgresql/current/bin/pg_ctl.exe`.

## Continuación finish4

La documentación se reescribió directamente en UTF-8, sin tuberías de texto. El brief autoriza incorporar `origin/main` en la rama del ticket, conservar natación de PR #21 y el reproductor, repetir solo los controles afectados y publicar un PR draft. Los resultados posteriores al merge se documentarán por separado con evidencia `gate-finish4-*`; los resultados históricos no se presentan como reejecutados.

## Pendientes, NOT RUN y coordinación

- Revisión semántica y visual independiente BT2/BT3: **PENDING**. Revisor externo/subagentes: **NOT RUN**, por autorización.
- Aprobación humana, lector de pantalla y dispositivo móvil físico: **NOT RUN**. Capturas/teclado no certifican WCAG ni suspensión real del SO.
- Firefox/WebKit, navegador running opt-in, persistencia offline completa BASIS-018 y servicios LIVE/Polar/SMTP: **NOT RUN**.
- Docker/build de producción y job operations Linux: **NOT RUN localmente**. CI remoto se consulta para el SHA publicado; no se infiere CI PASS de checks Windows.
- Integración en main, cierre del ticket, tracker/Notion/Linear, cambios de dependencias y limpieza: **NOT RUN**, no autorizados.
- **AVISO:** PR #21 / MAM-814 ya está fusionado en main; comparte el área training y las rutas `_metrics.html` y `training_tags.py`. MAM-629 comparte `basis/modules/training`, migraciones/urls; MAM-631 comparte `app.js`/`base.html`. No se crean relaciones de dependencia por estos avisos.
