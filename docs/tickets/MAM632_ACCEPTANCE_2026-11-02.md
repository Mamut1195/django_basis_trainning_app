# MAM-632 — primera aceptación local, 2026-11-02

## Alcance y entorno

Worktree aislado `t3/mam-632-local-acceptance`, padre `2b9ed1c15c87183df9b8be7f1163dcd9bd246c43`. Esta aceptación no corresponde al SHA integrado de MAM-820 ni cierra MAM-632. Sin cambios en recorder, Progress, contratos compartidos, bootstrap ni migraciones. No se modificó código de producción.

Python 3.13.7, Django 5.2.18, Playwright 1.64.0, Chromium headless 153.0.8010.12, Windows, viewport 390 × 844, PostgreSQL 18.4 en `127.0.0.1:55482`, base desechable autorizada `basis_offline632`; Django creó y destruyó `test_basis_offline632`. Configuración `config.test_settings`, secreto sintético, `AI_ENABLED=0`, correo en memoria, cuentas y datos ficticios. `sitecustomize.py` impidió conexiones Python fuera de `127.0.0.1` (probado contra 192.0.2.1); Chromium usó proxy local cerrado, resolución restringida y red de fondo deshabilitada. La red offline de cada contexto se controló con Playwright. Estas barreras son controles del entorno de prueba, no una auditoría de seguridad de red.

## Matriz

| Escenario | Resultado y evidencia |
| --- | --- |
| Offline y reapertura | VERIFIED: worker real; descarga explícita, edición sin red, cola y valores tras recarga. También 20 descargas, rechazo de la 21.ª y eliminación de copias. `browser-run-127/browser-report.json` y `offline-reloaded.png`. |
| Respuesta perdida y reintento | VERIFIED para una mutación: el interceptor dejó completar el POST con 200 y descartó la respuesta; el cliente conservó pendiente y reintentó. PostgreSQL mostró un único recibo y el valor guardado. La prueba nueva está en `tests/regression/test_mam632_browser.py`. |
| Conflicto dos clientes | VERIFIED para dos contextos Chromium independientes, misma cuenta y sesión: ambos editan offline, uno sincroniza y el otro ve valores locales/remotos; selecciona conservar servidor y archiva copia local sin nueva revisión ni recibo. La carrera de revisiones en PostgreSQL también pasó en `ReceiptConcurrencyTests`. |
| Identidad/logout | VERIFIED: cambio de cuenta vacía los tres stores e invalida pestaña antigua; fallo de logout conserva datos y temporizadores; logout exitoso limpia identidad/stores y evita exposición al recargar offline. También se comprobaron retorno a la misma cuenta y cookie vencida. |
| Service worker | VERIFIED en Chromium: caché pública, bloqueo por cola/editor/temporizadores, recuperación de guarda que no responde y activación coordinada preservando sesión. El test sirve el worker real con versión variable. |
| Contratos sync | VERIFIED: 22 pruebas de PWA HTTP, wire, sync HTTP y recibos, incluyendo rollback, aislamiento, replays y carrera real PostgreSQL. No implica aceptación integral de entrenamiento. |
| POST interrumpido antes o durante la llegada al servidor | NOT RUN: descartar una respuesta después de un 200 no reproduce todas las interrupciones posibles. |
| Resolución de conflicto enviando versión local, historial completado y otros navegadores | NOT RUN en esta aceptación. |
| Dispositivos físicos, instalación Android/iOS, modo avión, HTTPS desplegado, cuotas/evicción, lector de pantalla | NOT RUN; viewport y contextos emulados no son dispositivos físicos. |
| Candidato integrado MAM-820, suite completa, CI remoto, producción | NOT RUN. Repetir aceptación sobre el SHA integrado y coordinar cualquier hallazgo en recorder/Progress con su dueño. |

## Ejecución y trazabilidad

Registros completos en `.cache/mam632/`: `server-tests.log` (22 OK), `browser-tests-127.log` (1 OK), `browser-run-127/browser-report.json`, `delivery-tests-verified.log` (1 OK), scripts `sitecustomize.py`, `browser_guarded.py`, `delivery_guarded.py` y captura. La carpeta es evidencia local ignorada por Git; conservarla en el handoff si se requiere reproducibilidad fuera de este worktree.

Ejecutar desde la raíz, con la base desechable autorizada disponible y sin una `test_basis_offline632` preexistente:

