# MAM-623 / BASIS-009 — prescripción, ejecución y series

## Contrato

Una sesión ejecutada tiene UUID propio; dos sesiones el mismo día son registros distintos. El original programado y sus bloques/series siguen siendo intención. Un resultado4×75kg no cambia5×80kg prescritos. No se modifica WorkoutData legado ni se descompone su agregado en series ficticias.

`start` y la creación vinculada por sync inicializan desde la misma prescripción canónica, bajo las guardas622. Sync comprueba los targets enviados contra esa fuente y superpone resultados; no convierte targets arbitrarios del cliente en prescripción. Un vínculo existente, incluso la condición de sesión no vinculada, no se reasigna después de crear la ejecución.

Se conserva [el contrato622](PLANNING_VERIFICATION.md): identidad `origin_id or pk`, fuentes/versiones protegidas, elegibilidad de inicio, continuidad por UUID histórico, cuentaAUTH real → ancla → prescripción → ejecución en el mismo alias y hasta COMMIT exterior. Los endpoints siguen usando default y los helpers/UoW conservan propagación de alias y reserva SQLite. No se añade unicidad global por prescripción: las filas históricas y sesiones manuales repetidas siguen representables. Reintentar start vigente reutiliza la activa; una intención cerrada no se reinicia automáticamente (regla622). Una repetición manual es otra ejecución propia, no una mutación del resultado cerrado.

## Identidad y compatibilidad de payloads

- Block, StrengthSet e Interval de ejecución conservan sus PK en cada edición, incluso al editar solo título/notas/duración. Los snapshots publican `id` y `source` por bloque/fila; source es FKPROTECT al original, asignada por el servidor al iniciar.
- IDs enteros se validan exclusivamente contra el padre de la ejecución actual. IDs desconocidos, repetidos, de otro bloque o de otra cuenta se rechazan con error genérico, sin consultas de datos ajenos ni enumeración. Tampoco se permite sustituir source.
- Clientes anteriores sin IDs de fila pueden guardar el mismo snapshot completo, a la revisión esperada y en el mismo orden. El servidor resuelve posiciones conservadas, vuelve a comprobar la intención y mantiene los IDs reales. IDs temporales de bloque de tipo texto siguen siendo etiquetas locales sin autoridad, como en el protocolo anterior.
- Filas nuevas omiten ID/source. Crear otra UUID no autoriza reutilizar IDs de una sesión distinta: el cliente debe omitirlos. El cliente offline actualizado conserva los IDs recibidos en su propia sesión.
- No hay borrado ni reordenamiento implícito al omitir filas de un snapshot. Se conservan filas pendientes y resultados existentes; payloads truncados/reordenados se rechazan. El editor ofrecido no tiene una operación de borrado histórico.
- Receipts antiguos se decodifican sin consultar el estado actual; campos nuevos ausentes quedanNone/vacíos. Repetir owner+mutation+digest devuelve el snapshot original, aunque sea anterior a esta migración. No se reescriben receipts ni se considera un replay una nueva edición.

## Intención y adaptación realizada

La política pura compartida entre manual y sync congela en copias vinculadas todos los target_*, exercise, kind, load_type, tempo, range_of_motion, side, group, rest_seconds y rm_reference; también disciplina/título/targets del bloque y la prescripción del intervalo. Resultados, descanso real y notas de ejecución se registran aparte.

Una adaptación realizada usa `actual_exercise`, `actual_load_type`, `actual_kind`, `actual_tempo`, `actual_range_of_motion`, `actual_side`, `actual_group` y `adaptation_reason`. Cualquier override requiere motivo explícito de1–1000 caracteres. El ejercicio real es FK protegida de catálogo. Los campos originales permanecen intactos; la comparación original/real y el motivo se muestran/exportan. Por ejemplo, una serie originalmentework/external puede registrarse como fallida/asistida con motivo sin destruir la clasificación prescrita.

Volumen externo y estimador conservan sus fórmulas: utilizan clasificación realizada explícita si existe, o la original si no hay adaptación. Assisted/bodyweight no se convierten en kg externos. No se infiere RM, esfuerzo ni peso realizado desde %RM o targets. ReferenciasRM deben seguir siendo propias, compatibles y no futuras.

## Presencia de campos de adaptación — revisión backend B1

