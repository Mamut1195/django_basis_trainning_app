# MAM-629 · Calendario y editor de planes y ciclos

Base local: `5cbcd32`, rama `ticket/MAM-629-calendario-editor`. Sin commit,
publicación ni integración. Revisión BT2/BT3 pendiente.

## Comportamiento

- Desde Plan se abre el calendario semanal: siete días, selector de fecha,
  semana anterior/siguiente y árbol macro → meso → micro → sesión concreta.
- Los enlaces de semana usan HTMX, conservan el foco por identificadores
  estables y funcionan por navegación GET cuando JavaScript está deshabilitado.
- Crear desde plantilla privada copia un plan propio a un linaje independiente,
  desplaza fechas y conserva solo prescripciones programadas. No existe catálogo
  de programas predefinidos. No copia ejecuciones, resultados ni identidades de
  intención de la plantilla.
- Editar plan o ciclo crea otra versión con motivo, autor y fecha efectiva.
  Conserva borradores. Solo copia sesiones futuras sin ejecución; las demás
  permanecen consultables en su versión histórica y en la agenda efectiva.
- Reprogramar, editar nombre/notas, omitir, cancelar o sustituir una sesión utiliza
  los casos de planificación existentes con bloqueo cuenta/linaje y revisión.
  La fecha y relación de intención se conservan al sustituir la prescripción.
- Antes de guardar se informa cuántas sesiones se copian y cuántas permanecen
  históricas. Una operación explícita puede afectar una sesión pasada sin
  ejecución. Conflictos y validaciones aparecen en el formulario correspondiente.
- La comparación muestra antes/después de metadatos, ciclos y sesiones; señala
  cambios de prescripción y permite consultar cada versión completa. La
  comparación de ciclos es de presentación por orden, sin atribuir identidad
  persistente entre ciclos de distintas versiones.
- Cotton, composiciones BASIS y tokens existentes; sin nuevo CSS, dependencia,
  modelo, migración, proveedor ni modificación de recursos PWA.

## Evidencia ejecutada

Logs de cada gate: `../../basis-runs/MAM-629/codex1/gate-*.txt`.
Manifiesto y hashes finales: `../../basis-runs/MAM-629/codex1/verification.json`.
Los hashes del manifiesto identifican los archivos sin necesidad de commit.

| Gate                                               | Estado   | Evidencia                                                                                          |
| -------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| Ruff check y format --check                        | VERIFIED | `gate-ruff-check.txt`, `gate-ruff-format.txt`                                                      |
| mypy core y Django estrictos                       | VERIFIED | `gate-mypy-core.txt`, `gate-mypy-django.txt`                                                       |
| architecture_check                                 | VERIFIED | `gate-architecture.txt`                                                                            |
| tests_architecture                                 | VERIFIED | `gate-tests-architecture.txt`, 209 pruebas                                                         |
| lint-imports                                       | VERIFIED | `gate-lint-imports.txt`, ocho contratos                                                            |
| djLint                                             | VERIFIED | `gate-djlint.txt`                                                                                  |
| Django check y makemigrations --check              | VERIFIED | `gate-django-check.txt`, `gate-makemigrations.txt`                                                 |
| Suite completa SQLite                              | VERIFIED | `gate-tests-sqlite.txt`; 512 pruebas; 64 omisiones                                                 |
| Suite completa PostgreSQL desechable               | VERIFIED | `gate-tests-postgresql.txt`; 512 pruebas; 2 omisiones                                              |
| Prettier del Markdown tocado                       | VERIFIED | `gate-prettier.txt`; usa `.gitignore` para comprobar este documento excluido por `.prettierignore` |
| Chromium headless                                  | VERIFIED | `gate-headless.txt` y el informe descrito abajo                                                    |
| Systems                                            | NOT RUN  | Prohibido por el encargo                                                                           |
| LIVE / proveedores reales                          | NOT RUN  | Sin Polar, IA ni SMTP reales                                                                       |
| BT2 / BT3, lector de pantalla y dispositivo físico | NOT RUN  | Revisión independiente y aceptación humana pendientes                                              |

El navegador ejecutó `run-20261027-190100-409` en
`../../basis-runs/MAM-629/acceptance-codex1/`: siete grupos de comprobaciones,
Chromium headless, viewport 390 × 844 con táctil, cero errores JavaScript y cero
solicitudes externas. El informe `result.json` registra `status=VERIFIED`,
`source_unchanged=true`, `server_stopped=true` y SHA-256 de tres capturas.
Se inspeccionaron visualmente `calendar-390.png`, `cycle-error-390.png` y `versions-390.png`.
No equivale a auditoría WCAG ni aprobación del propietario.

| Criterio de aceptación                              | Estado   | Comprobación                                                                                                 |
| --------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| Construir y recorrer bloque hasta sesión            | VERIFIED | Formularios de plan, macro/meso/micro, sesión y enlaces del árbol                                            |
| Mostrar impacto y conservar registros ejecutados    | VERIFIED | Resumen previo, nueva versión, igualdad de snapshot de ejecución y rechazo de edición de intención ejecutada |
| Usar calendario/editor sin arrastrar                | VERIFIED | Formularios, selectores, Tab/Shift+Tab/Enter, HTMX real y fallback sin JavaScript                            |
| Restricciones y errores junto a la acción           | VERIFIED | Ciclo fuera de fechas, error resumen/campo y conflicto en formulario de sesión                               |
| Crear/editar/reprogramar/omitir/sustituir/versiones | VERIFIED | Pruebas de regresión y recorrido headless con aserciones ORM de resultados                                   |
| Privacidad entre cuentas                            | VERIFIED | GET/POST privados rechazados, plantillas/objetivos propios y comparación ajena 404                           |

