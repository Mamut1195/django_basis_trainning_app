# MAM-811 — resistencia, intervalos y referencias privadas

Base del candidato: `3edc3c11a378d66b3ab1a857c5753ac8074bbd4c`.
Rama: `feature/mam-811-endurance`. Los resultados del ejecutor y del revisor se distinguen abajo; los resultados de integración se enlazan en el PR.

## Contrato implementado

- El diccionario ejecutable actual es `basis/modules/training/domain/sports.py`:
  **55 entradas en total entre disciplinas**, compartidas por modelos, formularios, API y sync.
  Las rutas antiguas `training/domain.py` de los documentos históricos son anteriores
  a la modularización. Esta entrega conserva sus variables, unidades y máximos.
- Duración/distancia de bloque e intervalo usan s/m; potencia medida W y cadencias
  conservan sus claves explícitas por deporte. Se rechazan claves de otra disciplina,
  unidades embebidas en números, booleanos, valores no finitos y rangos fuera del
  contrato. Son límites de almacenamiento/validación existentes, no límites
  fisiológicos ni recomendaciones de entrenamiento.
- Ausencia/null/vacío numérico significa desconocido. Un cero registrado permanece
  cero, incluido descanso 0 s. La pausa por sí sola tampoco puede superar la duración
  transcurrida conocida. No se suman intervalos de nuevo a los totales del bloque.
- Umbrales nuevos o modificados requieren valor decimal positivo, unidad compatible,
  fecha no futura, método, tipo **medido/estimado** y fuente declarada. Se mantiene la
  edición de experiencia de referencias legacy con procedencia desconocida; no se
  inventan ni se borran metadatos ya documentados. El campo `method` sin valor de
  umbral conserva su uso legado como nota de perfil.
- El lector público `athletes.SportThresholds` consulta el perfil **actual y único**
  de la cuenta y disciplina, con fecha de referencia no posterior a la prescripción
  ni a hoy. Usa account ID, no PK del perfil de atleta, y respeta el alias SQL. No
  busca un registro de otro deporte ni supone un historial inexistente del perfil.
- Al crear un bloque prescrito se guarda un `ThresholdSnapshot` tipado en un JSON
  servidor: profile ID, deporte, valor, unidad, fecha, método, tipo y fuente. Es
  contexto congelado; no calcula zonas, porcentajes, cargas o resultados.
- Revisar/restaurar/copiar un plan conserva el snapshot original, incluido `null`.
  Empezar una ejecución copia ese snapshot y los objetivos e identidades de origen;
  no rellena observaciones, RPE real ni descansos reales. Editar posteriormente el
  perfil no cambia ninguna de esas referencias históricas.
- Sync serializa el snapshot con los IDs de origen. Un codec legacy que omite el
  campo no lo elimina ni lo actualiza. Intentar falsificarlo se rechaza atómicamente.
  El cliente offline existente clona/serializa el objeto completo; no se cambia su
  cola, su IndexedDB ni su protocolo de reintentos.
- Las vistas de prescripción/ejecución muestran la referencia congelada o su ausencia.
  La exportación privada incluye los nuevos campos mediante el exportador existente.
  El codec de contexto ya existente conserva los dos metadatos nuevos; no se altera
  el guard comercial, el acceso personal gratuito, RM ni el comportamiento de IA.

## Migraciones aditivas

- `basis_athletes.0003_sportprofile_threshold_kind_and_more`: tipo/fuente de referencia.
- `basis_training.0004_block_threshold_snapshot`: snapshot nullable después de
  `0003_execution_identity`. Sin tablas nuevas ni backfill de referencias históricas.
- Las migraciones anteriores no se reescriben. El test de upgrade usa ORM histórico,
  conserva IDs/resultados/cero y confirma snapshot desconocido después de migrar.

## Evidencia propia y reproducción

Regresiones: `tests/regression/test_endurance.py`, **13 tests nuevos**. Recorren las
55 variables, límites numéricos, null/cero, incompatibilidades, formularios, sync
HTTP, recibos idempotentes, propietario inyectado, exportación privada, copia profunda
del cardio del sábado, procedencia congelada y migración legacy.

Ejecutado antes de gates finales:

- 88 pruebas dirigidas SQLite: OK, 21 skips de concurrencia PostgreSQL.
- 13 pruebas nuevas PostgreSQL 18.4: OK, sin skips; base fresh y upgrade incluidos.
- mypy Django: OK, 366 archivos.

La pasada final se registra en `.cache/MAM811_IMPLEMENTATION_REPORT.json` y su resumen
`.cache/MAM811_IMPLEMENTATION_REPORT.md`: comandos, salidas, versiones, estados y
SHA-256 de **cada archivo modificado/nuevo**, más binding agregado. Los logs y bases
de verificación son exclusivos de este worktree. Las pruebas no leen `.env`, no usan
la base del usuario ni llaman proveedores externos.

Para repetir solo las regresiones nuevas con el intérprete existente y configuración
de prueba aislada: `python -B manage.py test tests.regression.test_endurance --noinput`.
Definir antes `DJANGO_SETTINGS_MODULE=config.test_settings`, una clave pública de
pruebas y `DATABASE_URL` de una PostgreSQL desechable propia (o vacío para SQLite).

