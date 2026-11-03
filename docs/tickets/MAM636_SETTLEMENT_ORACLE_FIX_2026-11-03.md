# MAM-636 R6: settlement conocido — R7/R5-F01

## 1. Goal
Detectar gasto erosionado antes del primer snapshot y alteraciones tras idle en EV-017, con FAIL localizado y guard rechazado.

## 2. Context
Padre 8ac8fe30cf7478d6d8a9aba5e47d330000bbf426; dependencias636 incorporadas exclusivamente por cherry-pick: 7594a4f → 24f9daa, 4d59594 → f38dfd3, c1aaa93 → e84871b, ebf018f → ce1a371. R5 final REQUEST_CHANGES leído; un hallazgo material nuevo, sin ampliar alcance.

## 3. Constraints
Solo este checkout; sin agentes anidados, producción, integración, publicación o bases ajenas. Corpus17/expectativas34 y semántica de reportes intactos. EV001–012 NOT_RUN, humano/deporte PENDING, LIVE NOT_RUN. Ningún umbral deportivo nuevo.

## 4. Affected areas
mam636_harness.py, nueva prueba específica, constante DATABASE de mam636_runner.py y este recibo. Evidencia ignorada propia en .cache/mam636-fix6/.

## 5. Implementation steps
RED con mutación única de spent tras process_one real. Derivar costo de respuesta recibida y pricing congelado antes del worker; comparar ambos estados con ledger original, tokens, reserva e identidad. GREEN baseline y controles completos con reportes separados de creación exclusiva. Commit de código y después recibo con evidencia exacta.

## 6. Required skills
task-planning, safe-git-workflow, systematic-debugging, verify-before-complete; leídas antes de editar.

## 7. Validation
PostgreSQL18.4 127.0.0.1:55482, basis_wave0; solo basis_wave4_636_fix6/test_basis_wave4_636_fix6. Guard HTTPX sync/async, sockets/libpq/_nodb_cursor; settings de prueba y secretos sintéticos, AI0 salvo fixture. Focales nuevas/R1–R6, tipos core/Django, puras, arquitectura/imports, Ruff sin caché, check/migrations. Capturar argv, exits y hashes; conservar fallos y cachés inválidas.

## 8. Risks
Dos snapshots corruptos iguales no acreditan un cargo correcto. La función domain.usage_cost valida y cuantiza Decimal a ocho decimales con ROUND_CEILING; no duplicar tarifas ni inventarlas. Trials no forman parte del corpus ejecutado: si existe fondo capturado se verificará su coherencia, sin declarar fixture trial ejecutada.

## 9. Entrega inmutable y alcance real

Código propio **`a676e37a6f3ca2f05b5837d7c7f6e1567a5a457e`**, rama `t3/mam636-settlement-oracle-fix`. Este recibo se versiona después, sin editar esas fuentes. Solo tres archivos Python en el commit: harness, prueba nueva específica y una constante DATABASE. El candidato continúa **NO aprobado/NO integrado**; coordinación debe obtener revisión independiente R7. No se crearon agentes.

Dependencias exclusivas aplicadas sin reescritura desde el padre `8ac8fe30cf7478d6d8a9aba5e47d330000bbf426`:

| Original | Cherry-pick en este checkout |
| --- | --- |
| `7594a4f` | `24f9daace5c53a9da179be18b74897c8f5ea380a` |
| `4d5959491391245eccbce3505da336d828cc488e` | `f38dfd3add3c64ef1e281a18fcbcb382d8ca0142` |
| `c1aaa93987e34be96136f91ddc754811b501057a` | `e84871bb7fe4bbb5019b0472e19e689456b2bda0` |
| `ebf018f98562695e10f103bba9ba417f3214446b` | `ce1a37118f74f31bce43a6203a4e63b9276bf242` |