Las fixtures son locales y ficticias. El resultado de distancia usado para
comprobar conservación se introduce como fixture; no se atribuye a una persona
ni a un entrenamiento real. Las lecturas de fixture del auditor se ejecutan
en un hilo propio; no se deshabilita la protección asíncrona de Django.

## Comandos reproducibles desde la raíz del worktree

El wrapper local configura `config.test_settings`, base SQLite propia, IA
deshabilitada y rutas de evidencia. Invocaciones exactas, una por gate:

```powershell
../../basis-runs/MAM-629/codex1/gate.ps1 ruff-check
../../basis-runs/MAM-629/codex1/gate.ps1 ruff-format
../../basis-runs/MAM-629/codex1/gate.ps1 mypy-core
../../basis-runs/MAM-629/codex1/gate.ps1 mypy-django
../../basis-runs/MAM-629/codex1/gate.ps1 architecture
../../basis-runs/MAM-629/codex1/gate.ps1 tests-architecture
../../basis-runs/MAM-629/codex1/gate.ps1 lint-imports
../../basis-runs/MAM-629/codex1/gate.ps1 djlint
../../basis-runs/MAM-629/codex1/gate.ps1 django-check
../../basis-runs/MAM-629/codex1/gate.ps1 makemigrations
../../basis-runs/MAM-629/codex1/gate.ps1 tests-sqlite
../../basis-runs/MAM-629/codex1/gate.ps1 tests-postgresql
../../basis-runs/MAM-629/codex1/gate.ps1 prettier
```

Los comandos expandidos y códigos de salida figuran en los logs. Las suites
ejecutan las mismas etiquetas completas de `checks.yml`, añadiendo la prueba
nueva bajo `tests.regression`; no se excluyen escenarios. SQLite omite los
casos que requieren bloqueos reales; PostgreSQL ejecuta esas carreras. Las
omisiones exactas se conservan en logs con verbosidad 2.

Para otra aceptación, elegir una carpeta **nueva** y un navegador ya instalado:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
.venv-win/Scripts/python.exe -B -m tests.regression.planning_browser --output ../../basis-runs/MAM-629/acceptance-codex1/run-NUEVO --browser-executable ../../../AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

El auditor migra una SQLite exclusiva en `codex1`, levanta WSGI en loopback
en un hilo propio, cierra navegador/conexiones/servidor en `finally` y conserva
la base y el informe. No lanza un runner Python de comandos secundarios.
PostgreSQL se inicializó con `postgres-init-retry.ps1` y se ejecutó con
`postgres-server.ps1`, dentro de `codex1/pgdata`, puerto 55654, solo loopback.
Se detiene mediante `gate.ps1 postgres-stop` después de la suite; verificar
`gate-postgres-stop.txt` y `verification.json` antes de reusar el puerto.

## Fallos diagnosticados y límites

- FAILED resuelto: el primer initdb directo no pudo inicializar por token/ruta
  en el sandbox. El script con directorio de trabajo propio y ruta relativa
  terminó correctamente. Los logs de ambos intentos se conservan.
- FAILED resuelto: una aserción esperaba `no-store` sin el `private` añadido
  por el middleware. La prueba ahora exige que se conserve `no-store`.
- FAILED resuelto: el auditor accedía al ORM en el contexto de Playwright;
  se trasladaron sus lecturas de fixture a un hilo, manteniendo las guardias.
- FAILED resuelto: el editor no formateaba las fechas iniciales como ISO para
  controles date nativos. Corregido con `%Y-%m-%d` y regresión dedicada.
- FAILED resuelto: selector del auditor coincidía con dos registros históricos;
  se identifica la intención ejecutada concreta sin eliminar aserciones.
- Comparaciones de ciclos son descriptivas por orden. Para cambios complejos,
  consultar los dos árboles completos. No hay edición masiva por arrastre.
- La plantilla conserva prescripciones y referencias de medición; no calcula
  ni actualiza umbrales deportivos para el nuevo período.
- La aceptación cubre Chromium local. Otros navegadores, lector de pantalla,
  dispositivos físicos, despliegue, CI remoto y revisión independiente NOT RUN.

## Convivencia con PR abiertos

- #22 / `9b8ac8d`: único archivo compartido, `training/adapters/web/urls.py`.
  Aquí se añade el import `editor` y siete rutas; se deben conservar también
  el import `player` y sus dos rutas al integrar. `web/planning.py`, ejecución,
  reproductor y `test_player.py` permanecen intactos. Integración conjunta NOT RUN.
- #23 / `309880f`: cero archivos compartidos. No se cambian offline, service
  worker, updates, base, `_pwa` ni shell offline. Integración conjunta NOT RUN.
- Sin migraciones nuevas; el último nodo sigue siendo
  `training/0004_block_threshold_snapshot`.

El service worker se bloquea solo en el auditor; el aviso de modo sin conexión
indisponible en las capturas no acredita ni modifica la PWA. PostgreSQL propio
ya detenido: `gate-postgres-stop.txt` VERIFIED y `pgdata/postmaster.pid` ausente.