No se atribuyen a esta entrega las 446 pruebas de la base, CI previo, calidad deportiva
LIVE ni operación de proveedores. Los totales finales propios y sus skips están en
el reporte. Navegador real y build Docker se informan explícitamente si no se ejecutan.

### Resultado final propio: LOCAL_READY

| Gate | Resultado ejecutado en este candidato |
|---|---|
| Suite PostgreSQL 18.4 | **VERIFIED**: 459 tests, sin skips; 446 existentes + 13 nuevos. Incluye fresh/upgrade, aislamiento de cuentas, alias SQL y concurrencia real heredada. |
| Suite pura | **VERIFIED**: 191 tests existentes, ejecutados de nuevo sobre este candidato. |
| Tipos | **VERIFIED**: mypy core 119 archivos; Django 366 archivos. |
| Arquitectura/imports | **VERIFIED**: architecture check; 8 contratos conservados, 0 rotos. |
| Lint/formato | **VERIFIED**: Ruff check/formato y djlint. |
| Frontend | Prettier nativo señaló CRLF en 9 archivos sin cambios; **VERIFIED** formato de esos mismos bytes normalizados LF en memoria, comprobados idénticos a HEAD. Sin modificar CSS/JS. |
| Django/schema/estáticos/diff | **VERIFIED**: system check, ausencia de drift de migraciones, collectstatic y diff whitespace. |
| Navegador real/build Docker/CI remoto/LIVE | **NOT RUN**. |

El primer proceso de suite PostgreSQL fue interrumpido por el límite de 120 s del
harness. Se repitió exclusivamente ese gate interrumpido con log persistente y límite
600 s: 459 tests OK en 194,891 s. Los demás gates finales no se repitieron.

## Revisión independiente — APPROVE local

El revisor comprobó los **27 archivos** contra el binding del ejecutor
`2e2d2df1e647fa7c5a8137c8f4f59feba76ab714b771fddc348007eb2be71841`:
ninguna diferencia de implementación o tests. Solo esta documentación se amplió.
Revisados dominio, modelos, DTO, wire, exportador privado y consumidores.
Sin defectos bloqueantes encontrados y sin cambios de código del revisor.

| Criterio literal | Evidencia focal propia del revisor |
|---|---|
| Bloques ordenados objetivo/real, repeticiones y descanso; unidades explícitas; RPE opcional | 13 regresiones PostgreSQL OK, 0 skips (4,180 s). Dos copias sucesivas comparan objetivos e intervalos completos; descanso objetivo 0 permanece 0, resultados y RPE real ausentes permanecen desconocidos. |
| Validar variables incompatibles, datos ausentes y rangos | Regresiones recorren las 55 entradas, sus límites declarados, null/cero, booleanos y unidades incompatibles. Chromium rechaza running/W sin persistir el formulario. |
| Umbrales con unidad/fecha/método; congelar referencias históricas | Formulario real guarda estimado/fuente. Prescripción, dos copias e inicio conservan snapshot. Editar después valor/método/fuente del perfil no reinterpreta la ejecución. Sync legacy omitiendo snapshot lo conserva. Procedencia legacy sin fecha/método no se fabrica. |
| Aislamiento entre cuentas | Regresiones de owner inyectado y AccountId distinto del PK de atleta; probe propio deniega historial ajeno y excluye la fuente privada de su exportación. |
| Flujo web pertinente | Django nativo con PostgreSQL desechable y Chromium **153.0.8010.12**, binario compartido revisión **1243**: formulario, prescripción, copia histórica e inicio/ejecución, a **390 y 1440 px** (8 capturas), sin overflow horizontal ni errores JavaScript. |
| Perfil personal gratuito y guard comercial | Probe propio confirma edición personal HTTP 200 con período vencido; escritura de entrenamiento HTTP 403. |
| Migraciones fresh/upgrade | Fresh propio aplica **33 migraciones totales**, incluidas las **2 nuevas aditivas**. Regresión de upgrade conserva PK/FK, UUID de sesión, resultados y snapshot null; no backfill ficticio. |

Evidencia run-owned: `.cache/MAM811_REVIEW_REPORT.json`,
`.cache/mam811_review.py`, `.cache/mam811-review-migrations.log` y
`.cache/mam811-{threshold-form,prescribed,copied-history,execution}-{390,1440}.png`.
Comandos propios: `python -B manage.py test tests.regression.test_endurance --noinput --verbosity 2`
y `python -B .cache/mam811_review.py`, con configuración explícita aislada.
Los intentos iniciales del runner corrigieron espera de navegación, compatibilidad
del ORM con el loop idle de Playwright y orden de copia anterior al inicio; no
requirieron cambios del producto. El resultado final ejecutó **32 comprobaciones OK**.

**Evidencia reutilizada**, no repetida localmente: 459 PostgreSQL, 191 puras,
mypy 119/366 y 8 contratos del ejecutor sobre los mismos bytes de implementación.
CI hosted en árbol limpio del candidato y del merge debe verificar sus propios
totales, build Docker, logging Gunicorn, deploy checks, migraciones y operaciones
backup/restore/HTTP; se registra en el PR y reporte de integración con SHA exacto.
El fixture operacional heredado no contiene umbrales: su backup no sustituye las
pruebas focales de snapshots anteriores. LIVE dispositivos/proveedores: **N/A**
para este alcance manual sin GPS ni wearables. MAM-816 conserva su gate separado.
