# MAM-635: cancelación segura de consultas IA pendientes

## Candidato y alcance

Implementación **local, lista para revisión independiente**, sin integración ni cierre del ticket.
Padre: `97e771daa99e23657dc24843928be136a649dfac`.
Commit funcional: `d88fca8b4f5bc4314cb7efbc61428a0ec8a931c3`.
Este recibo se entrega en un commit documental posterior; todas las ejecuciones finales corresponden a ese código funcional, sin cambios de fuentes durante la suite completa.

Worktree exclusivo: `C:/Users/Jonnathan/.t3/worktrees/django-basis-trainning-app/t3-163b62a1`, rama `t3/cancel-pending-ai-queries`. Estado inicial limpio. No se crearon otros agentes ni se editó el checkout raíz u otros worktrees. Se leyeron arquitectura, plan Wave4, contrato de cancelación e integración818 antes de implementar. Skills: `task-planning`, `safe-git-workflow`, `verify-before-complete` y `systematic-debugging` para aislar los errores heredados.

Solo cambian jobs dominio/aplicación/adaptadores, la fachada actions, vistas/URL de jobs, su fragmento de resultado y tres archivos nuevos de pruebas. No hay migraciones, cambios de bootstrap/public, precios/whitelist818, fuentes/prompts633, propuestas/guard634, entrenamiento manual, recorder, offline, evals, workflows ni lockfiles. La rama congelada conserva `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`, comprobado con `git rev-parse`.

## Comportamiento implementado

`Jobs.cancel(owner, job_id)` devuelve el mismo `Job` durable. Comprueba propietario antes de bloquear o escribir; ausencia y cuenta ajena se traducen al mismo404. Bloquea fondo original cuando existe → cuenta → job → usage original, y relee estado/propiedad bajo lock. Una referencia de origen que cambie durante esa lectura se rechaza.

Solo cancela pending sin intento abierto ni evidencia de procesamiento. Antes de cualquier ajuste valida reserva, saldos, procedencia del período/fondo, ausencia de costo/uso observado y contadores. Libera la reserva original, resta una acción del tipo correspondiente y guarda `status=cancelled`, `cost=0` y `completed_at` dentro de la misma UoW. No modifica spent, el contador del otro tipo ni períodos/fondos posteriores. Una excepción después de escribir el job revierte también usage/fund. Cancelled se devuelve sin segundo ajuste; otro intento abierto y estados running/uncertain/succeeded/failed/desconocido producen conflicto sin mutación.

`POST /coach/jobs/<uuid>/cancel/` requiere sesión y CSRF, sin autorización comercial/deportiva ni IA habilitada. Éxito redirige al detalle; conflicto409 renderiza el estado actual y la reserva conservada. El formulario solo aparece para pending sin attempt_id/started_at. Cancelada muestra costo cero y carece de polling/formulario de cancelación. Se conservan el consumo de la consulta y el aviso de actualización fallida, sin tocar su JavaScript. El replay de request_key con contenido idéntico utiliza la idempotencia existente: mismo job cancelado, sin proveedor ni propuesta.

## Entorno y aislamiento

- Python raíz `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`: **3.13.7**.
- Django5.2.18, psycopg3.3.6, HTTPX0.28.1, mypy1.19.1, Ruff0.17.1, djLint1.36.4, Import Linter2.11; Node22.19.0 y Git2.55.0.windows.4 verificados.
- PostgreSQL **18.4**, `127.0.0.1:55482`, usuario sintético `basis_wave0`; solo `basis_wave4_635_cancel` y `test_basis_wave4_635_cancel` para datos/pruebas.
- La base principal exclusiva faltaba. El bootstrap abrió una conexión de mantenimiento a postgres únicamente para `CREATE DATABASE basis_wave4_635_cancel`, sin enumerar bases ni leer/escribir datos ajenos. El runner posterior limita psycopg/libpq a las dos bases autorizadas, incluyendo el cursor de mantenimiento Django; no usa su fallback a postgres/template1. No se detuvo ni reinició el servidor compartido.
- Runner copiado/adaptado en `.cache/mam635-cancel/run_guarded.py` desde la referencia818, sin editarla. `config.test_settings`, secretos sintéticos y `AI_ENABLED=0` fuera de fixtures. No se leyó `.env` ni credenciales.
- HTTPX sync/async real y sockets externos rechazados antes del transporte; loopback permitido para PostgreSQL y servicios sintéticos. Proveedor probado con MockTransport en las regresiones818; las cancelaciones no despachan. `verify_guard.py` confirmó también rechazo de conexiones a una base ajena. Es un guard Python, no un cortafuegos del sistema ni garantía sobre procesos descendientes arbitrarios.