Leídos antes de implementar: instrucciones AGENTS suministradas y búsqueda de AGENTS aplicables sin archivos adicionales; arquitectura modular/hexagonal; última sección P2 de WAVE4; harness/report/runner y pruebas existentes; `coach/domain/jobs.py:usage_cost`, settlement en application/jobs.py, codec de pricing y decode_reply. Probes/logs y dictamen final R5 en `t3-19a75c82/.cache/mam636-review-r5` consultados solo como archivos. El dictamen confirma un nuevo hallazgo P2 **R5-N1**, denominado aquí **R7/R5-F01**; no se detectó otro hallazgo material que justificara ampliar esta implementación. Ninguna DB del revisor consultada.

## 10. Oráculo contable ejecutado

Antes del primer worker, `state()` conserva job/cuenta/request, IDs originales de UsagePeriod/TrialFund, reservation, kind, pricing_version/snapshot, contadores y filas completas de ledger. El transporte real simulado conserva la respuesta recibida y correlaciona el dispatch con el job ORM reclamado. El nuevo chequeo no filtra llamadas por contenido: exige exactamente una llamada y la identidad original.

La evidencia de `controlled_reply.usage` proporciona prompt/completion/cache-hit tokens; cache-hit ausente sigue el contrato existente de decode_reply (cero). Se exige tipo int exacto. El costo esperado se deriva mediante **usage_cost(TokenUsage, kind, reservation original, pricing congelado original)**: validación existente y Decimal/ROUND_CEILING, sin tarifas nuevas ni cálculo a partir del texto. El costo observado en esta fixture es `0.00001800`, con 20/10/0 tokens; se trata de un resultado del contrato ejecutado, no de una nueva tarifa pública.

Tanto `after` como `after_second_worker` se contrastan de forma independiente con ese origen: delta spent igual al costo calculado; delta reserved igual a la reserva del job; cost/tokens/modelo/status failed/answer vacío/attempt cerrado coherentes; IDs, pricing, reservation y contadores conservados. Las filas originales de UsagePeriod y, si se capturó un fondo, TrialFund deben cambiar únicamente spent/reserved por esos deltas. Se mantiene además la comparación previa entre workers y la cuenta de llamadas para detectar reintentos. Un dispatch/respuesta/pricing/uso ausente o inválido produce FAIL de evidencia o scenario_execution, nunca un PASS por omisión. No se modifican producción, corpus, expectativas ni semántica de `mam636_report.py`.

Se añadió un módulo de pruebas específico para mantener intactas las regresiones R1–R6. Cada mutante llama primero `process_one` real y hace una única escritura ORM, restaurando después todos los patches. No se atribuyen estas mutaciones al producto intacto.

## 11. RED → GREEN y matriz P2

**RED propio VERIFIED como reproducción del defecto:** `red.log`, exit1, una prueba en4.013s, falla por `PASS != FAIL`. `red/fix6-spent-erased-once.json` conserva la escritura única y el reporte completo: costo positivo, tokens20/10, reserva0 y spent0; after/after_second iguales. EV017 PASS, 74 observaciones PASS, 0 FAIL, 3 INCONCLUSIVE. SHA256 del reporte **`38502ac61354b311864fc6a9bf4ea3b047763c2563bdd6d14634ec4b00cc271a`**; log **`13adb07abf73a98dea45ad663c734d2dc324d272401f51e7962dc89f79b97f61`**. Las fuentes de esa ejecución están en red.command.json.

El test RED se detuvo antes de invocar el guard. Se realizó después un **readback del guard sobre las observaciones RED persistidas**, sin ejecutar workers ni alterar el reporte: `red_guard_readback.py`/`red-guard-readback.json`, exit0 de caracterización, `guard_rejected=false`. No es aceptación de corrección ni una nueva corrida del harness original. El código del guard sigue idéntico (`c6025346350d0f7381da0e9b1052944fcae81fa00d14a5b540560576a262831c`).

**GREEN inicial:** siete pruebas,3.603s,exit0, baseline sin FAIL y mutación única detectada. **GREEN estable:**21 pruebas,25.423s,exit0,sin omisiones, incluye las15 pruebas originales/R1–R6 y seis nuevas. Reportes de baseline y cada mutante separados con creación exclusiva.

