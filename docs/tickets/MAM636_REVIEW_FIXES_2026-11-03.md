# MAM-636 — correcciones de revisión R1–R6

## 1. Goal

Reparar los seis falsos PASS del evaluador SIMULATED y demostrar detección RED→GREEN con mutaciones completas, sin conceder aceptación deportiva ni integrar al padre.

## 2. Context

Checkout propio `t3-19a75c82`, inicialmente limpio en `0da0dedb192981cd4c80335900d8c1b5e289b9f3`. Dependencias no aprobadas incorporadas exclusivamente por cherry-pick: `df5550d` → `7594a4f`, `eb0ec6c` → `4d59594`. No se reescribieron los originales. Leídos instrucciones, arquitectura, Wave4, plan636 completo, corpus17, candidato, recibo y revisión/probes/manifest de R2 (solo lectura). No AGENTS.md adicional encontrado en checkout/padres.

## 3. Constraints

Solo harness/report/runner y pruebas/recibo propios. Sin producción, calendario, offline, pruebas635, agentes anidados, integración, CI, push, PR, Linear ni LIVE. Conservar corpus, expectativas e intentos fallidos. Bases exclusivas `basis_wave4_636_fix3`/`test_basis_wave4_636_fix3`; PostgreSQL compartido18.4 sin detenerlo. No usar DB de autor/revisor/coordinación. `f42b861` intacto.

## 4. Affected areas

`mam636_harness.py`: correlación del HTTP recibido con job/cuenta, precondición de respuesta, estado posterior al worker y ciclos en historia. `mam636_report.py`: validación runtime cerrada e igualdad estructural sensible a tipos. `mam636_runner.py`: constantes DB exclusivas. Pruebas nuevas de regresión y evidencia local en `.cache/mam636-fix3/`.

## 5. Implementation steps

1. Runner exclusivo, baseline sin corrección y regresiones que exigen detección (RED).
2. Reparar R1–R6; repetir baseline y mutantes completos separados, con guard rechazando FAIL y artefactos localizados (GREEN).
3. Focales normales sin reloj global, puras/arquitectura/imports/tipos/Ruff/Django/migraciones; registrar límites y fallos.
4. Commits nuevos propios, árbol limpio y entrega a coordinación para nueva revisión independiente antes de integración.

## 6. Required skills

`safe-git-workflow`, `task-planning`, `systematic-debugging`, `verify-before-complete`.

## 7. Validation

Python raíz `.venv-win`, secretos ficticios, AI0 salvo fixtures, MockTransport y guardas HTTP/sockets/libpq/cursor administrativo. Reutilizar patrones de probes de revisión con aserciones invertidas que exigen detección. Tres mutaciones completas: fuga en request, liberación al quedar idle y corrupción de ciclos. Además ausencia de respuesta, estados/dimensiones/índices inválidos, booleanos/números anidados y RuntimeError retenido. Reportes exclusivos, nunca sobrescritos.

## 8. Risks

Estas mutaciones prueban el evaluador, no defectos del producto sin mutar. Ningún nuevo oráculo/tolerancia/umbral deportivo. EV001–012 NOT_RUN, revisión humana PENDING y LIVE NOT_RUN siguen vigentes. Guardas Python no equivalen a firewall del sistema. Nueva revisión independiente corresponde a coordinación, sin agentes anidados aquí.

## 9. Recuperación R4 y código entregado

Código recuperado y versionado en **`c1aaa93987e34be96136f91ddc754811b501057a`**, sobre `4d5959491391245eccbce3505da336d828cc488e`, rama `t3/mam636-review-fixes`. Este recibo se entrega mediante un commit posterior. Exclusivamente cuatro Python propios; no cambia código de producción ni las dependencias cherry-picked. Las secciones1–8 conservan el plan anterior; esta sección registra el resultado real de recuperación.

Antes de editar/versionar se inventariaron estado, diff y SHA256 en `.cache/mam636-fix3/recovery-r4/initial.json` y `initial.diff`. Diff inicial SHA256 `89bffc3b1955a2c4344ac0c808e271a4d6e2114462e25b405dd1c1323af2f396`. No fue necesario corregir nuevamente el Python recuperado: sus bytes son idénticos a los del inventario inicial y a los `source_hashes` del reporte de105 pruebas. Sí se completó este recibo y se repitieron controles cuya evidencia no era utilizable.

