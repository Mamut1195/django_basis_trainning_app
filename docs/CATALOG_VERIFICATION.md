# MAM-621 / BASIS-007 — catálogo y variantes

## Alcance y fuentes

Estado actual: **MAM-621 Done**, integrado por PR #3; ver el
[readback de integración y cierre](#readback-de-integración-y-cierre-2026-10-21).
Los siguientes registros locales conservan sus propios candidatos y resultados.

Captura de implementación local en `feature/mam-621-catalog`, base
`fc3da6319024f3b49eb89cff0d9d42271747b655`. Implementación y evidencia en el
worktree run-owned `basis-mam621-20261020`. Esa captura local, por sí sola, no
acreditaba integración en main ni cierre del ticket; el readback posterior es separado.

Criterios contrastados con el informe sanitizado de Luna
`luna-bridge-mam637-mam621-20261020-2322.report.sanitized.md`, sección MAM-621,
readback de `2026-10-20T23:24:51.775Z`. Este ejecutor leyó ese artefacto local;
no consultó ni modificó Linear/Notion. Contrato vigente:
[TRAINING_CONTRACT.md](TRAINING_CONTRACT.md) y
[TRAINING_VARIABLES.md](TRAINING_VARIABLES.md).

## Implementación

- API de ejercicios: búsqueda por nombre/descripción y filtros combinables de
  clasificación, equipo, patrón, fatiga descriptiva, etiqueta de variante y padre.
  Parámetros tipados y acotados; entradas inválidas devuelven 400.
- Filiación opcional `Exercise.variante_de`, con FK `PROTECT` y rechazo de ciclos
  directos/indirectos en las escrituras validadas. El padre archivado conserva su
  identidad. `variante` sigue siendo la etiqueta descriptiva existente.
- Catálogo activo por defecto. Personal puede consultar/editar el archivo con
  `?archivado=true`; cuentas ordinarias reciben 403 para ese filtro. El historial
  privado sigue resolviendo los ejercicios archivados por sus identidades.
- El admin presenta filiación, equipo y archivo; incluye autocomplete del padre,
  filtros y búsqueda. Carga clasificación/padre con joins. API conserva un join
  de clasificación y serializa la filiación por ID, sin consultas por padre.
- La sustitución utiliza el versionado existente de planes y la edición de la
  nueva prescripción: `previous`, `lineage` y `version` conservan la procedencia;
  las series/prescripciones anteriores mantienen ejercicio, carga y referencia RM.
  Una variante no hereda el RM de otro ejercicio. No se modifica training runtime.

## Contrato de consulta

`GET /api/v1/exercises/` requiere sesión autenticada. Escrituras requieren staff.
La paginación existente devuelve 50 filas por página, ordenadas por nombre y PK.

| Parámetro | Semántica |
|---|---|
| `q` | Subcadena de nombre o descripción, insensible a mayúsculas; máximo 255 caracteres. |
| `classification` | ID positivo de clasificación. |
| `variante_de` | ID positivo del padre directo; no expande ancestros automáticamente. |
| `equipo` | Coincidencia exacta del texto declarado, insensible a mayúsculas. |
| `patron_movimiento` | Coincidencia exacta del patrón declarado, insensible a mayúsculas. |
| `nivel_fatiga` | `Bajo`, `Medio` o `Alto`; atributo descriptivo, no recuperación del atleta. |
| `variante` | Coincidencia exacta de etiqueta, insensible a mayúsculas. |
| `archivado` | Booleano; por defecto false. true requiere staff. |
| `page` | Paginación DRF existente. |

Ejemplo: seleccionar candidatos para una prescripción de sentadilla con mancuerna:
`/api/v1/exercises/?equipo=Mancuerna&patron_movimiento=Sentadilla`.
Los filtros se combinan mediante AND; la persona elige el ejercicio y prescribe
su carga/repeticiones/ROM/lado en las series. `Barra` no equivale a `Barra y discos`.
Equipo vacío significa dato no declarado, no disponibilidad universal.

## Equipamiento, unidades y límites de producto

El contrato representa equipo como texto descriptivo y fuerza mediante las series:
`external`, `bodyweight`, `assisted`; cargas decimales en kg; lado `both`/`left`/
`right`; repeticiones, segundos, RPE/RIR y referencia RM opcional. Volumen externo
no mezcla peso corporal ni asistencia con carga externa. El bienestar/recuperación
permanece en los registros privados del atleta.

No se define en las fuentes un inventario canónico de equipos, equivalencia de
máquinas/bandas, conversión de placas nominales, cargas por mancuerna frente a
totales, ni sustitución automática basada en fisiología. No se infieren esas
reglas. Si se necesita un motor de compatibilidad o una lista exhaustiva de
sustitutos deportivos, producto debe proporcionar esas reglas primero.

La filiación declara una relación de catálogo, no equivalencia de rendimiento.
La trazabilidad de sustitución demostrada es entre versiones de plan; no se ha
añadido una entidad independiente de motivo/autor de sustitución ni una transición
que reescriba ejecuciones completadas. `QuerySet.update`, bulk y SQL directo no
ejecutan `clean`, igual que las demás invariantes validadas del contrato existente.

## Migración

`basis_catalog/0002_exercise_variante_de` agrega sólo una FK nullable con índice y
protección de borrado. Es necesaria porque una etiqueta de variante no identifica
su ejercicio de origen. No asigna parentescos por similitud de nombres ni hace
backfill de datos deportivos.

Se ensaya sobre PostgreSQL desechable: migrar catálogo a 0001, insertar una fila
legacy, migrar todas las apps a la versión final y comprobar identidad/equipo y
padre NULL. La suite crea además otra base de tests desde cero. Se verifica ausencia
de migraciones pendientes. Ningún paso abre la base original del usuario.

## Matriz de aceptación y evidencia

### Corrección de revisión F1/F2 — 2026-10-21 UTC

La revisión independiente encontró una carrera real en el primer candidato:
dos PATCH sobre filas distintas podían validar el grafo anterior y persistir
`A → B → A`. El gate secuencial anterior de 270 pruebas no acreditaba esa
invariante concurrente. Reproducción propia RED:
`.cache/verification-9ab78efaf244448e89a35440865d2d92/postgres-tests.log`.

La corrección está en `Exercise.save()`, compartido por API, admin y ORM:

1. Resolver el alias de escritura (`using` o router) y abrir `atomic` en ese alias.
2. PostgreSQL: adquirir `LOCK TABLE ... IN SHARE ROW EXCLUSIVE MODE`, antes de
   la validación autoritativa. El bloqueo es nativo de BD, autoexcluyente y dura
   hasta el commit/rollback de la transacción exterior, incluso con catálogo vacío.
   Protege escritores de filas distintas y procesos distintos; no usa mutex Python.
3. Leer el mapa PK/padre en una sola consulta sobre el mismo alias y revalidar el
   candidato antes de escribir. PostgreSQL usa además `SELECT ... FOR UPDATE` en
   esa lectura: un snapshot antiguo bajo REPEATABLE READ debe abortar con el error
   de serialización nativo, no validar silenciosamente un grafo obsoleto.
4. SQLite: reservar el escritor mediante un UPDATE de cero filas antes de leer;
   no se envía SQL de bloqueo PostgreSQL ni se confía en un `select_for_update`
   ignorado. Si una transacción exterior ya tiene un snapshot incompatible, SQLite
   puede rechazarla con `database is locked`; debe hacer rollback completo. No hay
   retry local ni bypass de validación. Otros motores se rechazan explícitamente.

SQLite conserva su papel de fallback de desarrollo; la configuración de
producción existente sigue exigiendo PostgreSQL y no se modifica en esta entrega.

El mapa completo elimina una consulta por ancestro sin limitar la profundidad:
`full_clean()` mide **3/3/3 consultas** con 1/8/32 ancestros, antes 3/10/34.
Tradeoff: O(tamaño del catálogo) de lectura/memoria en validaciones con padre y
serialización de escrituras de ejercicios, apropiada al catálogo administrativo
de bajo volumen. El listado sigue con COUNT + página con JOIN: dos consultas.

`full_clean()` aislado y la validación anticipada del formulario son preflight;
la garantía concurrente está en el `save()` transaccional. Continúan excluidos
`QuerySet.update`, bulk y SQL directo. La corrección no agrega migraciones ni
modifica la FK nullable, el contrato deportivo o permisos.

Pruebas nuevas versionables: `test_catalog_concurrency.py` cubre API/API, ORM/ORM,
admin/ORM, ciclo de tres aristas e aislamiento REPEATABLE READ. Un coordinador de
BD espera en `pg_locks` a todos los contendientes antes de liberar su bloqueo;
no hay barrera posterior al lock y los timeouts SQL/esperas están acotados.
Se comprueban aciclicidad persistida y archivo posterior. La sonda run-owned
SQLite/multi-alias ejecuta además dos procesos OS reales, transacciones frescas
y snapshots previos, y comprueba alias seleccionado/ausencia de escrituras en el
otro alias. Los códigos 400/409 de esa sonda clasifican excepciones: no acreditan
una traducción HTTP nueva para SQLITE_BUSY o SQLSTATE 40001.

La ejecución final y los hashes exactos se registran en
`.cache/MAM621_IMPLEMENTATION_REPORT.md`; los recibos JSON contienen comandos,
exit codes, versiones y manifiestos del runtime y de fuentes/tests.

| Criterio | Evidencia ejecutable |
|---|---|
| Encontrar ejercicio por equipo y prescripción declarados | `test_filters_combine_and_do_not_infer_equipment_equivalence`, paginación estable y formularios reales de prescripción/series. Filtros explícitos, sin equivalencia automática. |
| Sustitución trazable y archivo histórico | `test_versioned_substitution_preserves_original_and_archived_history`: plan anterior, ejecución completada, revisión, sustitución por HTTP, RM incompatible rechazado, copia original intacta, ejecución nueva y consulta histórica tras archivo; cuenta ajena recibe 404. |
| Sin consulta por clasificación | `test_list_queries_do_not_grow_with_classifications_or_variant_parents`: dos consultas de catálogo (COUNT + página con JOIN), con 2 y 17 ejercicios y clasificaciones distintas; mismo total de consultas de petición. |
| Cargas/unidades según contrato | `test_equipment_variants_keep_contract_load_types_and_decimal_kg`: tres tipos de carga, bilateral/unilateral, decimales, cero explícito y rechazo de tipo/unidad/texto/carga negativos no admitidos. |
| Validación requerida | Permisos de lectura/escritura/archivo, filtros inválidos, paginación, ciclos, referencias inexistentes y borrado protegido; navegador Chromium real sobre PostgreSQL. |

## Navegador y verificación

Resultado local final: **VERIFIED**, recibo
`.cache/verification-464ff7bc7c014f0eaa4694c6daada57b/result.json`.

| Check | Resultado de esta ejecución |
|---|---|
| PostgreSQL 18.4 | VERIFIED: 276 pruebas, 0 omisiones; baseline 270 + cinco concurrentes + un check de consultas por profundidad. |
| Suite pura | VERIFIED: 174 pruebas. |
| Mypy estricto | VERIFIED: 113 archivos core y 323 Django/tests. |
| Ruff lint/formato | VERIFIED. |
| Arquitectura e imports | VERIFIED: ocho contratos conservados, cero rotos. |
| Django y esquema | VERIFIED: `check`, migración desde vacío/legacy y sin drift. |
| Chromium 153.0.8010.12 | VERIFIED: siete recorridos, cero `pageerror`; capturas y traza. |
| SQLite y alias | VERIFIED: cinco checks reales; procesos frescos 200/400, snapshots previos 200/SQLITE_BUSY; grafos acíclicos y archivables. |

Runtime SHA-256:
`227290917db42fc77bb8bdad2098e53a9dd5c11f81e974e6bce37608a6fd88ec`.
Manifiesto ampliado de fuentes/tests/configuración:
`06d0410e00845ab89b4cf3a36a1510df468b37ceddc84e57f0c763210d8690ff`.
Ambos estables durante el gate; se conserva la lista completa de hashes en el
recibo. Esta documentación y el reporte se completan después del gate y se
verifican aparte con el diff. Los puertos de PostgreSQL y web fueron dinámicos;
cluster, servidor y navegador quedaron detenidos.

El runner local `.cache/mam621_browser.py` usa Chromium existente por ruta explícita,
perfiles temporales propios y servidor loopback dinámico. Recorre login staff,
creación mediante autocomplete real, listado con padre/equipo, filtro API bajo
sesión de navegador, archivo/restauración, error de ciclo sin escritura y login
ordinario con archivo/admin denegados. Guarda capturas y traza local.

Las comprobaciones y fallos intermedios se conservan en el reporte. El primer
launcher intentó un headless shell no instalado; se corrigió seleccionando el
Chromium existente, sin instalar dependencias. Un fallo previo de mypy en el test
se corrigió con tipos precisos y comprobación explícita de `planned` no nulo.

Para reproducir en este entorno Windows, desde el worktree, con el Python existente:

```powershell
& "C:\Users\Jonnathan\Mamut system\django-basis-trainning-app\.venv-win\Scripts\python.exe" -B .cache/mam621_gate.py --full
```

El runner es evidencia run-owned, no un nuevo script operativo del producto.
Levanta y detiene su propio cluster PostgreSQL con puerto dinámico y no descarga
toolchains. En aquella entrega local, review, integración/CI remoto y readback de
cierre correspondían todavía al orquestador; el resultado posterior se registra abajo.

## Readback de integración y cierre (2026-10-21)

Rama real `feature/mam-621-catalog`, commit
`e733e2c54eeb00092af9efd7fc1b19271c4b4841`, [PR #3](https://github.com/Mamut1195/django_basis_trainning_app/pull/3)
MERGED, merge `158235c035dc442e008fe4e423442c8c955aba9b`. El
[CI postmerge 39524085686](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39524085686)
es SUCCESS en ese SHA: **276 PostgreSQL, 174 puras, mypy 113 core/323 Django y ocho
contratos de imports**. Las pruebas locales anteriores, incluido RED de la carrera,
conservan sus hashes, entornos y resultados; no se reinterpretan como otro candidato.

La entrega conjunta posterior de operaciones conserva catálogo: merge PR #4
`5edf6bd515ed56289b76da3339c9acaa4a7d4680`, con
[CI 39527756424](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424)
SUCCESS: **288 PostgreSQL, 174 puras, mypy 113/330 y ocho contratos**. Es evidencia
del árbol conjunto, distinta del gate local y del CI de PR #3.

Según los exports de Luna `opencode-go/gpt-6-luna`, sesión
`ses_ea3e2209dffehoFNLoBgWy77bW`, **MAM-621 ya estaba Done** al consultar;
`completedAt=2026-10-21T00:53:58.059Z` se conservó. Verificó los cuatro criterios
de la matriz, corrigió la rama prevista en el comentario
`058dc6d7-ae69-4f6f-b208-fdb36255aa78` y registró el cierre
`14757265-2b57-44e4-b382-07cbca44b6c9` a `2026-10-21T01:47:28.696Z`, con readback exacto.
No cambió el estado ni reejecutó tests de aplicación. El APPROVE independiente de
agentes no es un review de GitHub: el API de PR #3 devuelve cero reviews.

[Fuente y conteos conciliados](DEVELOPMENT_2026-10-20.md#cierre-del-lote-mam-621-y-mam-637-2026-10-21).
MAM-622 sigue bloqueado por MAM-620 y MAM-623 por MAM-622; el cierre del catálogo
no inicia el siguiente lote. El CI propio del cambio documental se reporta aparte.
