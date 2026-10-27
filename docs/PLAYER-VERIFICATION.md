# MAM-628 / BASIS-014: Hoy y reproductor de sesión

## Alcance y estado de entrega

Validación local heredada del 26 de octubre de 2026 (Ecuador; recibos UTC del 27), sesión MAM-628f, snapshot directo v6. Rama `ticket/MAM-628-hoy-reproductor`, base `00fc7185355b05f34874c4cefb4a4c8c16b05793`. Continuación MAM-628g autorizada por `prompt-finish4.md`, snapshot directo v7. Se conservan los 13 archivos heredados. Riesgo 2; MATH_VERIFY OFF, METHOD_REGISTRY NONE: no se modifican ecuaciones, métricas deportivas, modelos ni migraciones.

- Hoy prioriza una ejecución propia en curso y ofrece objetivo y check-in.
- Registro rápido por serie: repeticiones, carga, RPE y RIR reales separados de prescripción y referencia anterior privada. Ausente no equivale a cero; no se autocompletan observaciones.
- Autoguardado serializado con revisión y confirmación HTTP; edición/deshacer compensatorio, errores recuperables y cierre explícito parcial. Se reutilizan casos de uso, autorización, CSRF y validaciones existentes.
- Temporizador por deadline y cuenta en `localStorage`, recuperable tras recarga, cierre/reapertura de pestaña y salto del reloj. Comparte el deadline entre pestañas del mismo origen/cuenta; depende de que el navegador conserve el almacenamiento local. Navegación local entre series.
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

## Resultados finish4 tras incorporar main