Leídos el plan y readback del padre (`WAVE4_PLAN_2026-11-03.md`, recuperación `8f64263`, readback `b7ed34e`), arquitectura, contrato/corpus636 y revisión R2/probes de solo lectura. El readback del padre registra R3 **cancelled**, `workState=result_available`, `hasPendingChildRuns=false`, sin preguntas. La consulta directa desde este hijo, tanto con nombre corto como con taskId completo, respondió `task_not_found`: la tarea pertenece al hilo padre. Por tanto, ese estado se atribuye al readback del padre, **no a una verificación live de este hijo**. No se usó `thread_send`, no se reanudó R3 ni se crearon agentes/checkouts.

SHA256 de las fuentes de la entrega:

| Archivo bajo `basis/bootstrap/tests/` | SHA256 de bytes locales verificados |
| --- | --- |
| `mam636_harness.py` | `ee7ed4133751d784c3467de9433ecf95cd42f6f3a50fb4706e28caff3c9165ea` |
| `mam636_report.py` | `c6025346350d0f7381da0e9b1052944fcae81fa00d14a5b540560576a262831c` |
| `mam636_runner.py` | `bdc3ecad9cbc2e7a4588850e8d20afc722cb3d06549b18d1c11fefb723aa2fca` |
| `test_mam636_review_fixes.py` | `73fee7436708812f959a375465347224d3a8aaf8674a26c0d389d6e3095f4af9` |

Git normaliza finales de línea al almacenar blobs; estos hashes corresponden a los bytes con los que se ejecutaron las pruebas. Identidad agregada de fuentes `basis/**/*.py` en ambos reportes posteriores: `3249a4983bfecf2615b70299b575430d843278fe3b4daa0eac641793134d87d8`. El `candidate_sha` de los reportes anteriores al commit sigue siendo `4d59594`; la identidad del WIP se acredita por los hashes, sin reescribir reportes para atribuirles el commit nuevo.

## 10. Matriz de respuesta R1–R6

Todos los tests siguientes están en `test_mam636_review_fixes.py`; la focal nueva ejecuta además los seis tests originales. El comando común C1 y su log se detallan en la sección12. Los guards se ejecutan dentro de los tests, exigen excepción y guardan `guard_rejected=true` junto al listado localizado de contradicciones.