## Matriz del contrato

| Requisito | Evidencia ejecutada |
| --- | --- |
| Paid/trial × short/plan, costo0/completed_at y decremento de un solo contador | Mismo `CancellationContract` ejecutado en fake y ORM; recorrido POST en las cuatro combinaciones. |
| Doble cancelación y replay request_key | Mismo job/resultado; saldos idénticos tras segunda llamada; un único job por clave; provider/proposal sin llamadas. |
| Fondo/período originales frente a posteriores y spent previo | Prueba compartida conserva later usage/fund, spent y contador del otro tipo. |
| Integridad y rollback integral | Rechazo de saldo insuficiente, contador cero/negativo, spent excesivo, owner/is_trial incoherentes y fondo incompatible; fallo después de save_job revierte las tres filas. |
| Cuenta vencida y ausencia de gates comerciales/deportivos | POST real del cliente Django con período vencido e IA deshabilitada; puertos billing/context configurados para fallar si se consultan durante cancelación. |
| Foreign404, inexistente404, anónimo, GET405, CSRF403 | Cliente Django con CSRF estricto; posterior POST con token válido; prompt privado ausente en404. |
| Estados no pending y cualquier attempt abierto | Matriz fake/ORM; estados y ledgers sin mutación. Cancelled con attempt abierto también se rechaza. |
| Orden de locks y settlement posterior | Orden observado fund/account/job/usage; settle con token ausente/ajeno no altera cancelled. |
| Claim primero | Transacción principal conserva lock real del job reclamado; conexión separada de cancelación espera; `pg_blocking_pids` demuestra el blocker concreto; después del commit devuelve conflicto y conserva reserva/token. |
| Cancel primero | Transacción conserva cancelación sin commit; otro worker devuelveFalse por SKIP LOCKED. `pg_blocking_pids` vacío es lo esperado, porque claim no espera. Después del commit tampoco reclama/envía. |
| Cancel vs enqueue de la misma cuenta | Ambos órdenes con transacciones/conexiones separadas, blocker real demostrado por `pg_blocking_pids`; también fondo original frente a mes posterior. No ciclos; nueva reserva intacta y sin negativos. |
| Cancelaciones simultáneas | Segundo cancel espera un blocker concreto y luego devuelve mismo resultado sin doble ajuste. |
| Barrera818, matching/wrong token, retención y conciliación | Regresiones completas de jobs/provider_policy/reconciliation/pricing_migration/attempt_fence incluidas en la focal86. No se modificó esa política. |
| Manual/plan vigente | Nueva prueba HTTP crea plan, cancela adaptación y registra sesión manual; filas del plan permanecen idénticas. |

Las carreras nuevas usan Events, transacciones y consulta explícita de blockers, sin sleeps para probar orden. Acreditan los intercalados ensayados, no todos los posibles.

## Resultados de validación

| Check | Estado y resultado |
| --- | --- |
| Focal cancelación + jobs/ledger818 estable | **VERIFIED**:86 pruebas PostgreSQL, cero omisiones,40.057s, salida0. Incluye17 pruebas nuevas ORM/HTTP/carreras. |
| Puras `tests_architecture` | **VERIFIED**:285 pruebas,3.721s, salida0; incluye siete nuevas de paridad fake. No sumar como casos únicos adicionales a la suite Django. |
| Mypy core / Django final | **VERIFIED**:135 /433 archivos, sin errores. |
| Arquitectura / Import Linter | **VERIFIED**: fronteras y legado; ocho contratos conservados, cero rotos. |
| Ruff check / formato global | **VERIFIED**:sin errores;444 archivos ya formateados, respetando exclusión de migraciones. |
| djLint global | **VERIFIED**:cero archivos por actualizar. |
| Django check / migraciones | **VERIFIED**:sin incidencias; makemigrations --check --dry-run sin cambios. |
| Guard del runner | **VERIFIED**:HTTPX sync/async, TCP externo y base ajena rechazados; PG18.4 confirmado. |
| T3 navegador escritorio/móvil | **VERIFIED LOCAL_SYNTHETIC**:interacciones y navegación reales, descritas abajo. |
| Suite Django completa estable | **FAILED, errores heredados reproducidos**:1071 casos,1054 satisfactorios, ocho errores y nueve omisiones,322.411s, salida1. Las24 pruebas nuevas (17 ORM/HTTP/carreras y siete fake) pasan. |
| Reproducción de todos los errores sobre padre97e771d | **VERIFIED**:mismos ocho casos fallan sin cancelación,0.748s; comparación exacta de nombres confirmada. |
| Base temporal al terminar | **VERIFIED**:tras teardown de la suite/reproducción, conexión únicamente a test_basis_wave4_635_cancel confirma que ya no existe. |
| Diff y alcance | **VERIFIED**:`git diff --check`; solo archivos propios; commit funcional registrado. |