En mutaciones, omitir un campo de adaptación no significa borrarlo. JSON y POST conservan el conjunto de claves realmente presentes mediante `AdaptationField`/`AdaptationPresence`, contratos puros tipados en los comandos; esa presencia no se almacena ni se publica como observación. El conjunto vacío describe al cliente legado que no conoce estos campos. `None` en la metadata del comando Python significa snapshot tipado completo, no un patch; los callers parciales deben indicar su conjunto explícito.

Con revisión vigente, un snapshot legado de notas o resultados numéricos conserva overrides y motivo existentes. Un cambio de `actual_kg/reps/rpe` no reclasifica ejercicio/carga/tipo. Manual y sync aplican la misma conciliación bajo los locks/guardas existentes. Snapshot/receipt de lectura se decodifica como historia, no como un nuevo patch.

No existe borrado implícito de observaciones: `null` o cadena vacía que elimine un override existente, y vaciar su motivo, se rechazan atómicamente (sin avanzar revisión ni crear receipt). Para volver a valores prescritos se declaran valores reales concretos —por ejemplo `actual_load_type="external"`, `actual_kind="work"` y el ID del ejercicio original— con un motivo explícitamente suministrado en ese cambio. No se borra la clasificación para activar un fallback de fórmula.

Toda modificación efectiva de un override requiere un motivo presente explícitamente en ese cambio y no vacío. El motivo no se hereda implícitamente para autorizar otro override: si se omite, el cambio se rechaza aunque exista un motivo anterior. Su texto sí puede repetirse legítimamente (por ejemplo, «por dolor» en dos adaptaciones). No hay unicidad ni deduplicación por texto, espacios o mayúsculas. Cada cambio aceptado avanza su revisión; en sync se guarda su snapshot en el receipt correspondiente. Repetir un motivo no convierte otro cambio en replay. Reenviar los mismos valores/motivo es válido; omitirlos sin cambiar overrides preserva lo existente. Las cadenas vacías nuevas de campos textuales no permiten eliminar un valor previo. Esta regla no modifica fórmulas, IDs/source, NULL/0 ni la idempotencia.

La evidencia por archivos backend propios se conserva en `.cache/MAM623_BACKEND_REVISION_REPORT.md` y su JSON. Corresponde a aquella fase de escritura paralela, no a aprobación independiente del compuesto. Sus snapshots, fallos y cifras no se transfieren automáticamente al candidato final.

La precisión posterior de presencia —sin la regla de texto distinto— se conserva en `.cache/MAM623_BACKEND_REASON_FIDELITY_REPORT.md` y su JSON. Esa adición sustituye únicamente la exigencia textual excesiva del reporte backend anterior; se mantienen las salvaguardas de omisión y borrado. La validación final se ejecuta de nuevo tras congelar el conjunto completo.

## Cola offline y corrección de validación — CLIENT623-R1

El almacenamiento IndexedDBv1 conserva `sessions`, `outbox` y `archive`. Lectura/decisión/escritura de la cola y acknowledgements son transacciones. Un registro nuevo es `unsent`; antes de fetch se reclama como `attempted`. Un pendiente legado sin metadata se trata como ambiguo, nunca como no enviado.

Solo un `HTTP400` con detalle JSON de validación confirmado permite `rejected_validation`. Corregir desde el editor puede coalescer el sufijo no enviado o definitivamente rechazado: archiva originales, crea mutation UUID nueva y usa la primera revisión no consumida, sin cambiar execution UUID, prescripción, IDs ni datos no editados. No se omiten campos para eludir las reglas backend. La corrección recupera errores de entrada; no reabre historial completed confirmado ni autoriza borrar observaciones con `null`.

Una petición en vuelo/ambigua conserva su clave y payload. Si la respuesta se pierde después de aplicar realmente el POST, el retry usa la misma identidad y recibe su receipt. Solo después de un400JSON definitivo se reconstruye una corrección ya solicitada. Un409 requiere decisión explícita;401/403/429/500,400HTML y fallos de red no se reinterpretan como rechazo de validación. Otras execution UUID permanecen independientes.

Los acknowledgements no reemplazan inputs de un editor abierto; su revisión solo avanza si corresponde a la misma versión local. Web Locks serializa consumidores; sin esa coordinación se conserva la cola y se ofrece corrección/exportación en lugar de enviar concurrentemente sin control. El runner de cliente ejercita IndexedDB real, corrección400 solo por UI, dos consumidores, edición en vuelo y timeout después de aplicación real, sin fabricar un200 que acepte datos inválidos.

Reproducción exacta del runner versionado y tipado, desde la raíz del worktree con el Python/Chromium existentes:

```powershell
& "C:\Users\Jonnathan\Mamut system\django-basis-trainning-app\.venv-win\Scripts\python.exe" -B "scripts/client623_queue_regression.py"
```

Cada ejecución crea SQLite/servidor/contextos y evidencia UUID propios en `.cache/client623-queue-*`; verifica los hashes servidos y deja `result.json`, capturas/traces y estado de limpieza. El código sigue incluido en el scope estricto de `mypy-django.ini`, sin whitelist legacy ni exenciones. Los16 escenarios/25receipts de fases anteriores son historia; se vuelven a ejecutar contra el candidato final congelado. Ni ese runner ni los reportes de implementación constituyen la nueva revisión independiente de cliente.

## Cierre parcial y desconocidos

Se mantienen in_progress/completed. **Completed significa cierre del registro, no cumplimiento total del objetivo.** Es válido cerrar parcialmente con series desconocidas. None no significa0, serieomitida ni fallo; tampoco se copian targets como resultados pendientes. Un0 declarado permanece0. Marcar una serie fallida mediante actual_kind requiere la entrada explícita y su motivo.

No se fabrica hora deportiva histórica ni se cambia la definición de adherencia. Calendario/progreso conservan sus contratos622/618. La UI explica cierre y desconocidos; el contexto IA local identifica UUID, estado y planned para no confundir sesiones del mismo día. Esto no acredita calidad ni operaciónLIVE de un proveedor.

## Persistencia y lectura

Migración aditiva `basis_training.0003_execution_identity`, después de0002: sourceFK opcionales y campos de adaptación. Sin backfill de fuentes ni resultados inferidos; PK/UUID/lineage/resultados existentes no cambian. La revisión/version de prescripción se obtiene por el FK estable; no se duplica como una medición inventada en Session. Los campos nuevos se exportan en las mismas secciones de basis-export-v1.

Las lecturas de snapshots precargan bloques/series/intervalos de forma acotada; las pantallas precargan ejercicios originales/reales. Se valida revisión y propietario antes de convertir el cuerpo tardío; errores de un hijo o del receipt revierten toda la mutación. El perfil personal gratuito y las guardas comerciales/CSRF permanecen sin cambios.

## Evidencia de la entrega (captura anterior a integracion)

El inventario final congelado vive en `.cache/MAM623_CANDIDATE.json`; el nuevo gate compuesto se documenta en `.cache/MAM623_FINAL_CANDIDATE_REPORT.md`, con manifests antes/después, comandos, logs y recursos propios por run. `.cache/MAM623_IMPLEMENTATION_REPORT.md`, los reportes backend/fidelity y `.cache/MAM623_CLIENT_REVISION_REPORT.md` se conservan como snapshots de sus fases, incluidos los fallos. No se atribuyen390PG/179puras de PR8 ni otros PASS previos a esta ejecución final.

Pruebas funcionales: `tests/regression/test_execution_records.py`, `test_adaptation_updates.py`; procesosPG: `test_execution_concurrency.py`, `test_adaptation_concurrency.py` y regresiones622; upgrade29→30: `test_execution_upgrade.py`; políticas puras: `tests_architecture/test_execution_identity.py`, `test_adaptation_updates.py`. Los runners finales ignorados `.cache/frozen_mam623.py gate` y `.cache/frozen623_operations.py` usan solo DB/puertos/caches sintéticos propios y herramientas existentes. La referencia operacional comprueba backup/restore de tablas y secuencias con adaptación y referencias de origen, no capacidad ni despliegue productivo.

El gate incluye regresiones622 y los cruces start/sync/manual/cierre/replay con espera real. SQLite, navegador real/IndexedDB y herramientas tienen recibos separados ligados al mismo candidato. Local VERIFIED no equivale a revisión independiente, CI remoto, merge o estadoDone. El readback formal622 fue confirmado antes de esta consolidación;623 aún requiere re-revisión backend y nueva revisión independiente cliente, además de la integración autorizada posterior.

## Revisión final de cierre desde una pestaña obsoleta

El cierre desde HTML antiguo cambia únicamente `status` sobre la copia local vigente, leída dentro de la misma transacción IndexedDB; no reemplaza medidas recientes por el snapshot del HTML. El editor vuelve a leer la copia actual al abrir y comprueba su versión al guardar. Si una edición pierde contra el cierre, conserva sus inputs y permite revisar el borrador pendiente por UI.