| Revisión | Respuesta implementada | Regresión y evidencia nueva bajo `recovery-r4/mutants/` | Baseline frente a mutación |
| --- | --- | --- | --- |
| R1 P1 | Captura en el receptor MockTransport del body efectivo, job/cuenta/attempt/request-key reales. Comprueba identidad, roles/modelo y user-payload contra el jobA congelado; conserva también el contexto persistido. | `test_full_request_only_leak_fails_and_rejects_guard`; `full-request-leak.json`; `guard-EV-014-dispatched_payload_excludes_B.json`. C1. | Baseline EV-014 INCONCLUSIVE por límites de calidad. Mutación solo del request deja contexto/respuesta persistidos sin PRIVATE_B, pero EV-014 pasa a FAIL en `dispatched_payload_excludes_B` y `A_dispatched_user_payload`;2 observaciones FAIL y guard rechazado. |
| R2 P1 | `state()` relee ORM e incluye UsagePeriod completo y TrialFund vinculado. EV-016/017 comparan después del segundo worker, además de estado/reserva/costo/gasto; no se inventa conciliación ni costo conocido. | `test_full_idle_worker_release_fails_both_cases_and_rejects_guard`; `full-idle-release.json`; guards EV-016 y EV-017 para `invalid_json`/`missing_usage`. C1. | Baseline EV-016/017 PASS técnico. Worker idle mutado cambia uncertain→failed, costo0/reserva0 sin HTTP: ambos casos FAIL,12 observaciones FAIL y guard rechazado. El fixture usa cuentas pagadas; `trial_fund=[]` refleja ausencia real, no ensayo de un fondo trial financiado. |
| R3 P2 | `history()` incorpora filas completas de Cycle, con orden estable, en cada snapshot de conservación histórica. | `test_full_cycle_corruption_fails_and_rejects_guard`; `full-cycle-corruption.json` conserva escrituras y reporte; `guard-EV-015-invalid_preserves_all_history.json`. C1. | Baseline EV-015 PASS técnico. Tras rechazar propuesta inválida se mutan títulos de ciclos: EV-015 FAIL en conservación histórica;3 observaciones FAIL, guard rechazado. |
| R4 P2 | Precondición explícita de una llamada A correlacionada, respuesta controlada y job succeeded. Se compara respuesta recibida/persistida antes de comprobar exclusión. Ausencia produce precondición FAIL y salida INCONCLUSIVE. | `test_full_no_a_dispatch_does_not_credit_b_response`; `full-no-a-response.json`; `guard-EV-014-A_dispatch_count.json`. C1. | JobA queda pending con answer vacío; respuesta de B no acredita A. EV-014 FAIL por count/identity/succeeded; `controlled_response_excludes_B=INCONCLUSIVE`, nunca PASS sobre vacío. |
| R5 P2 | Conjunto runtime cerrado de estados/dimensiones e índice int exacto. `observe`, agregación, export, coverage y guard validan incluso observaciones insertadas directamente. | `test_invalid_status_is_rejected_at_entry_and_aggregation`, `test_invalid_dimension_and_expectation_are_rejected`, `test_direct_observations_are_validated_by_export_coverage_and_guard`; `runtime-invalid-status.json`. C1. | None/BROKEN/vacío/0/bool/list/dict rechazados con ValueError; FAIL no oculta un status desconocido. Entrada fallida no se añade y conserva denominador1 del caso sintético. Ningún desconocido llega a PASS. |
| R6 P2 | Comparación estructural recursiva por tipo exacto, incluidas claves, listas y tuplas. No hay equivalencia numérica entre tipos autorizada en este contrato; tampoco tolerancias nuevas. | `test_boolean_numeric_mismatches_including_nested_values_fail`; `typed-structure-mismatches.json`. C1. | Siete pares incompatibles, incluidos bool/número anidados y1/1.0, producen FAIL y guard rechazado; controles de mismo tipo conservan PASS. |

Control adicional `test_full_runtime_error_remains_failure_with_other_cases_retained`: RuntimeError se conserva como EV-013/`scenario_execution=FAIL`, con mensaje `fix3-sentinel` en artefactos; los otros casos siguen presentes. `full-runtime-error.json` y guard propio. No se silencian excepciones.

Las mutaciones R1/R2/R3 anteriores a la reparación conservaron7 expectativas PASS y0 observaciones FAIL, demostrando los puntos ciegos. R4 exige una distinción: en el recorrido completo anterior EV-014 publicaba el falso PASS de salida, pero había16 FAIL posteriores porque A pendiente contaminaba el orden de jobs. El recorrido corregido conserva esos efectos y alcanza20 FAIL en total, tres de ellos localizados en las precondiciones de A. No se afirma aislamiento entre casos ni que los20 sean defectos independientes del producto.

Identidad de artefactos nuevos (reportes anteriores `red/`, `green-01/` y `final/` se preservan por separado):

| Artefacto bajo `recovery-r4/mutants/` | SHA256 |
| --- | --- |
| `full-request-leak.json` | `8e3bdd914a15e3a1c72cf75da77279ebb5f33575ca6772783ea5e6ac5d871e9a` |
| `full-idle-release.json` | `eed1af463deb0e973938625381a12ec68be6795c6d8de9294fbdf4caaaaf7247` |
| `full-cycle-corruption.json` | `0b1faea37242a936607a1d37f5c50165931647f7958f74d912133811a37a7fc9` |
| `full-no-a-response.json` | `78d6452b08f517413689727750e50ac7237553ccd31a3aed3fdae852715f60dd` |
| `runtime-invalid-status.json` | `5f71b617d60cffeac03ba1e8b9a88e2d206685ddfbddacf0608ebfdc087503aa` |
| `typed-structure-mismatches.json` | `a459b7a534cdf1ca7ec7c5eefedc09c08069906500aacdb601b819f247b74a44` |
| `full-runtime-error.json` | `b38e54903f540c7b9f1b24dd07de65c54c5552477e1e33221e378b681d1fc023` |

