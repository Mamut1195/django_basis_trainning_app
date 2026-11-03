# Wave4: recuperación e integración local — 2026-11-03

## Alcance y estado

Continuación local autorizada por el usuario tras recuperar las tres tareas canceladas. No publicación, PR, Actions, producción, pagos, IA LIVE, actualización de dependencias ni cierre remoto. Los tres documentos untracked ajenos se preservan. La rama congelada633/634 sigue en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`.

**MAM-635 integrado localmente**, código `d88fca8` → `f2aeb68`, recibo `f14cdd8` → `6df2c4d`. Conserva la revisión independiente APPROVE recuperada en el readback anterior; esta integración incorpora también la corrección calendario `8c453f7`. **MAM-638, auditoría revisada e incorporada**, `75a67b3` → `8806f70`, solo documento. **MAM-636, todavía fuera de integración**, corrección `c1aaa93987e34be96136f91ddc754811b501057a`, recibo `ebf018f98562695e10f103bba9ba417f3214446b`; nueva revisión independiente en curso. La suite global conjunta queda pendiente de ese dictamen y de fuentes estables.

## Tareas de recuperación

Los taskId nuevos usan el prefijo `node:delegated-task:command%3Amcp%3Aaf50bba0-8a06-43a9-89af-ea4a02879d0c%3Adelegate-task%3A` y estos sufijos:

| Sufijo | Modelo | Estado leído |
| --- | --- | --- |
| `basis-wave4-636-recovery-completion-20261103-r4` | Sol6.1 high | completed; sin hijos pendientes; código/recibo entregados |
| `basis-wave4-638-recovery-completion-20261103-r2` | Terra6.1 high | completed; sin hijos pendientes; recibo entregado |
| `basis-wave4-636-independent-review-20261103-r5` | Sol6.1 high | iniciado; dictamen pendiente |

Las dos recuperaciones trabajaron en sus checkouts existentes para conservar WIP/evidencia, sin nuevos checkouts ni agentes anidados. El revisor636 tiene fuentes inmutables y escritura solo de evidencia propia, DB separada `basis_wave4_636_review5`/`test_basis_wave4_636_review5`.

## Verificación nueva de coordinación: MAM-635 y calendario

Comandos ejecutados sobre `6df2c4def8e165697294ce4e62f335672fa2a8a7`. El commit posterior `8806f70` solo añade el informe638. Python raíz3.13.7, PostgreSQL18.4 en loopback55482, usuario sintético `basis_wave0`; DB exclusivas de coordinación `basis_wave3_integration`/`test_basis_wave3_integration`. `config.test_settings`, AI0 salvo fixture, secretos ficticios, HTTPX real y sockets externos rechazados; proveedores simulados. No es firewall del sistema. Runner propio `.cache/wave4-recovery-20261103/run_guarded.py`, SHA256 `A538351A6AE8C533C1C327C9D96A3F492D5F0E3506553A84CA77A7A31FDB19AC`.

| Check nuevo | Resultado |
| --- | --- |
| Cancelación/jobs/provider policy/reconciliación/pricing/fence + calendario/edges/aceptación635 | VERIFIED:113 pruebas,0 omisiones,38.542s,exit0 |
| Puras y contratos fake | VERIFIED:285 pruebas,4.251s,exit0 |
| mypy core/Django | VERIFIED:135/435 fuentes,exit0 |
| Arquitectura e imports | VERIFIED:fronteras;8 contratos kept/0 broken |
| Ruff check y formato | VERIFIED:exit0;446 archivos ya formateados |
| djLint | VERIFIED:52 templates,0 cambios,exit0 |
| Formato CSS/JS | VERIFIED:Prettier CLI con los mismos patrones de package.json,exit0 |
| Django check y migraciones pendientes | VERIFIED:sin incidencias/sin cambios,exit0 |
| Guards HTTP sync/async, TCP externo y DB ajena | VERIFIED:rechazados antes de transporte; conexión propiaPG18.4 |
| Diff check | VERIFIED:sin errores |

Los 113 casos incluyen ambas carreras de cancelación/claim, cancelación/enqueue, integridad/replay/ownership/CSRF y la aceptación que antes fallaba por calendario. El resultado global fallido del autor se preserva en su recibo histórico; no se rebautiza como PASS. Esta focal nueva no es una suite global.

Cada ejecución se captura con `capture.py <label> <argv...>`, abriendo archivos nuevos exclusivamente; metadata `<label>.json` conserva argv/cwd/HEAD/fecha/duración/exit/log SHA256. Focal: `focal635.log`, SHA256 `f98b1b69648c4cc4f2abea040dfd011ea13a78cb462489d4c3c80db57099c852`. Puras: `pure635.log`, SHA256 `75964916371c593b892a3c8203f3cb3fad5ca8bbd2a9bbe78a7acd3694fed98f`. Los demás labels son `mypy-core635`, `mypy-django635`, `architecture635`, `imports635`, `ruff635`, `format635`, `djlint635`, `prettier635-retry`, `django-check635`, `migrations635` y `guard03`. Evidencia ignorada, no disponible en un clon nuevo.

## Navegador T3 sobre integración local

VERIFIED LOCAL_SYNTHETIC en `8806f70`: servidor propio `127.0.0.1:8767`, datos nuevos de coordinación y proveedor deshabilitado fuera de la creación sintética de jobs. Login real, detalle pending con reserva y formulario, botón POST real y redirección a Cancelada/costo0; al reabrir los dos jobs conservan estado,0 formularios,0 polling y sin overflow horizontal. Escritorio1280×800 y viewport390×844, emulación de tamaño sobre navegador de escritorio, no dispositivo físico.

Evidencia DOM: `.cache/wave4-recovery-20261103/browser-evidence.json`, SHA256 `71F5B8C60B68B142657E575C803FDB9EC8C3A6D2178BA45CE28722C075991F9F`. Capturas en `C:/Users/Jonnathan/.t3/userdata/browser-artifacts/`: `browser-screenshot-127-0-0-1-mw0rtpcj-de944d7c.png` (escritorio) y `browser-screenshot-127-0-0-1-mw0ru22i-85bc8388.png` (móvil). Conflicto409 se repitió mediante cliente Django en la focal, no en navegador durante este corte. El servidor propio se detuvo mediante su sesión; PostgreSQL compartido permanece activo.

## Auditoría638: revisión de coordinación

Se recalcularon las26 entradas del manifiesto del agente sin discrepancias; commit limitado al nuevo informe, diff check satisfactorio. Se contrastaron nuevamente las fuentes primarias [PyPA](https://github.com/pypa/advisory-database/blob/main/vulns/certifi/PYSEC-2026-4320.yaml) y [proyecto certifi](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2): respaldan el identificador único, versión afectada y severidad crítica. El rango se corrige desde2026.10.18 y PyPA recomienda2026.10.19 o posterior. No se verificó explotabilidad concreta ni se aplicó/probó actualización; la remediación requiere un cambio posterior separado. El recibo638 conserva los alcances23/49/49, duplicación del ID en la salida, npm sin hallazgos reportados para su lockfile y límites TLS históricos.

## Incidencias conservadas y pendientes

El primer intento de captura usó un ejecutable relativo que `subprocess` no resolvió en Windows (`WinError2`), antes de ejecutar el guard; salida en historial de herramientas y `guard.log` vacío, sin metadata fabricada. Se reintentó con ruta absoluta. `guard02` rechazó correctamente transportes externos pero agotó timeout de PostgreSQL: no había servidor activo. `pg_ctl status` sobre el directorio contenedor inicialmente indicó que no era cluster; el cluster real estaba en su subdirectorio `data`. Se inició exclusivamente el cluster sintético histórico, mismo endpoint; pg_ctl agotó30s mientras el servidor recuperaba un cierre interrumpido. Se conservan log de arranque/recuperación y timeout; `pg_isready` después confirmó accepting connections, y `guard03`/focales pasaron. No se borraron archivos de recuperación ni se paró el servidor.

El wrapper `cmd /c npm.cmd run format:check` falló por sintaxis antes de ejecutar el check (`prettier635.log`). Se usó directamente Node+Prettier con los mismos argumentos/patrones, sin instalar paquetes ni cambiar assets; reintento aprobado. `docker version` no pudo conectar a `dockerDesktopLinuxEngine` (named pipe inexistente); no se inició Docker Desktop ni se intentó build/operaciones. El primer preview se abrió antes del servidor y recibió `net::ERR_CONNECTION_REFUSED`; tras arrancarlo, la nueva pestaña propia completó ambos recorridos.

NOT RUN todavía: suite global conjunta, revisión636 terminada, integración636, Docker/imagen/operaciones, CI remoto, publicación, dispositivos físicos, lector de pantalla, revisión deportiva/humana/LIVE, actualización y reauditoría tras remediación638. Polar sigue pospuesto por el usuario. Ningún resultado local equivale a cierre de ticket.