Los siguientes archivos están bajo `.cache/mam636-fix6/stable-mutants/`. En cada mutante se mantienen17casos/34expectativas y EV017 termina FAIL; el guard conserva `guard_rejected=true` y su error real en el mismo JSON.

| Trigger único sobre worker real | Oráculo localizado que falla | Artefacto | FAIL observaciones total |
| --- | --- | --- | --- |
| spent=0 después del primer process_one, antes del primer snapshot | known_usage_after_spent_delta y fila original; también ambos contra el segundo worker | fix6-spent-erased-once.json |4 |
| cost=0 después del worker idle | known_usage_after_second_worker_job; comparación entre workers | fix6-idle-cost.json |2 |
| spent += Decimal0.000001 después de idle | delta de gasto y fila original del segundo worker; comparación entre workers | fix6-idle-ledger.json |3 |
| output_tokens=11 tras el primer worker, respuesta recibida conserva10 | known_usage_after_job y known_usage_after_second_worker_job | fix6-first-tokens.json |2 |
| añadir nuevamente job.cost al gasto tras el primer worker | delta y fila original frente al costo recibido, en ambos estados | fix6-first-double-charge.json |4 |
| Control positivo: gasto previo0.00010000, reserva adicional0.00000200, contadores2/1 antes del worker | Conserva el gasto previo, solo suma un costo, libera solo su reserva y conserva contadores | fix6-existing-ledger-baseline.json |0 |

El control positivo usa la misma fixture pagada; no amplía el corpus. El caso no depende de que spent_before sea cero ni de que deba desaparecer toda la reserva del período. Los cinco negativos se ejecutan completos; no se promueven a PASS los casos no alcanzados.

R1–R6 conservados por las pruebas originales: payload HTTP realmente despachado con identidad/cuenta; snapshots posteriores al segundo worker; ciclos en historia; precondición de ejecución/respuesta A; estados runtime cerrados y excepción del escenario; comparación JSON con tipos exactos incluidos anidados. Sus artefactos están en stable-mutants/full-*.json, guard-EV-*.json y controles runtime/typed. La revisión R5 había ejercido además controles independientes propios; esos resultados pertenecen al revisor y no se presentan como ejecuciones nuevas de esta entrega.

## 12. Baseline y trazabilidad

`stable-baseline.json`: SHA256 **`6d2dc667e9f3bee8891b42191d6a0d893844912563b953d0c78f28fbb9c81294`**. **5/17** casos ejecutados,3 casos con todas sus expectativas técnicas PASS; **7/34** expectativas PASS,3 INCONCLUSIVE,24 NOT_RUN,0 FAIL. Observaciones: **89 PASS,0 FAIL,3 INCONCLUSIVE**. Se sustituyen dos chequeos débiles por17 chequeos contables; los denominadores y expectativas se conservan. EV001–012 NOT_RUN,EV013/014 INCONCLUSIVE,EV015–017 PASS técnico. **0 casos aceptados deportivamente**. `stable-baseline.negative-leak.json` es un control aparte, no el baseline.

Corpus SHA256 intacto **`cefef9c79c093850e31ca570c9bf2706d639ba45c90fc855c01e56975a233d8e`**. Identidad de `basis/**/*.py` ejecutado estable: **`d51e897694bd7ae9d2563c66c3ec87f88cccb0ec932019d3402cad8f93e97e90`**. Los reportes se ejecutaron antes del commit y registran honestamente HEAD `ce1a37118f74f31bce43a6203a4e63b9276bf242`, junto a los hashes reales de las fuentes modificadas. **No se reescribió candidate_sha**. `code-integrity.json` prueba que esas fuentes y las de los once checks estables coinciden con las fijadas en a676e37; Git diff HEAD sobre basis está vacío.

| Archivo propio | SHA256 de bytes ejecutados |
| --- | --- |
| mam636_harness.py | `506f63c991b98b549d6ee6dfb254b53ce6412c15a89c89a2b189c62d9e316714` |
| mam636_runner.py | `c00b37f517a316920bca14a6d12fb660322ca398f7401c7e8b94c848ae00101d` |
| test_mam636_settlement_oracle.py | `57d67988da2a8ca508af9108b67794859fa779315be237575608737544a2fd0e` |