## 11. Resultados recuperados y baseline nuevo

**Evidencia R3 recuperada, no ejecución nueva:** `regressions-red.log`:9 pruebas,28 failures y2 errors, salida1, SHA256 `d5f0b817d4e1140398d6ab026593a0b4f42dbfca4ee7bb565344239d6bdef6f5`. Esta es la fase RED contra el evaluador sin reparar. `regressions-green-01.log`:15 pruebas aprobadas en15.179s, salida0, SHA256 `f661b11404c24ba20a7be33a9485f0ecc47c3b08bb3fba9234df5efe1691094e`. `focal-final.log`:105 aprobadas en33.899s, salida0, SHA256 **`2491f2ad760c91efdc451686c7bc692799e6a475d0e26dd931002b57352ae356`**. Las metadata válidas coinciden con sus logs. Esta focal no se repitió al estar las fuentes idénticas; no se hereda como una ejecución nueva.

`before-baseline.json` (sin reparar) SHA256 `f4109d0ce653f7e56a2d8b2a87b6642d571b111c39e3214030a6b213038fa64a`; `final-baseline.json` recuperado SHA256 `ae339a9411b6ce79db17db542dce0347cccf2a8be01f67d81b9bc228fa956a4a`. Expectativas sin cambios:7 PASS,3 INCONCLUSIVE,24 NOT_RUN,0 FAIL sobre34. Las observaciones pasan de59 a74 PASS al añadir guardas; esto no representa progreso deportivo ni aumento de expectativas aprobadas.

**Ejecución nueva R4 C1:**15 pruebas aprobadas, cero omisiones,9.091s, salida0. Baseline `recovery-r4/baseline.json` SHA256 **`56831e27dc4e81515efb027f975a777841e6386fd92603d510541a54689bf3ca`**.5/17 casos ejecutados;3/17 con todas sus expectativas técnicas PASS;7/34 expectativas PASS,3 INCONCLUSIVE,24 NOT_RUN,0 FAIL.74 observaciones PASS,3 INCONCLUSIVE,0 FAIL. Casos EV-001–012 NOT_RUN; EV-013/014 INCONCLUSIVE; EV-015–017 PASS técnico en este modo. Casos aceptados deportivamente: **0**.

Dimensiones del baseline: numeric17 NOT_RUN; sport17 NOT_RUN; structure3 PASS/14 NOT_RUN; operation3 PASS/2 INCONCLUSIVE/12 NOT_RUN. `sport_review=PENDING`, rúbrica `PROPOSED_NOT_APPROVED`, aceptación final/LIVE **NOT_RUN**. No se ejecutó modelo IA ni se midieron tokens/costo/latencia LIVE. El texto controlado solo prueba la ruta de transporte/servicios.

Corpus17 intacto: `docs/fixtures/coach_evaluation_v1.json`, SHA256 **`cefef9c79c093850e31ca570c9bf2706d639ba45c90fc855c01e56975a233d8e`**. El reloj fijo2027-01-04 se limita al contexto de ejecución de fixtures del harness; las demás focales recuperadas no usan reloj global. UUIDs/secuencias/duraciones quedan registrados, sin prometer igualdad byte a byte entre corridas.

## 12. Comandos, controles y hashes de logs nuevos

Desde este checkout. `$py` es `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`; `$r = 'basis.bootstrap.tests.mam636_runner'`; `$e = '.cache/mam636-fix3/recovery-r4'`; `$c = "$e/capture.py"`. Cada ejecución usa `& $py -X utf8 -B $c <nombre> $py -X utf8 -B <argumentos>`; metadata `*.command.json` conserva argv, cwd, salida, instante y SHA del log. `code-integrity.json` conserva los overrides de caché/PYTHONPATH de cada comando.

C1 (focal y mutantes nuevos):

