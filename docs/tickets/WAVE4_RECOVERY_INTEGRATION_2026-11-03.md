# Wave4: recuperación e integración local — 2026-11-03

Estado final de este avance local: MAM-635 y el harness636 revisados, incorporados y validados juntos; auditoría638 revisada e incorporada. El cierre verificado está al final y en [el handoff](../HANDOFF_WAVE4_RECOVERY_2026-11-03.md). Las secciones intermedias conservan los cortes anteriores y sus fallos, sin reescribirlos.

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

## Comprobaciones mientras termina la revisión636

Sobre `37179be`, fuentes de producto idénticas a `6df2c4d`, se ejecutaron dos controles adicionales previstos por el workflow local: `manage collectstatic --noinput` aprobó (10 archivos copiados,177 sin cambios) y `manage test benchmark_calendar_queries --noinput -v1`, con `PYTHONPATH` apuntando a `scripts`, aprobó un caso en5.070s. Para10/100/1000 registros mantuvo selection2/statuses0/scheduled2/today11; esto acredita conteos de consulta, no capacidad de producción. Capturas `collectstatic635.json`/`.log` (SHA log `392d9d8f152610c4bf8f3848b7542a7ab0bc56a0d0b0977b95a3683000c4e20a`) y `calendar-benchmark635.json`/`.log` (`3b95f8c9faba55ff0d792632a068a887b120731219e3f4747814898e4c1056ac`) bajo la misma caché de coordinación.

Coordinación recalculó también las135 entradas del manifiesto R4 de636 sin discrepancias (SHA del manifiesto `abec2c95a91ea7d946c5c29ba0bbab1fa5cb6c3618280db7015037baf50543ac`); fuentes siguen idénticas a `c1aaa93`, y corpus del padre/candidato coincide con `cefef9c79c093850e31ca570c9bf2706d639ba45c90fc855c01e56975a233d8e`. Esto verifica integridad, no sustituye la revisión independiente. `task_status` de R5 confirmó `running`, sin preguntas pendientes; no se duplicó ni reinició la revisión y636 permanece fuera de integración.

## Revisión636 R5 terminada: REQUEST_CHANGES

R5 terminó `completed`, sin hijos ni preguntas pendientes; dictamen **REQUEST_CHANGES**, un P2 nuevo `R5-N1`. R1–R6 superan sus controles independientes, pero en EV017 `null_content` borrar una sola vez `UsagePeriod.spent` después del primer worker real y antes de capturar `after` conserva `cost=0.00001800`, tokens20/10, reserva0 y gasto0. El caso y guard técnico aún pasan. La comparación after/after_second no basta cuando ambos snapshots ya están corruptos. Sigue siendo mutación del evaluador, no defecto atribuido al producto intacto.

Informe en `t3-19a75c82/.cache/mam636-review-r5/REVIEW.md`, SHA256 `488CBA5634BF397A1627DFA3ACD1E402321520CDB285A9590FC5C497982AC317`; manifiesto `BB66F6011013D7E34318553603555884C9697DDE428E76AA86C59FC84AB01D8E`. Coordinación verificó sus84 entradas sin discrepancias. No se incorpora636. La nueva corrección Sol6.1 high R6 tiene taskId con el mismo prefijo de tareas de recuperación y sufijo `basis-wave4-636-settlement-oracle-fix-20261103-r6`, checkout aislado `t3-b2aa5a24`, desde el plan `8ac8fe3`, DB `basis_wave4_636_fix6`/`test_basis_wave4_636_fix6`. Debe reproducir RED→GREEN y someterse a otra revisión independiente. No se modificó el checkout bajo revisión.

## Suite completa de coordinación:635/calendario

**VERIFIED LOCAL:** `manage test --noinput -v2`, con el runner propio, ejecutó **1074 casos en440.212s:1064 satisfactorios,10 omisiones optativas,0 fallos/errores**, exit0. Fuentes estables y HEAD `8ac8fe30cf7478d6d8a9aba5e47d330000bbf426` durante la corrida; fuentes de producto/tests iguales a `6df2c4d`, cambios intermedios solo documentales. Metadata `full635.json`, log `full635.log`, SHA256 `0747a425e802fb399c6862477944bdf2e5cdda68486c932fcf12274b789d6d96`, en la caché de coordinación. Incluye contratos puros y PostgreSQL, migraciones y carreras; no se añadieron clocks globales ni se omitieron pruebas fallidas. Los ocho errores de calendario históricos no se reprodujeron en este conjunto corregido.

Las diez omisiones corresponden a navegadores optativos (hiking, cuatro offline632 originales, multisport632, PWA, running, swimming y trekking); no acreditan esos recorridos como ejecutados en esta suite. La repetición T3635 de escritorio/viewport móvil se documentó por separado arriba. La suite **no contiene el harness636**, aún rechazado y fuera de integración; tras corregir y aprobar636 corresponde validar su combinación final. CI/Docker/operaciones siguen con los límites ya registrados. Los tres documentos ajenos untracked y la rama congelada permanecen intactos.

## Corrección636 R6 fijada y nueva revisión R7