La nueva revisión independiente cliente **APPROVE** corresponde al authored `65dbf071a1275297ef2f5947b536bfed180e01c34bf4321d9ae5f19403bc3e7c`, antes de esta adición documental: cinco probes propios pasaron, con seis receipts y cero errores JS. Se repitió el P1 original mediante UI a390/1440 y ambos órdenes edición/cierre bajo bloqueo real de IndexedDB, liberado sin esperar una lectura bloqueada. Servidor y receipts conservan4×77.5,0×0, una tercera serie desconocida,600s/RPE5, intención e IDs. El timeout propio posterior a aplicación real conserva la misma clave al reintentar y no duplica el receipt.

Separadamente, el runner versionado fue inspeccionado y reejecutado: **21/21 escenarios,32receipts,0erroresJS**. Sus escenarios siguen siendo diseño del autor, no cinco probes independientes adicionales. Evidencia: `.cache/client623-rereview-sol-8ba907d626834df3811d82814183f008/` y `.cache/client623-queue-23ca65fb7c9c4aee9987d223556954bd/`.

El backend tiene **APPROVE independiente** sobre el congeladofe9; el cotejo completo verifica584archivos iguales y solo los dos cambios cliente (`offline.js` y runner), incluidos390Python ajenos al runner intactos. Los429PG/191puras/118+358mypy/8contratos del gate anterior siguen siendo evidencia histórica de ese árbol, no ejecuciones nuevas del revisor cliente. Inventario:29modelos de negocio,35registrados totales,39tablas,35secuencias y30migraciones; upgrade29→30 verificado por el revisor backend.

La adición documental genera un binding de entrega nuevo en `.cache/MAM623_RELEASE_BINDING_SOL.json`; `.cache/MAM623_CANDIDATE.json` permanece como manifiesto históricofe9. Los dictámenes son revisiones locales, no reviews formales de GitHub. Integración y CI alojado del SHA exacto se verifican después; no se acredita SMTP/IA/pagosLIVE, dispositivos físicos ni lectura humana de otros hitos, y esta nota no cierra623.

## Readback de integracion y cierre 2026-10-21

**MAM-623 ya estaba Done** en el primer readback de Luna, `completedAt=2026-10-21T19:29:27.562Z`, conservado sin nueva transición. Los cuatro criterios quedaron VERIFIED. Luna actualizó el comentario existente `8e90525d-2e80-44db-a483-f5f93e0fe8d8` a `2026-10-21T19:47:08.184Z` y cotejó exactamente el cuerpo de retorno. El inventario final de las19:47:27.908UTC conserva46tickets,22Done/23InProgress/1Backlog. Los pendientes de integración/revisión de las capturas anteriores ya fueron resueltos; sus FAIL y manifests siguen históricos.

[PR #9](https://github.com/Mamut1195/django_basis_trainning_app/pull/9) MERGED: commit `dbae5dbc767d69d3d294478583d84144d7f452f8`, merge `71751bd2ee10fa7dff9f2c7a9d4f9ccda7c6c2cd`. [CI postmerge 39662083662](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39662083662) SUCCESS en ese SHA:429PG/191puras, mypy118/358 y ocho contratos, más Docker/Gunicorn/logging/health. Las5sondas/6receipts y el runner21/21/32receipts anteriores siguen siendo pruebas locales; Luna no repitió navegador ni los contó como CI.

[Artefacto12376055219](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39662083662/artifacts/12376055219): JSON SHA256 `5255fb5c3c4171782ab1b81aa3460e557d5ce8abd083822167f322914fda8717`, ZIP `9c12532fc51184fdbac72cba37c27b3539eaaa86f89835f5b52981d184c80c8c`;586hashes de fuente y586GitblobIDs cotejados al merge. CI restaura39tablas/35secuencias,30migraciones y160/160HTTP200; su fixture10perfiles/20planes/120sesiones/360series/10RM **no incluye el suplemento local específico de adaptación**. Inventario29modelos de negocio/35registrados totales; no son35modelos de negocio.

Las aprobaciones independientes son locales, no reviews formales de GitHub. La consulta de reviews/comentarios/latestReviews de PR9 fue denegada a Luna y no se reintentó; el dato comunicado de cero reviews no se presenta como revalidado en ese puente. [Fuentes del cierre y límites](DEVELOPMENT_2026-10-21.md#procedencia-y-limites-de-la-evidencia). SMTP/provider LIVE, producción, dispositivos físicos y los gates humanos626/627 no se certifican con este cierre.