## Navegador T3

Servidor sintético propio en loopback8765 con el runner guardado y AI0, datos de `basis_wave4_635_cancel`. Se usaron `preview_status`, `preview_open`, `preview_snapshot`, `preview_type`, `preview_click`, `preview_navigate`, `preview_resize` y `preview_evaluate`; no hubo standalonebrowser ni Playwright alternativo.

- Escritorio1280×800: login de cuenta sintética, pending con reserva/formulario y polling; botón envía POST real y redirige a detalle Cancelada/costo0 sin formulario ni polling; recarga conserva el resultado. Sin desbordamiento horizontal.
- Móvil390×844 mediante preset iphone-12-pro: mismo recorrido y recarga, botón de155.92×44.80 píxeles CSS, sin desbordamiento horizontal. Es viewport del navegador de escritorio, no dispositivo físico ni user-agent móvil.
- Aviso de polling anterior: evento sintético `htmx:sendError` conserva el consumo y muestra el aviso de último estado. Esto comprueba el manejador existente, no una interrupción de red física.
- Conflicto real de formulario: se retuvo el fragmento pending impidiendo solo su siguiente poll; un claim sintético en otra conexión confirmó running; el botón produjo POST409 y mostró running, aviso de reserva conservada, sin botón y con polling del resultado real. No se ejecutó HTTP de proveedor.
- El cliente HTTP Django se registra por separado y no se atribuye a esta evidencia de navegador.

Snapshots T3 guardados en `C:/Users/Jonnathan/.t3/userdata/browser-artifacts/`:

- Desktop Cancelada: `browser-screenshot-127-0-0-1-mw0a4rie-ce77bf1a.png`.
- Móvil Cancelada: `browser-screenshot-127-0-0-1-mw0a43wp-0b5510f6.png`.
- Móvil conflicto: `browser-screenshot-127-0-0-1-mw0a3m1b-cee233c2.png`.

Lecturas DOM y metadatos adicionales: `.cache/mam635-cancel/browser-evidence.json` y `browser-screenshots.json`. Los artefactos ignorados por Git no estarán en un clon nuevo.

El servidor sintético propio se detuvo al terminar mediante la sesión de proceso que lo creó. No se detuvo PostgreSQL ni otro servicio. La base principal exclusiva con fixtures se conserva.

## Fallos conservados y atribución

1. **FAILED, corregido en las pruebas nuevas:** primera ejecución mypy Django, ocho errores por Decimal/int, kwargs del cliente y listas sin anotación. Después pasó. Primer core detectó dos errores del retorno Self en el nuevo fake; se añadió `CancellationMemory.__enter__`, y core/Django finales pasan. Se conserva el log inicial Django. El helper reemplazó el log inicial core al repetirlo; su salida exacta conservada en el historial de herramientas se transcribió a `mypy-core-initial-tool-transcript.txt`, identificado como transcripción y no como log original.
2. **FAILED heredado y fuera de ámbito:** focal integrada inicial111 casos,40.035s, ocho errores de propuestas en `test_coach_edges` y `test_mam635_acceptance`. El fixture define disponibilidad `[1,3,5]` y programa sesión en `timezone.localdate()`, hoy martes2026-11-03; el guard combinado634 rechaza «Una sesión queda fuera de tus días disponibles». La propuesta nunca se crea, de ahí sus DoesNotExist derivados. No se relajó el guard ni se modificaron esos fixtures.
3. **VERIFIED reproducción padre:** `git archive` del padre97e771d a un snapshot dentro de la `.cache` de este mismo worktree, sin editar otro checkout. Mismo runner/bases exclusivas y fecha real. Primero dos casos representativos reprodujeron CoachInvalid/PlanProposal.DoesNotExist sin código de cancelación (`parent-repro.log`, dos errores en0.403s). Después de la suite completa se reprodujeron los ocho casos sobre el padre: `parent-all8.log`, ocho errores en0.748s. `compare_parent.py` confirma los mismos ocho nombres en padre y candidato; la lista está en `parent-repro-tests.txt`. No se cambió el reloj para obtener un resultado favorable. El helper de extracción tuvo que leer el log Windows como cp1252 tras un primer error de decodificación UTF8; no se modificaron bytes del log de la suite.
4. **Preflight:** primera conexión confirmó que faltaba la base exclusiva; se creó como se explica arriba. T3 rechazó inicialmente about:blank y luego encontró loopback sin servidor; al arrancarlo funcionó. Se corrigieron los argumentos de interacción a los locators documentados. Estos errores no son fallos de la aplicación ni se ocultaron.