Manifiesto propio de112 artefactos (logs, argv/exit, scripts, reportes y hashes; excluye cachés mypy y el propio manifiesto): `.cache/mam636-fix6/artifact-manifest.json`, SHA256 **`0686eb811f72b7b751f8b1b34652aac940e000f60750fdeb063b02e74559c7da`**. `evidence-summary.json`: **`e88d3cbb26272f49afeb08d9dccd91af0adc262708688c88108502226faec703`**. `code-integrity.json`: **`7e2e85bf97a70ae148c57f53a337ebb3befeb3452eea28b4dcb11b836d8fc3aa`**. Todo se preserva local e ignorado; ningún cache se incluye en Git.

## 13. Comandos y checks pertinentes

Desde este checkout, `$py='C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'`, `$r='basis.bootstrap.tests.mam636_runner'`, `$e='.cache/mam636-fix6'`, `$c="$e/capture.py"`. Cada comando capturado usa `& $py -X utf8 -B $c <nombre> $py -X utf8 -B <argumentos>`. Cada `<nombre>.command.json` conserva argv real/cwd/instante/exit/duración/hash del log, corpus, mapa de fuentes y overrides pertinentes.

```powershell
$env:MAM636_FIX_EVIDENCE="$e/stable-mutants"
$env:MAM636_REPORT="$e/stable-baseline.json"
$env:MAM636_ATTEMPT='fix6-stable'
& $py -X utf8 -B $c focal-stable $py -X utf8 -B -m $r manage test basis.bootstrap.tests.test_mam636_evaluation basis.bootstrap.tests.test_mam636_review_fixes basis.bootstrap.tests.test_mam636_settlement_oracle --noinput -v 2
```

Los demás procesos no usan esas variables MAM636. Tipos/puras usan directorios nuevos distintos MYPY_CACHE_DIR (`mypy-core-stable`, `mypy-django-02`, `mypy-pure-stable` bajo $e). Imports usa PYTHONPATH absoluto a $e y check_imports.py llama al CLI oficial dentro de las guardas del runner. Ruff y formato usan --no-cache. No se borró ni reparó ninguna caché inválida; no se encontró una nueva en este checkout.

| Estado | Log; argumentos tras Python | Resultado | SHA256 log |
| --- | --- | --- | --- |
| VERIFIED | guards.log; -m $r verify-guards | HTTP sync/async, connect/connect_ex, libpq exclusivo;PG18.4;exit0 | `2247da7e91d503a5d395abdc5e2f38d6354f15adcff26e3aefa6d67e00c52d26` |
| VERIFIED | focal-stable.log; comando anterior |21/21;25.423s;exit0 | `88f2ffc604e89812417099a1481486fff8ef09c24ca5a6e37433539a1e3eebaf` |
| VERIFIED | worker-regressions.log; -m $r manage test y nueve módulos indicados abajo |127/127;82.577s;exit0 | `a26242690f421258f41e6ffd01d63a4d6a181a44ab3be014dc0b13435771e9e2` |
| VERIFIED | mypy-core-stable.log; -m $r mypy --config-file mypy-core.ini |135 fuentes;exit0 | `4655baa132d62306c2599cdaba3a28c92702eed4d94418fabd2f14a499caa500` |
| VERIFIED | mypy-django-02.log; -m $r mypy --config-file mypy-django.ini |441 fuentes;exit0 | `e008f1fbfd5679a15d646b2d9fce4c2c57d9b842e7799b8b2129586c06450705` |
| VERIFIED | pure-stable.log; -m unittest discover -s tests_architecture |285/285;14.055s;exit0 | `f4ac56e631b3402d0b9d890c39807971440aa2a63fc718cf663d3f725ee74ebe` |
| VERIFIED | architecture-stable.log; scripts/architecture_check.py |fronteras/legado;exit0 | `94560b348ce438daa452f8bb2313693d8edcd7c8a464be13271136ec91b6d26f` |
| VERIFIED | imports-stable.log; -m $r check_imports --no-cache |8 kept/0 broken;exit0 | `b28c642589a45d544caae79e3ac8cf5843ee9dba47008bd53cb1a576bb61c558` |
| VERIFIED | ruff-stable.log; -m ruff check --no-cache y tres Python propios |exit0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| VERIFIED | format-stable.log; -m ruff format --check --no-cache y tres Python propios |3 formateados;exit0 | `eee76f865de5a9f2456950f710ae5d5f9b5bd0ea02aa54f614c5eed6642a0bfd` |
| VERIFIED | django-check-stable.log; -m $r manage check |sin incidencias;exit0 | `f87ceb15410bde28ff826ce26228e0576558258fa64d145847921a593a61ee63` |
| VERIFIED | migrations-stable.log; -m $r manage makemigrations --check --dry-run |sin cambios;exit0 | `93e6e2d5be3c054add80c0f19101608803f7ca8a7df1fa41f76bbb9a1f570f4a` |