```powershell
$py = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
$env:PYTHONPATH = "$(Resolve-Path .cache/mam632);$(Get-Location)"
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DJANGO_SECRET_KEY = 'mam632-local-synthetic-key'
$env:AI_ENABLED = '0'
$env:DATABASE_URL = 'postgresql://basis_wave0@127.0.0.1:55482/basis_offline632'
$env:HTTP_PROXY = 'http://127.0.0.1:9'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$env:NO_PROXY = '127.0.0.1'
& $py manage.py test tests.regression.test_pwa basis.bootstrap.tests.test_sync_web basis.bootstrap.tests.test_sync_receipts basis.modules.sync.adapters.test_wire --noinput -v 2
& $py .cache/mam632/browser_guarded.py --output .cache/mam632/browser-run-NUEVO --browser-executable 'C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'
& $py .cache/mam632/delivery_guarded.py
```

Ejecutar secuencialmente: Django crea y destruye la misma base de pruebas. El primer intento del wrapper no encontró `tests` por falta de raíz en `PYTHONPATH`; el segundo recibió `ERR_NAME_NOT_RESOLVED` porque el runner escogía `localhost` bajo la restricción de red. El wrapper final fija `127.0.0.1`. La prueba nueva primero contó dos solicitudes al combinar reconexión automática y clic, y luego encontró `SynchronousOnlyOperation` al consultar ORM durante Playwright; se corrigieron el estímulo y la lectura en hilo separado. Los registros fallidos se conservan. El warning de `staticfiles` ausente se observó; los recursos del test fueron servidos y las pruebas finales pasaron. El `Broken pipe` y el 409 del escenario de respuesta perdida/conflicto son esperados en ese caso.

## Ampliación de aceptación local — 2026-11-02

Sobre el mismo padre `2b9ed1c15c87183df9b8be7f1163dcd9bd246c43`, sin cambios de producción ni integración de MAM-820: `tests.regression.test_mam632_browser.OfflineDeliveryBrowserTests` ejecutó **3 pruebas OK** en PostgreSQL 18.4 desechable y Chromium con los mismos controles de red. El interceptor que aborta antes del servidor conservó el identificador de mutación y los datos de la cola en `basis-local-v1`, con cuenta coincidente; el servidor tenía cero recibos antes del reintento y uno después. El escenario de respuesta perdida tras HTTP 200 es distinto y ya había acreditado idempotencia al reintentar. El conflicto de dos contextos muestra 720 remoto y 730 local; al elegir local quedó 730, revisión 3, dos recibos de operaciones distintas y copia archivada.

La batería de servidor (`tests.regression.test_pwa basis.bootstrap.tests.test_sync_web basis.bootstrap.tests.test_sync_receipts basis.modules.sync.adapters.test_wire`) ejecutó **22 OK** en PostgreSQL. `mypy --no-incremental` core 130 y Django 412 archivos, checker de arquitectura, ocho contratos Import Linter, `ruff check .` y `ruff format --check` (420 archivos) pasaron. El primer mypy Django detectó anotaciones ausentes y reutilización de métodos con self incompatible en el archivo de prueba; se corrigió y volvió a pasar. Registros nuevos: `.cache/mam632/server-extended-20261102.log` y `.cache/mam632/delivery-final-20261102.log`.

**NOT RUN:** interrupción durante la recepción o commit en servidor; no se puede inferir del aborto previo ni de la respuesta perdida. También siguen pendientes aceptación del historial completado, navegadores adicionales, dispositivos físicos y SHA integrado, CI remoto y producción.

## Repetición sobre MAM-820 integrado — 2026-11-02

Base `98ea2923f6a675001bc9951f971d8a43759b58a3` (merge MAM-820), con el commit anterior aplicado mediante cherry-pick `685e162`. Worktree `t3/mam632-offline-acceptance`. Se utilizó únicamente PostgreSQL 18.4 local, `basis_wave2_632` y su base de pruebas exclusiva `test_basis_wave2_632`; la inspección previa confirmó que esta última no existía. `config.test_settings`, secreto sintético, `AI_ENABLED=0` y cuentas ficticias. El guard de Python permite conexiones solo a `127.0.0.1`; Chromium usa proxy local cerrado, resolución restringida y red de fondo deshabilitada. Las pruebas web solo accedieron al servidor local. Estos controles no constituyen auditoría de red.

