# Cierre documental del lote — 2026-10-21

## Cierre de la cadena MAM-810 / 620 / 622 / 623

**Lote cerrado; no se inicia ningún ticket nuevo.** Se concilian los estados ya verificados por Luna REAL (`opencode-go/gpt-6-luna`, agente `build`). El último export es `ses_ea005619bffeFsGUiK767yO4cv`: fuentes locales leídas `luna-mam623-close-20261021-1939/source-audit.sanitized.json` y `luna-mam623-close.report.sanitized.md`, bajo Temp/opencode. Esta entrega modifica solo documentación y Git; no opera Linear/Notion ni cambia estados, prioridades o relaciones.

Luna encontró los cuatro tickets **ya Done**, verificó la evidencia y conservó sus `completedAt`; no se le atribuyen nuevas transiciones. Todos los timestamps siguientes son UTC del2026-10-21:

| Ticket | Estado / completedAt conservado | Integración de código | CI postmerge histórico: PG / puras / mypy core-Django |
| --- | --- | --- | --- |
| MAM-810 | Done / `04:35:13.492Z` | [PR #6](https://github.com/Mamut1195/django_basis_trainning_app/pull/6), `58cbb0ea2e7421a696629391cb8a5eebf2df76fe` | [39544853138](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39544853138):318 /174 /113-335 |
| MAM-620 | Done / `05:03:54.506Z` | [PR #7](https://github.com/Mamut1195/django_basis_trainning_app/pull/7), `25af153d5108d39c97bf5cda6fea58d6a6346f7b` | [39547452496](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39547452496):346 /176 /115-340 |
| MAM-622 | Done / `15:27:40.765Z` | [PR #8](https://github.com/Mamut1195/django_basis_trainning_app/pull/8), `cccc448c4aeaffef8d7a9e60bbab0b174e24ce42` | [39624647162](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39624647162):390 /179 /115-350 |
| MAM-623 | Done / `19:29:27.562Z` | [PR #9](https://github.com/Mamut1195/django_basis_trainning_app/pull/9), `71751bd2ee10fa7dff9f2c7a9d4f9ccda7c6c2cd` | [39662083662](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39662083662):429 /191 /118-358 |

Los cuatro runs de código terminaron SUCCESS con `postgres` y `operations`, ocho contratos conservados y cero rotos. Sus cantidades permanecen vinculadas a sus SHAs originales; no son pruebas locales nuevas de quien reconcilia estos documentos ni PASS transferibles a la futura CI documental.

MAM-623 conserva sus cuatro criterios VERIFIED: múltiples sesiones/series,5×80prescrito separado de4×75real, cierre parcial sin inventar pendientes y consistencia transaccional. Comentario existente `8e90525d-2e80-44db-a483-f5f93e0fe8d8`, actualizado `2026-10-21T19:47:08.184Z`, con readback exacto. No se cambió su descripción ni el historial de estados. Las capturas originales de preparación, candidatos BLOCK, fallos y manifiestos conservan su contexto; sus pendientes no describen el estado actual.

## Inventario actual y frontera de este lote

Última lectura completa de Luna: **2026-10-21T19:47:27.908Z**, incluidos archivados y sin página siguiente. **46 tickets =22Done+23InProgress+1Backlog**,24abiertos. Funcionales: **35=11Done+24abiertos**; arquitectura: **11Done**. `ROADMAP.json.current_readback` refleja esta lectura; el grafo funcional sigue con35nodos/86dependencias. `catalog_operations_readback`, `postmerge_readback` y `docs/architecture/linear-readback.json` preservan sus snapshots anteriores, no son nuevas consultas.

Solo dos High están libres de dependencias formales abiertas para futura implementación local; **no se inicia trabajo en ninguno**:

- **MAM-811 / BASIS-026**, In Progress; depende de618/623 Done. Su alcance futuro es validar variables incompatibles, ausencias y rangos, copiar prescripciones sin inventar resultados y congelar referencias históricas. No implica iniciar running, ciclismo, natación ni otras ampliaciones en este lote.
- **MAM-816 / BASIS-031**, In Progress; depende de810 Done. Alcance futuro local: firma inválida, replay, orden invertido, renovación, cancelación, impago y reembolso; un redirect no concede entitlement. Polar sandbox LIVE, sujeto a configuración, es un gate de aceptación LIVE/cierre, no un bloqueo inventado para iniciar trabajo local. No se realizan checkout ni llamadas LIVE aquí.

No se inventa un tercer High elegible. MAM-626/MAM-627 siguen In Progress; lector de pantalla **NOT RUN**, aceptación del propietario **PENDING**. MAM-627 depende de626. MAM-638 conserva once bloqueantes abiertos y MAM-636 sigue Backlog. Este documento cierra el lote actual, no autoriza su siguiente ejecución.

## Contratos conservados

Perfil personal, objetivo de texto, preferencias/disponibilidad, disciplinas y peso son **gratuitos** bajo cuenta activa, perfil vinculado y correo verificado para escritura. La consulta/exportación de datos propios conserva la política autenticada existente; no se impone un entitlement comercial nuevo para recuperar datos. Entrenamiento, RM, Goal estructurado, planes e IA conservan sus permisos comerciales.

Siguen vigentes IDs/source/origin/supersedes protegidos, resultados separados de intención, NULL distinto de0, fuentes históricas congeladas y orden de locks hasta COMMIT exterior. El cierre desde HTML antiguo usa el borrador local actual dentro de la transacción IndexedDB; las correcciones400 no descartan peticiones ambiguas ni resuelven409 automáticamente. Esta conciliación no cambia código, configuración, CI, tipado, esquema ni fórmulas.

## Procedencia y limites de la evidencia

- **620:** el [artefacto12322016375](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39547452496/artifacts/12322016375) tiene miembro `operations.json` SHA256 `7b66b7d53e6ed3d13cfdf533839fc50dd89a65dc501bedbc53156366ca302da0`; el ZIP es `43605d796a55fac63a50d0f3b5add73e080b6ed7215c5c7486f22082240d85d8`. CI contiene10EmailVerification y0Measurement; las3mediciones/12verificaciones restauradas localmente son suplemento separado. El reporte agregado no acredita estados pending/disabled por fila.
- **623:** el [artefacto12376055219](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39662083662/artifacts/12376055219) declara el merge exacto,586hashes de fuente cotejados y JSON SHA256 `5255fb5c3c4171782ab1b81aa3460e557d5ce8abd083822167f322914fda8717`; ZIP `9c12532fc51184fdbac72cba37c27b3539eaaa86f89835f5b52981d184c80c8c`. Fixture CI:10perfiles/20planes/120sesiones/360series/10RM;39tablas/35secuencias/30migraciones y160/160HTTP200. El suplemento local de adaptación no se atribuye al fixture CI.29modelos de negocio y35registrados totales son universos distintos.
- Las5sondas independientes de cliente623/6receipts y el runner del autor21/21/32receipts son resultados locales previos; Luna no repitió navegador. Los APPROVE independientes son locales, no reviews formales de GitHub. La consulta de reviews/comentarios/latestReviews de PR9 fue denegada a Luna y no se reintentó ni eludió; no se presenta cero reviews como dato revalidado por ese puente.
- SMTP LIVE/proveedor, IA/pagos LIVE, despliegue productivo, dispositivos físicos y lector/aceptación humana siguen NOT RUN/PENDING según su alcance. SMTP no es gate de810 ni de623. Docker/Gunicorn y el workload WSGI de CI son verificaciones técnicas con PostgreSQL desechable, no despliegue real ni capacidad de1.000usuarios.

Fuentes saneadas verificadas: `source-audit.sanitized.json` SHA256 `323d159b6d3b88eb1c3d0db5dc1d10fcad9457ae65e261e8d5f254a6c2e98ba3`; reporte SHA256 `345053297a17bcf443a371b9dcfd234004b69045e386da9c8274f09fc9aa60f1`. Son archivos locales aportados, no recursos versionados ni nuevas operaciones del tracker. La CI del PR documental y del SHA de merge correspondiente se verifica y entrega separadamente mediante los checks de GitHub y el recibo local de este lote.