```powershell
$env:MAM636_REPORT = "$e/baseline.json"
$env:MAM636_ATTEMPT = 'recovery-r4-final'
$env:MAM636_FIX_EVIDENCE = "$e/mutants"
& $py -X utf8 -B $c focal-15-retry $py -X utf8 -B -m $r manage test basis.bootstrap.tests.test_mam636_evaluation basis.bootstrap.tests.test_mam636_review_fixes --noinput -v 2
```

Los archivos de evidencia se abren con creación exclusiva: para repetir usar nombres/destinos nuevos. Los restantes controles se ejecutaron sin las variables MAM636 de C1. En tipos/puras se fijó `MYPY_CACHE_DIR` a un subdirectorio nuevo distinto para cada comando (`$e/mypy-core`, `$e/mypy-django`, `$e/mypy-pure`); no se borró la caché anterior. Para imports/import del runner se fijó `PYTHONPATH` al directorio absoluto `$e`; `check_imports_r4.py` llama al CLI oficial y `import_r4.py` comprueba ausencia de cambios de environment/cwd/settings o conexiones al importar.

| Estado nuevo | Nombre de log bajo `recovery-r4/`; argumentos tras Python | Resultado | SHA256 log |
| --- | --- | --- | --- |
| VERIFIED | `focal-15-retry.log`; C1 |15/15;9.091s;exit0 | `9d27c3ed3c14e9aed286f8bf00624c0db0583333437f33ec7841871c135e73d6` |
| VERIFIED | `guards-retry.log`; `-m $r verify-guards` | HTTP sync/async, sockets, DB exclusiva;PG18.4;exit0 | `2247da7e91d503a5d395abdc5e2f38d6354f15adcff26e3aefa6d67e00c52d26` |
| VERIFIED | `mypy-core-fresh-cache.log`; `-m $r mypy --config-file mypy-core.ini` |133 fuentes;exit0 | `dd40ac776a2289d0356c8a11c4c080fe3ab9f4666ab8e85452808e1389bc892b` |
| VERIFIED | `mypy-django-fresh-cache.log`; `-m $r mypy --config-file mypy-django.ini` |439 fuentes;exit0 | `03ff6a43956102c8d169428b8eaae07822b9079d5a7bed87019efff2edcf2a6b` |
| VERIFIED | `pure-fresh-cache.log`; `-m unittest discover -s tests_architecture` |278/278;5.744s;exit0 | `dd0c596ee09b021c06516a106551470e741f52313070c0f977f1e5d5b90c809d` |
| VERIFIED | `architecture.log`; `scripts/architecture_check.py` | fronteras y legado;exit0 | `94560b348ce438daa452f8bb2313693d8edcd7c8a464be13271136ec91b6d26f` |
| VERIFIED | `imports.log`; `-m $r check_imports_r4 --no-cache` |8 contratos kept/0 broken;exit0 | `fbc8b2db794b5c81cf167a15cffdb9f9f55a03f50d48276823ad450fa031613d` |
| VERIFIED | `ruff-no-cache.log`; `-m ruff check --no-cache` y los cuatro Python entregados |exit0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| VERIFIED | `format-no-cache.log`; `-m ruff format --check --no-cache` y los cuatro Python |4 ya formateados;exit0 | `177f260a5645724013185e4b140c7045cc39e56c0c97b120f5cb23599f85f0de` |
| VERIFIED | `django-check.log`; `-m $r manage check` |sin incidencias;exit0 | `f87ceb15410bde28ff826ce26228e0576558258fa64d145847921a593a61ee63` |
| VERIFIED | `migrations.log`; `-m $r manage makemigrations --check --dry-run` |sin cambios;exit0 | `93e6e2d5be3c054add80c0f19101608803f7ca8a7df1fa41f76bbb9a1f570f4a` |
| VERIFIED | `runner-import.log`; `-m import_r4` |import sin efectos;exit0 | `b440c5e9566166703367c2af5fb33ad09375e65ee1502c62d77fd480ab3bc12a` |

