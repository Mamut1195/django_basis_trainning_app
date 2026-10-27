# MAM-631 · PWA instalable y sesiones disponibles sin conexión

Candidato sin commit sobre `5cbcd32`, rama `ticket/MAM-631-pwa-offline`.
Verificación local: 2026-10-27. No certifica instalación física, producción ni CI.

## Comportamiento y límites

Se extiende el worker de MAM-627 y se reutiliza su manifest. Los iconos 192/512,
metadatos de marca, Cotton UI, Alpine, HTMX, CSS y JavaScript se sirven localmente.
La composición compartida añade instrucciones de instalación y un botón cuando
el navegador ofrece `beforeinstallprompt`; Safari utiliza su menú Compartir.
Se reutilizan componentes y tokens actuales, sin dependencias ni estilos nuevos.

El worker descarga exclusivamente `/offline/` anónimo y recursos públicos de
una lista cerrada, sin credenciales. Nunca almacena HTML autenticado, snapshots,
respuestas API ni tokens CSRF en CacheStorage. Los documentos siguen intentando
la red y, ante un fallo de transporte, abren la pantalla pública offline.

«Guardar sin conexión» prepara explícitamente el snapshot privado en IndexedDB.
Las descargas admiten 20 sesiones, 2 MiB por snapshot y 10 MiB sumando snapshots
descargados (la UI usa MB como abreviatura). No se expulsan registros pendientes.
Una copia sincronizada puede eliminarse desde la lista; se vuelve a comprobar
la cola dentro de la transacción, para no borrar una edición concurrente.
Estos límites no incluyen el historial de correcciones ni la cola de operaciones:
se conservan para recuperación/exportación. La cuota real la impone el navegador.
La edición posterior puede aumentar el tamaño de una sesión. No se promete
persistencia ante borrado/evicción del navegador, modo privado o falta de espacio.

El marcador de cuenta se verifica frente a `/api/csrf/` cuando hay conexión.
Al cambiar de identidad, un Web Lock serializa la transición; primero invalida
el marcador y después limpia sessions/outbox/archive en una sola transacción.
Las lecturas y escrituras comprueban la identidad; storage/BroadcastChannel
invalidan las pestañas antiguas una sola vez y bfcache fuerza una recarga.
Un error del servidor al verificar identidad conserva las copias y bloquea su
uso; un fallo de transporte permite recuperar la última cuenta en la pantalla
pública offline. No se confunde un HTTP 500 con un cierre de sesión.

Logout conserva el flujo previo de exportación y confirmación si hay pendientes;
después de la respuesta satisfactoria limpia los tres stores y el temporizador.
Cambiar de cuenta borra deliberadamente las copias anteriores: exportar primero.
El acceso offline identifica la última cuenta preparada en ese perfil de navegador,
sin una nueva autenticación de servidor mientras no hay red. No cifra los datos
ni protege frente a alguien con acceso al perfil del navegador o a DevTools.
Usar un dispositivo de confianza. No existe sincronización entre dispositivos.

## Actualizaciones

No se usa `skipWaiting` durante la instalación. Una activación solicitada consulta
todas las ventanas del origen, incluidas las no controladas. Cada ventana congela
la interacción antes de comprobar formularios modificados, editor offline abierto,
sincronización/conflicto, temporizador activo y cola persistente. Una ventana sin
respuesta en tres segundos, un fallo de almacenamiento o una ventana nueva
aplaza la actualización. Al aplazarla se reanuda la interacción en todas ellas.
Al aceptar, `controllerchange` recarga las ventanas preparadas. La activación solo
limpia cachés públicas antiguas; no migra ni borra IndexedDB.

## Compatibilidad y aceptación pendiente

Se necesitan HTTPS (loopback es la excepción de desarrollo), Service Worker,
CacheStorage, IndexedDB, Web Locks, BroadcastChannel, AbortSignal.timeout y las
APIs modernas ya usadas por el registro. Un navegador sin estas capacidades no
tiene aceptación offline en este ticket. El formulario normal en línea conserva
su funcionamiento progresivo. No se fijan versiones mínimas móviles sin probarlas.

| Superficie | Estado y alcance |
| --- | --- |
| Chromium headless 153.0.8010.12, Windows, 390 × 844 | VERIFIED: recorrido funcional con red deshabilitada, recarga y worker real |
| Instalación Android desde navegador / pantalla de inicio | NOT RUN: requiere dispositivo real, HTTPS y menú de instalación |
| Instalación iPhone/Safari desde Compartir | NOT RUN: requiere dispositivo real; el botón Chromium no sustituye este menú |
| Modo avión, relanzamiento desde icono y almacenamiento en dispositivos reales | NOT RUN |
| HTTPS desplegado, actualización de producción, cuotas/evicción reales | NOT RUN |
| Lector de pantalla, revisión visual exhaustiva y aceptación del propietario | NOT RUN |
| Revisión independiente BT2 (código) / BT3 (QA) | NOT RUN en esta sesión; delegada para después del PR |
| Systems, LIVE/Polar, publicación y CI remoto | NOT RUN por alcance de esta ejecución |