El código R6 quedó fijado en `a676e37a6f3ca2f05b5837d7c7f6e1567a5a457e`, checkout `t3-b2aa5a24`; diff de tres archivos limitado a harness, runner DB exclusiva y prueba nueva. El recibo del autor sigue en preparación; no se declara la tarea terminada todavía. Coordinación leyó la focal estable:21 pruebas aprobadas en25.423s, y mypyDjango441 fuentes sin errores. La ampliación usa los ledgers anteriores a ambos workers y el uso recibido, con pricing congelado y `usage_cost` existente; compara costo/tokens/identidad y ledger original en ambos estados. No usa el costo ya liquidado como único oráculo.

Fuentes verificadas idénticas a ese HEAD antes de delegar una **nueva revisión independiente R7**, Sol6.1 high, taskId `node:delegated-task:command%3Amcp%3Aaf50bba0-8a06-43a9-89af-ea4a02879d0c%3Adelegate-task%3Abasis-wave4-636-settlement-independent-review-20261103-r7`. Revisor solo lectura del mismo checkout, evidencia propia `.cache/mam636-review-r7/` y DB distintas `basis_wave4_636_review7`/`test_basis_wave4_636_review7`. Debe invertir el control completo R5-N1, contrastar costo+gasto/tokens/doble cargo y conservar la detección R1–R6 y los denominadores. Dictamen pendiente; no se integra por el GREEN del autor. Solo el recibo puede cambiar mientras se revisan las fuentes fijadas.

R6 terminó después `completed`, sin hijos ni preguntas pendientes. Recibo final `1f45b15f66ae30cb885fd36049e2efd56e55aedc`, árbol limpio y fuentes idénticas al código fijado. Coordinación leyó el recibo y recalculó las112 entradas de `.cache/mam636-fix6/artifact-manifest.json` sin discrepancias; SHA256 del manifiesto `0686eb811f72b7b751f8b1b34652aac940e000f60750fdeb063b02e74559c7da`. Se conservan RED de una prueba (PASS!=FAIL) y GREEN estable21,127 regresiones de worker,285 puras, tipos core135/Django441 y checks pertinentes del autor; no se atribuyen a coordinación como ejecuciones nuevas. Baseline89 observaciones PASS/0FAIL/3INCONCLUSIVE y7/34 expectativas PASS/3I/24NOTRUN;5/17 casos ejecutados y0 aceptados deportivamente. El control positivo conserva gasto previo, reserva adicional y contadores; cinco negativos completos detectan gasto borrado, costo/ledger alterados, tokens divergentes y doble cargo. Dictamen R7 e integración/suite final siguen pendientes.

## Cierre verificado del avance local

R7 terminó **completed / APPROVE** para `a676e37a6f3ca2f05b5837d7c7f6e1567a5a457e`, sin hijos ni preguntas pendientes. Repitió21 focales y20 controles independientes, incluidos R1–R6, el borrado único R5-N1, costo/gasto corruptos coherentes entre sí, doble cargo, decoder divergente y evidencia ausente. Los negativos completos producen FAIL localizado y guard rechazado; baseline sin mutación conserva17 casos/34 expectativas y0FAIL. No hay P1/P2 materiales reproducidos pendientes dentro del corte técnico revisado. Informe R7 SHA256 `043dba2e13d92416ab608d2cf92c429eb7cf9fd13f249d655da4ee05f6908eb1`; manifiesto `ccbb1b750f97d009953d9803f70d9281f9417e22660b5dd0c789f3f6f9ac076a`,89 entradas recalculadas por coordinación sin discrepancias. Ambos permanecen en `t3-b2aa5a24/.cache/mam636-review-r7/`.

Solo después del dictamen se incorporaron los seis commits636: `7594a4f`→`26e6b60`, `4d59594`→`409912b`, `c1aaa93`→`c07becc`, `ebf018f`→`ef7c950`, `a676e37`→`3a3c0cd` y `1f45b15`→`efa9c4c`. La comparación Git de todas las fuentes/config/tests/scripts y entradas de dependencias con el candidato aprobado no presenta diferencias. El código de producto/assets/config sigue idéntico a `8806f70`, sobre el que se repitió navegador635. No se actualizaron dependencias ni se modificó el corpus.

### Validación final nueva de coordinación

Fuentes estables en **`efa9c4c1fad4c9038ea6d6d736daed860251cbe9`**, mismo HEAD antes y después de cada comando final:

| Check | Resultado ejecutado |
| --- | --- |
| Suite completa `manage test --noinput -v2` | **1095 casos:1085 satisfactorios,10 omisiones optativas,0 fallos/errores;468.546s;exit0** |
| Tipos core/Django, cachés nuevas separadas |135/441 fuentes;exit0 |
| Ruff/formato sin caché |exit0;452 archivos ya formateados |
| Arquitectura/imports |fronteras válidas;8 contratos kept/0 broken;exit0 |
| Django check y makemigrations --check --dry-run |sin incidencias/sin cambios;exit0 |
| Diff y procedencia |Git lógico sin diferencias con candidato; corpus intacto; verificación adicional descrita abajo |

