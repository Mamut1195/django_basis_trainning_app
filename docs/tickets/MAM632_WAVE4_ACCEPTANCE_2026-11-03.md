# MAM-632 — aceptación local Wave 4, 2026-11-03

## Candidato y límites

Código de aplicación sobre `97e771daa99e23657dc24843928be136a649dfac`, worktree `t3/mam632-offline-acceptance-1`. Este recibo y el refuerzo de la prueba son cambios posteriores a ese padre; no se modificó código de producción. La ejecución de 28 pruebas precedió al refuerzo de la prueba de logout; el recorrido PWA se repitió con las nuevas aserciones. Este documento no cierra MAM-632 ni acredita integración o CI. El recibo del 2 de noviembre y PR35 son históricos; sus resultados no se atribuyen a esta ejecución. Linear leído el 3 de noviembre: In Progress, sin comentarios.

Windows, Python 3.13.7, Django 5.2.18, Playwright 1.64.0, Chromium headless 153.0.8010.12 y PostgreSQL 18.4 `127.0.0.1:55482`. Solo `basis_wave4_632_acceptance` y su test DB; se verificó que la segunda no existía antes, Django la creó y destruyó. La primera, creada para esta tarea, conserva fixtures sintéticos. `config.test_settings`, correo locmem, secreto sintético, IA desactivada, sin proveedores LIVE. El runner limita sockets Python a loopback, bloquea HTTPX real y restringe PostgreSQL a las dos bases; Chromium usa proxy local cerrado, resolución restringida y red de fondo deshabilitada. Son barreras de prueba, no auditoría de red.

## Matriz de ejecución

| Criterio | Resultado y alcance observado |
| --- | --- |
| Offline y reapertura | VERIFIED acotado: PWA Chromium descargó sesión, desconectó el contexto, guardó duración y RPE, recargó y comprobó duración y cola. La prueba usa sesión running; no demuestra recuperación de **todas** las series de fuerza ni cierre/reapertura física del navegador o dispositivo. |
| Historial completado | VERIFIED acotado: se completó offline, recargó, sincronizó, volvió a abrir offline con duración 740 bloqueada, se observó en Progreso y se comprobó que otra cuenta no la veía. |
| Pérdida antes de llegar | VERIFIED: aborto de petición antes del servidor, cero recibos, outbox pendiente y exportación con mismo `mutation_id`; reintento produce un recibo y duración 710. |
| Respuesta perdida y reintento | VERIFIED: POST real terminó 200, respuesta descartada, outbox permaneció pendiente; reintento con mismo identificador dejó un solo recibo y duración 650. No se infiere del texto de UI. |
| Corte durante transacción | VERIFIED acotado: reset TCP observado por socket del servidor después de escribir y antes de liberar transacción; lectura externa anterior al commit, commit, un recibo y replay HTTP 200 sin duplicación. La instrumentación consume el reset; no demuestra recepción parcial de cuerpo ni interrupción dentro de COMMIT ni corte desde navegador. |
| Dos contextos y conflicto | VERIFIED para dos contextos Chromium aislados de la misma cuenta: ediciones 650/660 y 720/730, conflicto visible y copia archivada; elección servidor conserva revisión y recibo; elección local produce duración 730, dos recibos y revisión 3. Son contextos, no dos dispositivos físicos. |
| Identidad, expiración y logout | VERIFIED acotado: expiración conserva stores y oculta datos; cambio de cuenta purga e invalida pestaña antigua. Respuesta simulada 503 de logout conserva stores, identidad y temporizadores, y `/api/csrf/` sigue 200 autenticado. Con servidor real, POST logout respondió 302, `/api/csrf/` respondió 302 sin seguir redirecciones, stores y temporizadores vacíos, otra pestaña invalidada y recarga offline sin sesión anterior. |
| Actualización SW | VERIFIED en Chromium: worker real servido con versión alterada en fixture, espera por pendiente, editor y temporizadores; recuperación de guarda sin respuesta; activación coordinada conserva sesión. No prueba actualización desplegada ni interrupción de energía. |
| Manifest y SW en T3 | VERIFIED acotado en navegador T3 Chrome UA 154, 1280×800, servidor propio `http://127.0.0.1:58432`: contexto seguro, manifest HTTP 200 con iconos 192/512 y display standalone; SW activo y alcance `/`. Login sintético POST 302; guardar sesión por UI produjo `sessions=1`, `outbox=0`, `archive=0` en IndexedDB. Esto no es una sincronización ni instalación. Captura indicada abajo. |
| Instalación | NOT RUN: no se instaló aplicación ni se comprobó prompt/standalone instalado. `display-mode: standalone` era falso. HTTP loopback se considera contexto seguro en este navegador; no acredita HTTPS desplegado ni acceso desde un teléfono a través de una IP de red. |
| Cuota, accesibilidad y dispositivos | NOT RUN: cuota/evicción del navegador, lector de pantalla, modo avión y Android/iOS reales. El límite de aplicación 20/21 sí se comprobó, no equivale a cuota del navegador. |
| Cobertura y entrega | NOT RUN: todos los deportes/series, navegador adicional, suite global, CI, integración en main y producción. Sin aceptación humana ni dispositivo físico no se cierra MAM-632. |