Los ocho errores son cinco de `CoachEdgeTests` (edición/aceptación, idempotencia/owner, rechazo/replay, rechazo/contenido y generación de plan) y tres de `CoachAcceptance635Tests` (adaptación histórica, comparación/aceptación y revisión/rechazo). Las nueve omisiones optativas son hiking1, MAM632 offline4, PWA1, running1, swimming1 y trekking1; no hubo omisiones de cancelación ni de818.

## Comandos reproducibles y artefactos

Desde este worktree, `$py='C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'` y `$runner='.cache/mam635-cancel/run_guarded.py'`:

```powershell
& $py -B $runner manage test basis.bootstrap.tests.test_coach_cancellation basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_coach_attempt_fence --noinput -v 2
& $py -B $runner unittest discover -s tests_architecture -q
& $py -B $runner mypy --config-file mypy-core.ini
& $py -B $runner mypy --config-file mypy-django.ini
& $py -B scripts/architecture_check.py
& $py -B $runner script .cache/mam635-cancel/check_imports.py
& $py -m ruff check .
& $py -m ruff format --check basis config tests tests_architecture scripts/architecture_check.py scripts/browser_smoke.py scripts/acceptance_browser.py scripts/ux_acceptance.py scripts/cotton_acceptance.py scripts/verify_environment.py scripts/backup_db.py scripts/healthcheck.py scripts/verify_operations.py scripts/verify_gunicorn_logging.py deploy/gunicorn_config.py
& $py -m djlint basis --check
& $py -B $runner manage check
& $py -B $runner manage makemigrations --check --dry-run
& $py -B $runner script .cache/mam635-cancel/verify_guard.py
& $py -B $runner manage test --noinput -v 2
git diff 97e771d..HEAD --check
```

`checks.py` captura checks independientes y `capture.py <label> <runner-args>` captura stdout/stderr íntegros y conserva el exitcode. Runner, scripts, logs y plan de trabajo propios en `.cache/mam635-cancel/`, sin editar la referencia818. SHA256 de artefactos finales:

| Artefacto | SHA256 |
| --- | --- |
| `run_guarded.py` | `9596D3C9E6782A959FAA35A4E0C720E829376D11CBF66D89A46AD644C2119D3E` |
| `focal-cancellation-final.log` | `3D6F9405F99BAB3FCC0EA3EE35D2E6569AF1CDCA660C8211AF245EC228A1EC9F` |
| `pure.log` | `99806F7B60E6231754765BE028601DFF00B0D52C6ED840C5178165A2A48C3D9B` |
| `mypy-core.log` | `4655BAA132D62306C2599CDABA3A28C92702EED4D94418FABD2F14A499CAA500` |
| `mypy-django-final.log` | `AE012445309E1F15FC6D884ECF5F5EDEE17B7A9B4C84C1BF8FC9958656B931C6` |
| `mypy-core-initial-tool-transcript.txt` | `772048E5301ECFA06F05D8F4535F869D9B340A5809C07EC703CD192ADE52AD4B` |
| `browser-evidence.json` | `34FEA5997BA7EAC309ECA4F0A74BB381F0AECC3CD14CE697FA736A2505C09BAD` |
| `parent-repro.log` | `EC827F496A36655AED77581A1B3D38A2FFB9EFA3C0F939A3F9A9237BD408A5C2` |
| `focal-integrated-2.log` (ocho errores heredados) | `EB595448C6803CE789F011C65DE90D399A714E42AA0D7EE326AF29F2A9EF4AC8` |
| `full-stable.log` | `4E6E013F6BD8A35CC9F25BB9922F366CF386305CE4252D34C2B2EC95C5E6ECE0` |
| `parent-all8.log` | `C85B052536E2DA3B1EFD699682D240D2FCC9731FB986FD5A479B40647CA950F5` |

## Límites y entrega

**NOT RUN:** push/PR/Actions/CI remoto, Linear, integración, producción, pagos, IA LIVE, aceptación humana/deportiva, dispositivo físico, lector de pantalla, prueba offline física ni Docker/imagen de producción. No se ejecutó npm ci ni se cambiaron dependencias. No hay cambios JavaScript/CSS que requieran nuevo formato de esos recursos. La retención indefinida818 de un intento sin retorno sigue siendo deliberada.

No se promete cancelar una llamada ya enviada. La entrega no equivale a suite global verde, aprobación de revisión, integración ni cierre del ticket. Los fallos heredados se entregan con evidencia para coordinación.