`git diff --check` y diff staged satisfactorios antes de los commits. Las migraciones se aplicaron desde cero a la test DB propia durante C1. Runner con `config.test_settings`, clave sintética, AI0 salvo override de fixture, .env no leído y HTTP MockTransport; guardas de HTTP sync/async/socket/libpq y cursor administrativo. Solo `basis_wave4_636_fix3`/`test_basis_wave4_636_fix3`; no se detuvo ni reinició PostgreSQL. Puras/arquitectura/Ruff no necesitan Django ni DB. Las guardas Python no son un firewall del SO ni se heredan a procesos externos arbitrarios.

## 13. Fallos conservados, integridad y pendientes

La auditoría `recovered-audit.json` detectó metadata antigua de arquitectura/imports/puras/Ruff/formato/import del runner con contenido NUL completo (y varios logs/helpers del mismo grupo también afectados). Se preservaron sin reconstruirlos ni atribuirles éxito. El origen de esos bytes **no se determinó**; no se atribuye a la cancelación. Por eso se repitieron esos checks. Los logs válidos RED/GREEN/focal105 y mypy sí se contrastaron con sus SHA registrados.

Intentos nuevos fallidos preservados:

| Log bajo `recovery-r4/` | Resultado real antes del reintento | SHA256 |
| --- | --- | --- |
| `guards.log` |exit1;PG `FATAL: the database system is starting up` | `a30fcdfa53e6e3968ee5f1d959f287bcc706d7718f3263c94ea59aa69f6ab7d8` |
| `focal-15.log` |exit1;misma indisponibilidad antes de ejecutar tests;no reporte fabricado | `55aa5e3f15b05527a06537a5d2eafd4cc2709b8d80b251551217be9315e3c8ef` |
| `ruff.log` |exit2;panic `wrong package cache for file`, package root NUL | `b4eeea170736a1c251d7d2634c5875a4cfbb6e004cc6f55025515c7dab2406b6` |
| `format.log` |exit2;misma caché inválida;resuelto usando `--no-cache`, sin cambios de código | `5f2ccb66686404e77e07de2028ee647d4ab8d96be47350751c9e5bf68f75e374` |
| `pure.log` |278 tests,1 failure por `@plugins_snapshot.json: Error reading JSON file`;reintento solo cambia caché de mypy | `03c192bf026a66003857b9bdfc936ace617be44d9eac15b574026e9265c37203` |

También se conserva `mypy-django-01.log` de R3:4 errores de tipado en la regresión, corregidos antes del WIP recuperado; SHA256 `9d8e1fee2823c47f1381819b5673c6822f4a15da7983313c02c38f5b77314efb`. Su reintento previo y el nuevo control R4 pasan; no se borra el fallo.

Manifiesto de135 artefactos de evidencia/scripts/logs recuperados y nuevos (incluye bytes inválidos, excluye cachés de mypy y el propio manifiesto): `.cache/mam636-fix3/recovery-r4/artifact-manifest.json`, SHA256 **`abec2c95a91ea7d946c5c29ba0bbab1fa5cb6c3618280db7015037baf50543ac`**. `evidence-summary.json`, SHA256 `2f199ba817f3cee24d316030f1994bc9877e5c8b4520eac8e9e0a0d761b94b26`, conserva conteos/status/fallos por reporte y hashes de guards; `code-integrity.json` vincula las fuentes al commit de código. Estos artefactos ignorados permanecen locales para revisión, sin stage.

**NOT RUN:** suite global integrada (la ejecutará coordinación sobre fuentes estables), nueva revisión independiente, integración al padre, CI remoto, publicación/push/PR/Actions, LIVE/REPLAY/proveedor real, revisión humana y calidad deportiva, aprobación de rúbrica, oráculos deportivos, navegador/dispositivos, carga/concurrencia/capacidad, conciliación administrativa real, pagos/Polar y cierre de MAM-636. **NOT APPLICABLE a este diff:** compilación de frontend/djLint; no cambian assets/templates. No se modificaron recorder, contextos, prompts, propuestas, offline, pruebas635 ni fixture calendario.

Rama congelada633/634 releída en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`. Solo se versionan los cuatro Python y este recibo. `.import_linter_cache/` sigue untracked, preservada sin borrar ni stage. La entrega local termina implementación/reporte R1–R6; la aprobación independiente y la integración corresponden a coordinación y no se declaran realizadas.