La batería HTTP/recibos/wire incluye carrera PostgreSQL de revisión y rollback; el test TCP y los cuatro escenarios de entrega Chromium son independientes. La prueba PWA usa un viewport 390×844, no un teléfono. Mensajes `Broken pipe` y respuestas 409 aparecen en escenarios de desconexión/conflicto; la suite terminó OK. La primera llamada T3 de clic falló por transporte `error sending request for url (http://127.0.0.1:3773/mcp)`; la repetición tuvo éxito.

## Comandos y evidencia

Desde este worktree, con la base exclusiva ya preparada y verificando antes que la base `test_` no exista:

```powershell
$py = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
& $py -u .cache/mam632-wave4/run.py test tests.regression.test_pwa basis.bootstrap.tests.test_sync_web basis.bootstrap.tests.test_sync_receipts basis.modules.sync.adapters.test_wire tests.regression.test_mam632_disconnect tests.regression.test_mam632_browser tests.regression.test_pwa_browser --noinput -v 2
& $py -u .cache/mam632-wave4/run.py test tests.regression.test_pwa_browser --noinput -v 2
```

La primera ejecución terminó **28 OK, cero omisiones**, 64,541 s; la segunda **1 OK**, 34,055 s, con POST/logout y readback del servidor añadidos. La segunda ejecución precedió únicamente al formato automático de esas mismas aserciones. `ruff check` y `ruff format --check` del archivo modificado, `mypy --config-file mypy-django.ini --no-incremental` (432 archivos) y `git diff --check`: VERIFIED. Tipos core, djLint, build y suite global: NOT RUN, sin cambios de producción o plantillas.

Evidencia local ignorada por Git, conservar junto al handoff; hashes SHA-256:

| Archivo `.cache/mam632-wave4/` | SHA-256 |
| --- | --- |
| `focal.log` | `a5646b5d8da7ab7c414edb08c12394434028ce2011ba40f4da711676a21dd6f4` |
| `pwa-retest.log` | `836afde1fb89be2e314338f31246d7a8e84f2669f3206e3d47719260db0835e0` |
| `pwa/browser-report.json` | `1e858b66b2542175f1a8e004e98fb424fa1b0dc53e1571802b39c1ae395b4c37` |
| `pwa/offline-reloaded.png` | `a6b3bdbd41391e69d92a88700a0ba0a714477de727ae4cbac0e025caf9a2be4e` |
| `run.py` | `4d10e8afd14f3ea0462ca020e3ecc79c811fddc17b54900e1ab61ee0b289cf4d` |
| `mypy.log` | `19c7b299b152965f5d14f84ce7a6a765dfa4ff9c0b653301ab88bfad8675388a` |

Captura T3: `C:/Users/Jonnathan/.t3/userdata/browser-artifacts/browser-screenshot-127-0-0-1-mw09tfqa-eb43b3cd.png`, SHA-256 `ce2c3d2505aca18219fbfa0ee54f14aeabef79f8ab6d7d505b0ddae963b60f4d`. El runner local deriva del guard de Wave 4, con nombres exclusivos, loopback permitido y configuración de Chromium; no se ejecutó ni editó el runner de otra base. El servidor T3 usa esa misma configuración, datos sintéticos y origen propio. No se alteró la candidata congelada 633/634.