Los nueve módulos de worker-regressions son `basis.bootstrap.tests.test_coach_edges`, `test_coach_provider_policy`, `test_coach_reconciliation`, `test_coach_attempt_fence`, `test_mam634_proposals`, `test_mam635_acceptance`, `test_coach_fixture_calendar`, `test_coach_jobs` (todos bajo basis.bootstrap.tests) y `tests.regression.test_coach_context_633`; flags --noinput -v1. Sin reloj global: FROZEN_NOW se parchea solo dentro de las fixtures del harness. Se migró desde cero la test DB propia durante las focales; ningún cambio de migraciones generado.

## 14. Intentos conservados y pendientes

**FAILED esperado:** red.log descrito arriba. **FAILED corregido:** mypy-django-01.log,exit1,nueve errores de tipado nuevos en dos archivos; SHA256 `003e9b1479875b9a0966f66f3f67d40eaf50eb45fd7e954c39bcaf9d8e1eec0f`. Se corrigieron anotaciones/listas, estrechamiento de JobKind y alias explícito de process_one, sin alterar el producto. El reintento de441fuentes y la focal estable pasan. Los primeros GREEN/checks también se conservan con su identidad previa; no se sustituyen por los resultados estables.

Tras RED, la destrucción de test DB tardó en retornar. diagnose-own-db.log consultó exclusivamente actividad de las dos bases propias y no mostró bloqueadores/conexiones pendientes; el proceso terminó exit1 esperado en132.537s totales. No se determinó causa de la demora; no se cancelaron conexiones, bases ni PostgreSQL. El dato no se interpreta como fallo del producto ni de su settlement.

Operación local: config.test_settings, claves sintéticas, AI0 salvo overrides acotados, MockTransport. Runner preserva guardas HTTPX sync/async, sockets/libpq y _nodb_cursor propio. Creación inicial únicamente de basis_wave4_636_fix6 si faltaba; Django creó/destruyó solo test_basis_wave4_636_fix6. Sin .env, proveedor IA/Polar/pagos/red externa, root u otras DB. Las guardas Python no son un firewall del SO.

**VERIFIED:** diff/check y fuentes limpias contra el commit de código, hashes de logs/reportes, rama congelada633/634 en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`, ownership limitado. No cambios a jobs/precios/contextos/prompts/offline/635/calendario. El recibo es el único cambio posterior al commit de código.

**NOT RUN por este ejecutor:** suite global raíz/integrada (coordinación comunicó1074casos/10omisiones sin errores; no se atribuye a este checkout), nueva revisión independiente R7, integración al padre, fixture trial financiado, nuevos órdenes/concurrencia/carga/capacidad, navegador/dispositivos, aceptación/calidad deportiva, revisión humana/rúbrica/oráculos deportivos, EV001–012, LIVE/REPLAY/proveedor real, conciliación administrativa real, Docker/build/frontend, CI/push/PR/Actions, pagos/Polar/producción y mutaciones/cierre Linear. **Human/sport PENDING, LIVE/final acceptance NOT_RUN.** Frontend/djLint: NOT APPLICABLE al diff Python. MAM-636 continúa candidato local pendiente de revisión; esta entrega no se autoaprueba.