| Comprobación | Resultado de esta repetición |
| --- | --- |
| HTTP PWA, sincronización, recibos y codec | VERIFIED: 22 pruebas OK en PostgreSQL, incluida la carrera real de revisión y el rollback al fallar la creación del recibo. |
| Entrega y conflictos | VERIFIED: batería final de 4 pruebas Chromium OK, incluyendo historial: aborto antes del servidor, respuesta perdida después del 200 con reintento idempotente y dos contextos independientes resolviendo a favor del servidor o del cliente. |
| Historial completado | VERIFIED: prueba Chromium adicional: completar offline, recargar y recuperar duración y estado, sincronizar, volver a abrir offline con campos bloqueados, encontrar en Progreso y no mostrarlo en otra cuenta. Mientras permanece pendiente, el cliente permite editarlo; el bloqueo comprobado es posterior a la confirmación. |
| Logout, aislamiento y service worker | VERIFIED: prueba PWA Chromium OK, 15 comprobaciones en `pwa-run/browser-report.json`, incluyendo expiración, limpieza multi-pestaña, logout fallido y exitoso, actualización bloqueada y activación segura. |
| Corte durante recepción o commit | NOT RUN: el aborto previo al servidor y la pérdida de respuesta posterior al 200 no prueban ese momento. El rollback inducido al guardar el recibo comprueba atomicidad de servidor, no una desconexión de red durante commit. |
| Otros navegadores, dispositivos físicos, instalación, HTTPS desplegado, cuotas/evicción, accesibilidad asistiva, suite completa y CI remoto | NOT RUN. Chromium headless, viewport móvil y contextos separados son emulación, no dispositivos físicos. No se ha integrado este trabajo en main ni se cierra MAM-632. |

Evidencia ignorada por Git conservada en este worktree: `.cache/mam632-wave2/server.log`, `delivery.log`, `history.log`, `history-retry.log`, `delivery-history.log`, `delivery-final.log`, `pwa.log` y `pwa-run/browser-report.json`. `delivery-history.log` registra el primer fallo por selector escrito con `?`; `history.log` registra la expectativa incorrecta de bloqueo antes de confirmar el envío. Ambos se corrigieron sin eliminar la verificación posterior. Se observó el aviso de directorio `staticfiles` ausente; el servidor de pruebas sirvió los recursos y los recorridos pasaron. Un `Broken pipe` aparece en el recorrido de red interrumpida.

Controles adicionales de esta repetición: `ruff check` y `ruff format --check` sobre `tests/regression/test_mam632_browser.py`, `mypy --config-file mypy-django.ini --no-incremental` (414 archivos) y `git diff --check`: VERIFIED. No se ejecutó build ni suite completa.

Para reproducir, preparar una base exclusiva con permiso para crear su base `test_`, verificar que no exista antes y ejecutar secuencialmente. Los wrappers locales `delivery_guarded.py` y `browser_guarded.py` fijan el host de Django a `127.0.0.1`, agregan los argumentos de aislamiento Chromium descritos arriba y activan `BASIS_PWA_BROWSER=1`; `sitecustomize.py` restringe sockets Python. Se copiaron de la evidencia del worktree anterior, sin modificar ese worktree. No reutilizar los nombres de base del ejemplo sin autorización.

```powershell
$py = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
$env:PYTHONPATH = "$(Resolve-Path .cache/mam632-wave2);$(Get-Location)"
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DJANGO_SECRET_KEY = 'mam632-synthetic-local'
$env:AI_ENABLED = '0'
$env:DATABASE_URL = 'postgresql://basis_wave0@127.0.0.1:55482/basis_wave2_632'
$env:HTTP_PROXY = 'http://127.0.0.1:9'; $env:HTTPS_PROXY = 'http://127.0.0.1:9'; $env:NO_PROXY = '127.0.0.1'
& $py manage.py test tests.regression.test_pwa basis.bootstrap.tests.test_sync_web basis.bootstrap.tests.test_sync_receipts basis.modules.sync.adapters.test_wire --noinput -v 2
& $py .cache/mam632-wave2/delivery_guarded.py
& $py .cache/mam632-wave2/browser_guarded.py --output .cache/mam632-wave2/pwa-run-NUEVO --browser-executable 'C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'
```

## Diseño previo: corte real durante transacción

En una prueba PostgreSQL con servidor HTTP local real, autenticar una cuenta sintética y enviar un cuerpo válido con cookie y CSRF por socket TCP loopback. Un parche limitado a la prueba envolverá `DjangoReceiptRepository.save`: después de escribir el recibo dentro de la transacción, señalará una barrera y esperará su liberación. Desde otra conexión PostgreSQL se comprobará que la sesión anterior y la ausencia del recibo siguen visibles. Con el servidor retenido, el cliente cerrará el socket mediante reset TCP (`SO_LINGER`); se registrará ese cierre antes de liberar la barrera. Un segundo envoltorio observará el retorno de la salida de la unidad de trabajo para esperar el commit, sin temporizaciones arbitrarias. Después se comprobarán la sesión y el único recibo confirmados y se repetirá el mismo cuerpo y `mutation_id` por una nueva conexión HTTP autenticada, comprobando respuesta y ausencia de duplicación.