## Evidencia ejecutada

Archivos completos fuera del repositorio:
`C:/Users/Jonnathan/Mamut system/basis-runs/MAM-631/codex2/gate-*.txt`,
`result.md`, `pr-body.md` y `candidate-source-hashes.json`.
La tabla de `result.md` conserva comandos completos, códigos y cualquier fallo
intermedio recuperado; el ejecutor debe repetir los controles que dependan del
estado Git después de crear commits.

| Gate local | Resultado |
| --- | --- |
| Ruff check y Ruff format --check | VERIFIED |
| mypy-core / mypy-django | VERIFIED: 123 / 380 archivos |
| architecture_check.py / tests_architecture | VERIFIED: 209 tests; también sobre copia LF/CI |
| import-linter --no-cache | VERIFIED |
| djLint / manage.py check / makemigrations --check --dry-run | VERIFIED |
| SQLite, config.test_settings | VERIFIED: 504 tests, 65 skipped |
| PostgreSQL desechable, config.test_settings | FAILED: 504 tests, 1 failure, 3 skipped; ver causa literal debajo |
| Prettier, solo tres JS modificados | VERIFIED; también en copia LF/CI |
| Chromium headless equivalente a aceptación de UI | VERIFIED, sin errores JavaScript |

La repetición final PostgreSQL terminó con código 1: `FAILED (failures=1,
skipped=3)`. Causa literal: `AssertionError` en
`test_contract_definition_creates_private_prescription_without_results`
(`basis.bootstrap.tests.test_planning.DjangoPlanningTests`), al comparar
`saved.definition.cycles` con `self.definition.cycles` en
`tests_architecture/planning_contract.py:31`. Es un contrato no modificado en
este ticket. No se determinó la causa raíz ni se certifica que sea un fallo
previo. Se detuvo la implementación conforme a la orden del usuario; no se
cambió training ni el test para obtener verde. El log final prevalece sobre una
ejecución PostgreSQL anterior que había terminado con éxito en esta sesión.
El candidato no tiene todos los gates aprobados.

El recorrido headless comprueba login real con cuentas ficticias, descarga
explícita, 20 descargas aceptadas y rechazo de la 21.ª, eliminación de copias
sincronizadas, contenido público de CacheStorage, edición offline, cola y valor
restaurados tras recargar. Comprueba actualización bloqueada por pendientes,
editor en otra pestaña y temporizador, y activación segura conservando la sesión.
Antes del cambio de cuenta genera correcciones locales; comprueba que la cuenta
nueva ve los tres stores vacíos y la pestaña antigua pierde acceso. Finalmente
cierra sesión y recarga sin red, sin sesiones anteriores. Los límites de 2/10 MiB
se aplican en código; sus fronteras de bytes y la evicción real no se ensayaron.

Evidencia headless final:
`C:/Users/Jonnathan/Mamut system/basis-runs/MAM-631/acceptance-codex2/run-20261027-143952-606/`.
Contiene `browser-report.json` y `offline-reloaded.png`. Se inspeccionó la captura
de la pantalla offline a 390 px; no sustituye una revisión visual de toda la UI.

Reproducción headless (directorio de salida nuevo obligatorio):

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
.venv-win/Scripts/python.exe -m tests.regression.test_pwa_browser --output <carpeta-nueva> --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

El runner de evidencia `codex2/gate.ps1 -Gate headless` impone un límite externo
de 240 segundos; Playwright añade esperas finitas y cierra contexto/navegador,
y Django cierra su servidor de pruebas. No se descargan navegadores.
La prueba sirve el worker real con una versión de caché variable para provocar
una actualización; no modifica fuentes ni implementa un worker alternativo.

PostgreSQL se inicializó en `codex2/pgdata` con trust solo para este clúster
desechable, escuchando exclusivamente en `127.0.0.1:55642`, mediante postgres.exe
directo desde un `.ps1`. El primer initdb falló por el token restringido; el
reintento `Start-Process -Wait`, usando `-D pgdata` relativo a codex2, terminó con
éxito. Se conserva pgdata; el resultado de parada está en `gate-postgres-stop.txt`.

## Coordinación

Sin commit, push, gh, fetch, merge ni cambios de configuración Git global.
PR #22 / MAM-628 toca app.js y base.html: app.js queda intacto y base.html tiene
solo tres líneas añadidas (metadatos e include). Revisar ese choque al integrar.
MAM-629 toca training, migraciones y URLs; ninguno se modifica aquí. La pantalla
offline pertenece a sync. El ejecutor hará los commits convencionales y PR draft.