Se incorporó `origin/main` **5cbcd32** (incluye PR #21 / MAM-814) mediante merge normal **5a3daf5**; no hubo conflictos ni resolución manual. `_metrics.html` y `training_tags.py` conservan exactamente el contenido de main/natación, y el diff del ticket frente a main sigue limitado a sus 13 archivos. No se cambiaron modelos, migraciones, métricas ni los algoritmos incorporados desde main. La incorporación a la rama no equivale a integración del ticket en main.

Se ejecutaron los siguientes controles sobre **5a3daf5** con `finish4_gates.py`, snapshot directo v8. Todos terminaron con exit 0 y fuentes sin cambios. `verify-finish4.py` contrastó comandos, timeouts, hashes de runner/snapshot/ejecutables/logs, paquetes Python, HEAD/índice/estado y archivos completos antes/después contra el árbol probado. También comprobó hashes de las siete capturas. Resumen externo: `evidence-finish4-summary.json`. Esta documentación se amplió después de las pruebas; el cambio posterior es exclusivamente documental, sin modificar código, fixtures, tests ni configuración ejecutable. No se atribuye aceptación Systems sellada al nuevo commit.

| Gate | Estado finish4 | Evidencia / resultado |
| --- | --- | --- |
| Ruff check | VERIFIED | `gate-finish4-ruff-check.txt` |
| Ruff format --check | VERIFIED | `gate-finish4-ruff-format.txt`; 390 archivos |
| mypy core / Django | VERIFIED | `gate-finish4-mypy-core.txt`, `gate-finish4-mypy-django.txt`; 123 / 381 archivos |
| architecture_check | VERIFIED | `gate-finish4-architecture.txt` |
| tests_architecture | VERIFIED | `gate-finish4-architecture-tests.txt`; 209 pruebas |
| lint-imports | VERIFIED | `gate-finish4-lint-imports.txt`; 8 contratos, 0 rotos |
| djLint | VERIFIED | `gate-finish4-djlint.txt`; 43 archivos, 0 a actualizar |
| Prettier JS de MAM-628 | VERIFIED | `gate-finish4-prettier.txt`; player.js y timer.js, sin tocar CRLF ajenos |
| manage.py check | VERIFIED | `gate-finish4-django-check.txt`; 0 incidencias |
| makemigrations --check --dry-run | VERIFIED | `gate-finish4-migrations.txt`; sin cambios |
| Módulo training en SQLite | VERIFIED | `gate-finish4-tests-training.txt`; 15 pruebas, 0 omisiones; 0.791 s |
| Regresiones afectadas en SQLite | VERIFIED | `gate-finish4-tests-affected-regression.txt`; 74 pruebas, 0 omisiones; 4.263 s |
| player_acceptance | VERIFIED | `gate-finish4-player-acceptance.txt`; complete, siete capturas, 390/768/1440 × light/dark |
| Suites completas SQLite / PostgreSQL tras merge | NOT RUN | Se conserva evidencia histórica finish3; no hay cambios de persistencia/esquema/migraciones y el brief exige repetir solo lo afectado. CI remoto verifica el SHA publicado por separado. |

Se mantienen los comandos de lint/tipado/arquitectura/djLint/check/migraciones anteriores. Los comandos que cambian respecto de finish3 son:

```text
prettier: node node_modules/prettier/bin/prettier.cjs --check basis/adapters/web/static/basis/js/player.js basis/adapters/web/static/basis/js/timer.js
tests-training: python manage.py test basis.modules.training --noinput
tests-affected-regression: python manage.py test tests.regression.test_swimming tests.regression.test_running tests.regression.test_execution_records tests.regression.test_web tests.regression.test_training_contract tests.regression.test_strength_metrics --noinput
player-acceptance: python -B -m scripts.player_acceptance --output "C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/browser-finish4-player-acceptance" --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

`DJANGO_SETTINGS_MODULE=config.test_settings`, SQLite `.cache/mam628-finish4.sqlite3`, sin proveedores ni SMTP. Se reutilizan los binarios instalados, sin descargas. Límites del runner: 180 s por gate/navegador y 300 s por grupo de tests, stdin deshabilitado, limpieza acotada al árbol hijo propio si vence el timeout. No hubo timeout ni terminación forzada. PostgreSQL local no se inició en finish4. Browser: `browser_closed=true`, `server_stopped=true`, cero errores JS y cero solicitudes externas. La advertencia de `staticfiles` ausente continúa sin causar fallos.

**Revisión independiente BT2/BT3: PENDING; PR solo draft.** El estado remoto del CI se registra en el PR y en la entrega, sin confundir publicación con aceptación o cierre. Se mantienen los avisos de solapamiento con MAM-629 (training/migraciones/urls) y MAM-631 (app.js/base.html).


## Arreglo PR #22 / fix22f (27-oct-2026)

El job `postgres` de CI en `7a67b5955bd6c98ae1b6ab013b30f85a37438260`
(run `40558192217`) falló exactamente por Ruff I001 en los imports de
`test_player.py`, no por PostgreSQL. El commit `72b1510` corrige ese orden.
Los gates directos `gate-fix22f-step1-*` verificaron Ruff check/format, mypy
core/Django, arquitectura, 209 tests_architecture, ocho contratos lint-imports,
djLint, Django check y ausencia de migraciones. Pasaron 75 pruebas training y
regresiones afectadas en SQLite y las mismas 75 en PostgreSQL desechable, sin
omisiones. PostgreSQL puerto 55628 se inició, verificó y detuvo con exit 0.

El cronómetro vuelve a `localStorage`, manteniendo su clave `basis-rest:<cuenta>`
y la aritmética del deadline. Los borradores de formularios permanecen en
`sessionStorage`; no se cambia la cola offline ni la política de sincronización.
La aceptación headless ahora cierra la pestaña, abre una nueva y exige el mismo
deadline y los 59 segundos restantes antes de comprobar la expiración. Esto
prueba cierre de pestaña, no suspensión real del SO ni reinstalación/limpieza del
navegador. La reapertura de app depende del almacenamiento persistido del perfil.
Los resultados de gates del cambio de almacenamiento se registran por separado;
no se atribuyen a este cambio los PASS anteriores.

Systems **NOT RUN — WORKTREE_ALREADY_OWNED**, sin init ni cambios de ownership.
Evidencia manual directa, no sellada Systems; revisión semántica/visual fuerte
independiente **NOT RUN / PENDING BT2/BT3**. Sin aceptación, integración ni cierre.

## Implementación codex1 sobre 974ab15 (27-oct-2026, detenida)

Los resultados de esta sección corresponden exclusivamente a esta ejecución.
Los PASS históricos anteriores no validan el cambio sin commit actual.
Se leyeron primero `gate-fix22f-step2-player-acceptance.txt` y su JSON: el fallo
histórico fue `00:00` al exigir `00:59` tras recargar (línea 186); la reapertura
no llegó a ejecutarse en aquella corrida.

Diagnóstico: la API instalada de Playwright Python (`_impl/_clock.py`,
`parse_time`) multiplica por 1.000 los valores numéricos de `pause_at`, que espera
segundos Unix. El script le pasaba `Date.now()` en milisegundos. La captura
`codex1/gate-timer-diagnosis.txt` demuestra una hora de 16 dígitos y conserva
la clave y el deadline. Además, el reloj se instalaba después de que el JS
registrara sus temporizadores: mezclaba temporizadores nativos y virtuales.
La ejecución original sin cambios pasó esta vez (`gate-player-reproduce.txt`),
igual que la instrumentada (`gate-player-diagnosis.txt`); por tanto, **no se ha
reproducido de forma determinista el fallo histórico ni probado su causa exacta**.
Sí se ha demostrado el error de unidades del arnés. No hay evidencia de pérdida
del valor en localStorage, cambio de clave o defecto de hidratación en estas
capturas. No se modificó `timer.js`.

El candidato sin commit instala el reloj antes de navegar, convierte los
milisegundos a segundos y mantiene las aserciones `01:30`, `00:59` tras avance,
`00:59` tras recarga, `00:59` tras cerrar/reabrir pestaña y `00:00` al expirar.
Añade aserciones independientes de hora, cuenta y deadline persistido, con
recibos `timer_reload` y `timer_reopen` cuando esas etapas pasen. **El candidato
no está verificado.**

La invocación del candidato terminó antes de migrar o abrir Chromium:

```text
FileExistsError: [WinError 183] Cannot create a file when that file already exists: 'C:\Users\Jonnathan\Mamut system\basis-runs\MAM-628\acceptance-codex1'
```

La carpeta de salida ya existía y `run()` usa `output.mkdir(exist_ok=False)`.
Se conserva vacía, sin borrarla. Se detuvo el trabajo conforme a la orden
«Si algo falla, guarda lo hecho y para escribiendo la causa literal».

| Gate codex1 | Estado | Evidencia / alcance |
| --- | --- | --- |
| Diagnóstico del reloj y almacenamiento | VERIFIED | `codex1/gate-timer-diagnosis.txt`, `gate-timer-diagnosis-expect.txt`; defecto de unidades demostrado; fallo histórico intermitente no reproducido |
| Aceptación original sin cambios | VERIFIED | `codex1/gate-player-reproduce.txt`, `codex1/reproduce-player/result.json`; no valida el candidato |
| Aceptación del candidato | FAILED | `codex1/gate-player-acceptance.txt`; WinError 183 antes de ejecutar el flujo |
| Recarga y cierre/reapertura del candidato | NOT RUN | El lanzamiento falló antes de abrir el navegador |
| N+1 SQLite / PostgreSQL | NOT RUN | Inspección solamente: `PlayerTests.test_session_detail_query_count_is_constant_as_series_grow` ya usa `assertNumQueries(len(queries))`, compara 2 y 22 series renderizadas, exige una consulta ROW_NUMBER y valida las 22 referencias |
| Ruff check / Ruff format --check | NOT RUN | Parada tras fallo de aceptación |
| mypy core / Django | NOT RUN | Parada tras fallo de aceptación |
| djLint | NOT RUN | Parada tras fallo de aceptación |
| manage.py check / makemigrations --check | NOT RUN | Parada tras fallo de aceptación |
| Training y regresiones afectadas SQLite / PostgreSQL | NOT RUN | Parada tras fallo de aceptación |
| lint-imports --no-cache | NOT RUN | Parada tras fallo de aceptación |
| Prettier / tests_architecture LF o CI | NOT RUN | Sin red, sin ejecución CI ni normalización de archivos CRLF ajenos |
| Systems | NOT RUN | WORKTREE_ALREADY_OWNED; no se ejecutó systems-cli ni se alteró ownership |
| Revisión independiente BT2/BT3 | NOT RUN | Delegada a BT2/BT3 para el ejecutor; pendiente, no realizada por este implementador |

Comandos para retomar, **NOT RUN sobre el candidato**, desde el worktree con
`.venv-win/Scripts/python.exe` abreviado como `python`. Para el navegador debe
usarse una subcarpeta nueva bajo `acceptance-codex1` y un timeout externo de
240 segundos; no reutilizar la raíz existente ni borrar evidencia.

```text
python -B -m scripts.player_acceptance --output "C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/acceptance-codex1/player-01" --browser-executable "C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe"
python -m ruff check .
python -m ruff format --check scripts/player_acceptance.py basis/modules/training/adapters/test_player.py
python -m mypy --config-file mypy-core.ini
python -m mypy --config-file mypy-django.ini
python -m djlint basis --check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test basis.modules.training.adapters.test_player.PlayerTests.test_session_detail_query_count_is_constant_as_series_grow --noinput --verbosity 2
python manage.py test basis.modules.training tests.regression.test_swimming tests.regression.test_running tests.regression.test_execution_records tests.regression.test_web tests.regression.test_training_contract tests.regression.test_strength_metrics --noinput
python -c "from importlinter.cli import lint_imports; lint_imports()" --no-cache
```

Usar `DJANGO_SETTINGS_MODULE=config.test_settings`, `DJANGO_DEBUG=1`,
`AI_ENABLED=0`, sin proveedores ni SMTP; SQLite desechable y, por separado,
`DATABASE_URL=postgresql://postgres@127.0.0.1:55638/mam628_codex1` para PostgreSQL
desechable. No se inició ni inicializó PostgreSQL en esta ejecución. Las carpetas
de diagnóstico y `.cache/mam628-browser-*` quedan conservadas; no hubo limpieza.

Cambios sin commit, sin push, sin gh, sin red, sin integración ni cierre.
**Aviso de choque:** MAM-629 comparte training/migraciones/urls; MAM-631 comparte
app.js/base.html. Coordinar revisión e integración; estos avisos no crean
dependencias entre tickets.

## Verificación codex2 sobre 974ab15 (27-oct-2026)

Se revisó y conservó el diff heredado de codex1 sin reducir comprobaciones.
La API local instalada confirma `parse_time(time * 1000)`: `pause_at()` recibe
segundos Unix. La conversión de `Date.now()` y la instalación del reloj antes
de navegar son correctas. No se modificaron `timer.js` ni código de producto.
La causa exacta del fallo histórico intermitente sigue sin demostración;
el defecto de unidades del arnés sí está confirmado y el candidato ahora pasó.

Aceptación **VERIFIED** en una salida nueva, inexistente al iniciar:
`C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/acceptance-codex2/run-20261027-134901-945`.
Se usó el Chromium headless shell 1243 indicado y timeout externo duro de 240 s.
`result.json` confirma `stage=complete`, `timer_reload=VERIFIED` y
`timer_reopen=VERIFIED`: ambos conservan 59 segundos, cuenta y deadline de
localStorage. También pasó la expiración a cero y el resto del flujo.
Navegador y servidor cerrados, fuentes sin cambios, cero errores JavaScript y
cero solicitudes externas. Se comprobaron los hashes del arnés y las siete
capturas; esto no sustituye la revisión visual independiente.

Evidencia y comandos completos:
`C:/Users/Jonnathan/Mamut system/basis-runs/MAM-628/codex2/result.md`.
Los resultados siguientes pertenecen a esta ejecución del candidato sin commit:

| Gate codex2 | Estado | Evidencia bajo `codex2/` |
| --- | --- | --- |
| Aceptación headless / recarga / cierre y reapertura | VERIFIED | `gate-player-acceptance.txt`, `gate-player-receipt.txt`; recibo en la salida anterior |
| N+1 de session_detail, SQLite / PostgreSQL | VERIFIED | `gate-n-plus-one-sqlite.txt`, `gate-n-plus-one-postgres.txt`; prueba existente con assertNumQueries, 2 frente a 22 series y una consulta ROW_NUMBER |
| Ruff check / format --check | VERIFIED | `gate-ruff-check.txt`, `gate-ruff-format.txt`; alcance CI más player_acceptance.py |
| mypy core / Django | VERIFIED | `gate-mypy-core.txt`, `gate-mypy-django.txt`; 123 y 381 archivos |
| architecture_check / tests_architecture | VERIFIED | `gate-architecture-check.txt`, `gate-tests-architecture.txt`; 209 tests en copia LF |
| lint-imports --no-cache | VERIFIED | `gate-lint-imports.txt`; 8 contratos |
| djLint | VERIFIED | `gate-djlint.txt` |
| manage.py check / makemigrations --check | VERIFIED | `gate-django-check.txt`, `gate-makemigrations.txt` |
| Training y regresiones afectadas SQLite / PostgreSQL | VERIFIED | `gate-training-sqlite.txt`, `gate-training-postgres.txt`; 91 tests por motor, sin skips |
| Prettier, CSS/JS tocados, LF | VERIFIED | `gate-prettier.txt`, `prettier-files.txt`, `lf-source-manifest.json` |
| PostgreSQL desechable detenido | VERIFIED | `gate-postgres-stop.txt`; puerto 55639 sin respuesta y sin postmaster.pid |
| Diff acotado y sin whitespace errors | VERIFIED | `gate-diff-review.txt` |
| Systems | NOT RUN | WORKTREE_ALREADY_OWNED; sin systems-cli ni cambios de ownership |
| Revisión independiente BT2/BT3 | NOT RUN | Delegada a BT2/BT3 para el ejecutor; pendiente |

Prettier y tests_architecture se juzgaron sobre una copia de archivos rastreados
del candidato, cambiando únicamente CRLF a LF en texto UTF-8. El manifiesto
conserva hashes originales y normalizados. No se normalizaron archivos ajenos
del worktree ni se atribuye una ejecución CI nueva a estos gates locales.

El primer initdb directo falló por restricted token y creación de directorio;
el reintento indicado con carpeta nueva vacía y `Start-Process -Wait` pasó.
`postgres.exe` se ejecutó directamente desde un `.ps1`, ligado a 127.0.0.1:55639.
El servidor se detuvo al terminar. `codex2/pgdata` queda conservado, sin borrar.

Cambios sin commit; HEAD sigue en 974ab15903761d94f99381b1ba0f95f7af174704.
Sin push, gh, red, LIVE, Polar, D:, integración ni cierre del ticket.
**Aviso de choque:** MAM-629 comparte `basis/modules/training`, migraciones y urls;
MAM-631 comparte `app.js` y `base.html`. Revisar ambos cruces antes de integrar.