La secuencia acredita cierre local del socket durante una transacción abierta y el resultado observado del servidor y reintento. No demuestra un corte de alimentación, un cliente navegador ni una interrupción exactamente dentro de la instrucción COMMIT. Los límites de espera solo sirven para fallar ante bloqueo; no establecen el orden. La fixture no modifica producción.

Refuerzo del diseño, antes de ejecutar la variante: capturar el socket aceptado por el servidor de prueba y observar allí el reset mediante `recv(MSG_PEEK)` antes de liberar la barrera. Esta observación consume el error de socket; es instrumentación de la fixture, no una afirmación sobre cómo reaccionaría una implementación de servidor distinta.

### Resultado de la ejecución delimitada

**VERIFIED:** en PostgreSQL 18.4 y TCP loopback, la nueva prueba `tests.regression.test_mam632_disconnect` observó esta secuencia, forzada por eventos y sin sleeps: (1) sesión y recibo escritos dentro de la transacción del servidor; (2) otra conexión aún ve la revisión y duración anteriores y ningún recibo; (3) el cliente cierra con reset TCP; (4) el socket aceptado por el servidor informa `ConnectionResetError`; (5) se libera la barrera y termina la unidad de trabajo; (6) la sesión y un solo recibo son visibles; (7) una nueva petición HTTP autenticada con el mismo cuerpo y `mutation_id` devuelve 200 y exactamente el resultado del recibo, sin incrementar revisión ni duplicarlo. La lectura del reset en el socket del servidor consume ese error, por lo que este ensayo no mide si el servidor sin instrumentación detecta el reset al enviar su respuesta.

Comando focal: `manage.py test tests.regression.test_mam632_disconnect basis.bootstrap.tests.test_sync_receipts --noinput -v 2`; **12 pruebas OK**, incluidos rollback inducido y carrera de revisión como escenarios independientes. Registro `.cache/mam632-wave2/tcp-reset-typed.log`. El primer chequeo mypy encontró dos anotaciones incorrectas del handler en la fixture; se corrigieron y se repitió. Se usó exclusivamente `basis_wave2_632` y `test_basis_wave2_632`, configuración y barreras de red de la sección anterior; la base de prueba no existía antes de ejecutar.

`mypy --config-file mypy-django.ini --no-incremental`: **VERIFIED**, 415 archivos. Ruff y formato del archivo de prueba y `git diff --check`: **VERIFIED**.

Este resultado cubre un reset de conexión después de la escritura y antes de liberar el commit; **no** reproduce corte durante la recepción del cuerpo ni una interrupción dentro de COMMIT, una desconexión del navegador o un dispositivo físico. La prueba HTTP opera directamente con un socket, no con la cola de IndexedDB. No se repitieron suite completa ni CI remoto.

### Corrección de portabilidad de SO_LINGER

La fixture selecciona `struct.pack('HH', 1, 0)` en Windows y `struct.pack('ii', 1, 0)` en POSIX, sin cambiar las barreras ni las aserciones. Coordinación confirmó en el contenedor local existente `python:3.13.7-slim`, con `--network none` y solo `probe.py` montado: plataforma `posix`, `getsockopt(SO_LINGER)` de 8 bytes, `hh` falla con `OSError 22` e `ii` pasa. El registro compartido es `.cache/wave2-20261102/linger-linux.log` en el repositorio raíz; se leyó sin modificarlo. El primer intento de coordinación con `python -c` falló con `NameError` por quoting PowerShell; el probe final en archivo pasó.

**VERIFIED adicional:** en Ubuntu WSL, Python 3.12.3, un probe TCP loopback independiente con `ii` de 8 bytes produjo `ConnectionResetError` en el socket receptor. **NOT RUN:** la prueba Django/PostgreSQL completa en Linux y CI remoto; los probes no acreditan esa ejecución.

**VERIFIED en Windows tras la corrección:** `manage.py test tests.regression.test_mam632_disconnect basis.bootstrap.tests.test_sync_receipts --noinput -v 2`, 12 pruebas OK en PostgreSQL exclusivo; registro `.cache/mam632-wave2/tcp-reset-portable.log`. Ruff y formato del archivo modificado, y mypy Django estricto en 415 archivos: OK. No se repitió navegador ni suite completa.