La suite global contiene ahora las21 pruebas636 y la cancelación635/calendario, además de contratos puros, ORM, HTTP y carreras PostgreSQL. Sus diez omisiones son las mismas categorías optativas de navegador descritas arriba. Los checks anteriores de djLint, Prettier, collectstatic, benchmark y navegador mantienen su atribución y alcance; no hubo cambios posteriores de producto/templates/assets que invaliden esa evidencia.

Log global `full-final636.log`, SHA256 **`1a8afa0d6c036e5599093219c0622944c59c71c56483fce0c849d3cc33033e83`**. `full-final636.json` conserva argv, entorno MAM636 de salida, fecha, duración de proceso y HEAD antes/después. Labels finales: `mypy-core-final636`, `mypy-django-final636`, `ruff-final636`, `format-final636`, `architecture-final636`, `imports-final636`, `django-check-final636`, `migrations-final636`. No se ejecutó el runner636 default sobre la base del autor: se usó el runner de coordinación y sus dos bases autorizadas.

`full-final636-baseline.json` registra SIMULATED,5/17 casos ejecutados,3 casos técnicos con todas sus expectativas PASS;7/34 expectativas PASS,3INCONCLUSIVE,24NOT_RUN,0FAIL;89 observaciones PASS,3INCONCLUSIVE,0FAIL;0 casos aceptados deportivamente. Human/sport PENDING, rúbrica PROPOSED_NOT_APPROVED, LIVE/final acceptance NOT_RUN. Los mutantes y la respuesta con fuga se conservan por separado, sin mezclarlos con el baseline.

### Procedencia e incidencias de los verificadores

Los hashes crudos del mapa de364 fuentes difieren entre checkouts: revisión `d51e897694bd7ae9d2563c66c3ec87f88cccb0ec932019d3402cad8f93e97e90`, integración `d0514e89545dcc540e93541bd6859f34f41e5d307181b2bbc550fd67af3b95fd`. Se reprodujo e investigó la discrepancia con systematic-debugging. **43 archivos difieren únicamente por LF/CRLF**, con core.autocrlf=true. `source-provenance.json` verifica ambos mapas crudos contra sus archivos y compara bytes sustituyendo solo CRLF por LF:364/364 equivalentes,0 diferencias adicionales; ninguna fuente o reporte fue normalizado o reescrito. Su SHA256 es `c01dfa50ef13a274a17b7995faf65ced75c98e739638c65808da0b268732e64e`. No se presenta igualdad byte a byte entre checkouts; se conserva la identidad real de cada ejecución y la equivalencia de contenido Git.

El primer helper de coordinación usó `provenance-newlines.json` como resultado y como metadata de capture; esta última sobrescribió el resultado. La auditoría posterior falló con KeyError source_count, `scope-audit-execution.log`,exit1. El resultado inicial permanece solo en la salida de herramientas; no se reconstruyó fingiendo que fuera el original. Se conservaron copias de ambos scripts antes de corregirlos (`*-v1.py`), se separaron nombres y se ejecutó un nuevo readback `provenance-readback-v2`,exit0, que escribe `source-provenance.json`; auditoría `scope-audit-execution-v2`,exit0. Logs fallidos/corregidos y metadata se preservan. No afecta al resultado de tests ni modifica producto.

`scope-audit.json` comprueba checks/exit/log SHA, conteos, origen de fuentes posterior a tests, aprobación R7 y89 hashes, ancestros de integración, rama congelada y los tres documentos ajenos; SHA256 `7ef22e435afd321e3e9a119647bc06a9f227c03a0e47f279e05e4b03be920d24`. Se ejecutó antes del handoff final, por lo que deja ese último documento explícitamente pendiente de su readback Git posterior.

### Evidencia y límites finales

Manifiesto de coordinación `.cache/wave4-recovery-20261103/artifact-manifest-final.json`: **103 entradas**, verificadas sin discrepancias, SHA256 **`9100236ead1f7fba8531a4324888228168676a3a3227f72cb0371573c1bf0b4c`**. Excluye cachés mypy y el log vivo PostgreSQL `postgres-start.log`; incluye su snapshot inmutable `postgres-start-readback.log`. El servidor compartido se conserva activo. Los logs ignorados no estarán en un clon nuevo.

Este cierre acredita la recuperación, revisión, integración y validación **locales** solicitadas. **NOT RUN / fuera del cierre local:** publicación/push/PR/Actions/CI remoto, Docker/imagen/operaciones, remediación y reauditoría certifi, Polar sandbox pospuesto por el usuario, dispositivos físicos/lector de pantalla, EV001–012, LIVE/REPLAY/calidad o aceptación humana/deportiva y cierre de tickets. Los hallazgos críticos638 y esos gates siguen visibles para el siguiente trabajo autorizado. No se afirma preparación para producción. Handoff y auditoría final de alcance: [HANDOFF_WAVE4_RECOVERY_2026-11-03.md](../HANDOFF_WAVE4_RECOVERY_2026-11-03.md).
