# Goal

Cerrar BASIS-004 / MAM-617 con archivo del catálogo, conservación del historial,
normalización consistente y datos de demostración repetibles sin borrados.

Estado actual y matriz de los cuatro criterios: [readback tras revisión y Luna](#readback-actual-tras-revisión-independiente-y-luna-2026-10-20).
Las secciones previas a ese readback conservan los resultados y límites de sus
ejecuciones originales, incluidos los FAILED; no describen por sí solas el gate actual.

# Context

La revisión parte de `main/24484b7`. En una SQLite nueva se reprodujeron dos
escrituras ORM sin normalizar, en Classification y el perfil User, y dos ejecuciones
de `seed_demo` aumentaron los ejercicios de cinco a ocho por buscar nombres sin
normalizar que después se guardaban normalizados.

# Constraints

No usar ni migrar la base original. No modificar prescripciones, reprogramación,
esquema ni fórmulas deportivas. Conservar los datos existentes y el contenido
histórico del seed retirado. Producción y proveedores externos quedan fuera.

# Affected areas

Modelos de catálogo/perfil, fixture de demostración y pruebas de integridad.
El coordinador conserva la responsabilidad del guard temprano de `seed.py`, del
ensayo PostgreSQL/restauración y de la integración Git y conciliación de Linear.

# Implementation steps

1. Reproducir normalización ORM y seed repetido sobre una base nueva.
2. Reutilizar ValidatedModel para validar y normalizar guardados ordinarios.
3. Buscar los nombres canónicos del seed sin duplicar ni borrar datos anteriores.
4. Probar archivo e historial, borrados protegidos, validación ORM/API/admin,
   actualizaciones parciales y ejecución repetida del seed.
5. Ejecutar controles completos y ensayo de migración/respaldo/restauración antes
   de integrar y cerrar el ticket.

# Required skills

task-planning, systematic-debugging, safe-git-workflow y verify-before-complete.

# Validation

La reproducción inicial es VERIFIED en
`.cache/integrity-audit-442815e5070d4131a3f78901ee2b1906/`: ambos nombres sin
normalizar y cinco frente a ocho ejercicios. Los resultados posteriores se
registran al finalizar; una comprobación pendiente no se considera superada.

# Risks

La normalización puede revelar nombres de clasificación equivalentes a un nombre
único existente. Se rechaza esa escritura; no se fusionan registros ni se borra
historial. El seed tampoco corrige o elimina duplicados históricos. Si varias
clasificaciones anteriores coinciden sin distinguir mayúsculas, rechaza la
demostración con un error explícito y revierte todas sus escrituras; no elige
arbitrariamente una identidad del catálogo.

## Política de archivo y eliminación

Archivar un ejercicio lo retira del catálogo activo; su identidad, RM, registros
históricos y referencias en sesiones se conservan y siguen siendo consultables
por su propietario. El catálogo usado se protege con PROTECT. Una clasificación
con ejercicios y una cuenta o perfil con registros tampoco se borran en cascada.
Las rutas privadas de registros responden 409 al intento de borrado; las
eliminaciones administrativas protegidas revierten la transacción completa.

No hay una operación automática de purga de cuenta o anonimización. Desactivar la
cuenta impide el acceso sin borrar sus datos. Cualquier eliminación definitiva
requiere un procedimiento separado, explícito, revisado y precedido de respaldo;
este ticket no implementa ni autoriza una purga.

## Escrituras y normalización soportadas

Las entradas web/API/admin usan los casos de aplicación existentes. Los guardados
ORM ordinarios `create`, `get_or_create`, `save` y `update_or_create` ejecutan los
validadores de modelo y la función compartida de normalización. Cada modelo tiene
una única definición de `clean`. Los nombres obligatorios que quedan vacíos tras
normalizar espacios se rechazan antes de escribir, también para los ejercicios. `update_fields` sigue limitando las columnas
persistidas: normalizar un atributo en memoria no autoriza escribir una columna
excluida de esa lista.

`QuerySet.update`, `bulk_create`, `bulk_update` y SQL directo son operaciones de
persistencia de bajo nivel que omiten los hooks de Django; no son vías soportadas
para escrituras de usuario y no prometen normalización o reglas de aplicación.
Sus restricciones SQL siguen vigentes. Migraciones o reparaciones que las usen
requieren validación explícita y evidencia propia.

## Seeds y migraciones

`manage.py seed_demo` exige DEBUG, DEVELOPMENT_ACCESS y una contraseña de
demostración proporcionada por el operador. Se ejecuta en una transacción, no
borra filas y conserva la contraseña y los datos de cuentas existentes. Repetirlo
reutiliza el catálogo, los perfiles y el plan; no lo incluye el arranque/despliegue.
`seed.py` es una herramienta retirada y debe fallar antes de importar Django o
abrir una base; su contenido antiguo se conserva para recuperación.

Las migraciones iniciales de ARCH-09 crean el esquema modular nuevo en una base
vacía, según ADR-002. No son una actualización in situ del esquema retirado. La
base original se conserva; ejecutar las migraciones nuevas sobre ella no es un
procedimiento de importación soportado. Sobre el esquema final, una ejecución
repetida de migrate no debe cambiar filas ni relaciones. La restauración se
ensaya exclusivamente en otra base temporal nueva; el resultado real pertenece
al recibo del coordinador.


## Resultado del implementador: 2026-10-20

| Comprobación | Resultado real |
| --- | --- |
| Reproducción previa | VERIFIED: nombres ORM sin normalizar y seed repetido con 5 frente a 8 ejercicios. Las nuevas pruebas fallaron antes de corregirlos. |
| Nombres vacíos tras normalizar | VERIFIED: la nueva prueba fallaba para clasificación, ejercicio y perfil; los tres rechazan ahora espacios sin persistir filas. |
| `manage.py test basis.bootstrap.tests.test_integrity basis.bootstrap.tests.test_identity --noinput` | VERIFIED: 29 pruebas, cero omisiones, sobre la DB temporal del runner; incluye las 14 nuevas pruebas de integridad. |
| Ruff lint/formato de los cinco archivos Python de la entrega | VERIFIED. |
| `python -m mypy --config-file mypy-django.ini` | VERIFIED: 320 archivos en la ejecución final. |
| `manage.py makemigrations --check --dry-run` | VERIFIED: sin cambios de esquema. |
| `scripts/architecture_check.py` e Import Linter | VERIFIED: fronteras públicas/AST y ocho contratos; la corrección posterior de nombres vacíos no cambia imports. |
| `git diff --check` | VERIFIED sobre el árbol compartido. |
| Regresión amplia SQLite previa | FAILED: 234 pruebas, un assert de fixture y cinco omisiones PostgreSQL. El assert esperaba literalmente el nombre sin normalizar de la otra cuenta. Se corrigió para comparar con su valor persistido anterior y las 15 pruebas de identidad pasaron en el recorrido final anterior. |
| Regresión completa PostgreSQL, migrate repetido y respaldo/restauración | NOT RUN por este implementador; corresponde al recibo final independiente del coordinador. |
| Navegador de la entrega | NOT RUN por este implementador; lo ejecuta el agente UI sobre las fuentes finales. |
| Commit/main/Linear | NOT RUN por este implementador; no se declara cerrado el ticket. |

Las conexiones de pruebas usaron `config.test_settings`, una ruta exclusiva dentro
 de `.cache/` y ausencia de `DATABASE_URL` heredada. El runner creó y destruyó sus
bases de prueba; no abrió la base original. No se enviaron correos reales ni se
llamaron proveedores.

## Verificación delegada independiente: 2026-10-20

Se revisaron los cambios existentes de catálogo/perfil, fixture, guard temprano de
`seed.py`, ajuste de aislamiento en identidad y las 14 pruebas de integridad. No
se encontró un defecto adicional que justificase modificar la implementación.
Esta ejecución es nueva; no reasigna resultados de las corridas históricas.

Comando desde la raíz, usando el entorno y PostgreSQL 18.4 ya instalados:

```powershell
.venv-win/Scripts/python.exe -B .cache/integrity_delegate_gate_20261020.py
```

El lanzador es una copia acotadamente ampliada del gate local establecido:
agrega pruebas focalizadas, migración repetida con comparación, navegador y un
manifiesto completo del candidato. Su copia exacta ejecutada está en
`.cache/integrity-delegate-0a7fed2f46234775ac62b4435cc45976/executed-gate.py`.
El recibo y los logs nuevos están en el mismo directorio, en `result.json` y
`<comprobación>.log`; no se sobrescribieron recibos anteriores.

| Comprobación de esta ejecución | Resultado |
| --- | --- |
| Integridad e identidad en PostgreSQL | VERIFIED: 29 pruebas, incluidas las 14 de integridad, cero omisiones; `integrity-tests.log`. |
| Regresión completa PostgreSQL 18.4 | VERIFIED: 260 pruebas, cero omisiones; `postgres-tests.log`. |
| Núcleo puro | VERIFIED: 174 pruebas; `pure.log`. |
| Tipado estricto | VERIFIED: 113 archivos núcleo y 320 Django; `mypy-core.log` y `mypy-django.log`. |
| Fronteras e imports | VERIFIED: AST/arquitectura y ocho contratos; `architecture.log` e `imports.log`. |
| Lint y formato | VERIFIED: Ruff check/format, djLint y Prettier; logs separados. |
| Django, esquema y estáticos | VERIFIED: check, ausencia de deriva y collectstatic. |
| Migración desde vacío y repetida | VERIFIED: 25 migraciones; segunda ejecución sin migraciones aplicables, mismas filas de todos los modelos e historial de migraciones. |
| Seed repetido | VERIFIED: mismas identidades, cantidades y hashes de filas; cinco ejercicios. Las pruebas focalizadas verifican además contraseñas/datos previos y rollback por clasificación ambigua. |
| Historial y respaldo/restauración | VERIFIED: ejercicio archivado, RM/registros/referencias conservados, borrados protegidos y cuenta desactivada. Dump restaurado en otra base nueva con los mismos hashes de todos los modelos e historial de migraciones. |
| Navegador sobre runtime final | VERIFIED: 21 comprobaciones Chromium 153.0.8010.12; persistencia, offline/replay/conflictos, CSRF, logout y cuentas separadas; `browser/result.json`. Sin errores JavaScript. |
| Aislamiento y cierre de procesos | VERIFIED: cluster exclusivo en loopback y puerto libre; bases nuevas bajo el directorio de la ejecución. PostgreSQL, servidor y navegador detenidos; proveedores/SMTP deshabilitados. La base original no se abrió. |
| Git diff | VERIFIED: `git diff --check`; índice sin preparar. Copias de los 24 archivos previos en `baseline/`. |
| Integración en main, CI del candidato y tracker | NOT RUN: no commit/push ni acceso a Linear/Notion en esta delegación. |

### Identidad y límites de la evidencia

Base Git: `24484b7c8c5a4c0beb89ee1dc854c91581d7293a`. El recibo conserva dos
vínculos independientes, estables antes/después de todos los controles:

- Runtime: 349 archivos, SHA-256
  `5c456d64dbd6fa33847bdf5ac73c621de4bee8fc3b0a006471541e60db1980cb`.
  El navegador nuevo usa exactamente ese hash; `sources.json` y
  `browser/source-before.json` conservan los manifiestos.
- Candidato ampliado: SHA-256
  `cd047aa9cc6d1ac5d042d032d1b7520e501a504686c0291d7ca3187ee83a1026`.
  `candidate-before.json` y `candidate-after.json` incluyen archivos versionados
  y nuevos no ignorados, también pruebas, `seed.py`, CI, configuración y docs.
  Excluyen archivos de entorno, bases, logs y dumps; no abren ni guardan secretos
  del operador. No hubo diferencias durante la corrida.

Los dos documentos de esta entrega se actualizan después de la corrida para
enlazarla; sus nuevos bytes no forman parte del hash previo. Los cambios
posteriores al runtime o al código probado necesitan su propia evaluación; el
recibo no se transfiere a otro candidato por coincidencia de nombre de ticket.
La auditoría de preservación/diff posterior se guarda aparte en `delivery.json`
y `delivery.patch`, sin reescribir el recibo de ejecución.

Los criterios técnicos locales de BASIS-004 quedan verificados. No declarar
Done todavía: falta integrar el candidato revisado en `main`, verificar su CI y
confirmar el alcance/estado operativo mediante Luna. El navegador no acredita
aceptación UX humana, lector de pantalla, dispositivos físicos ni proveedores.

### Registro histórico: cambios concurrentes y comprobación complementaria

Tras el gate anterior, el readback de entrega rechazó correctamente la igualdad
global: cambiaron `basis/adapters/web/static/basis/css/app.css` y
`scripts/ux_acceptance.py`, además de estos dos documentos autorizados. El
ejecutor de integridad no escribió esos dos archivos de UI/UX. El gate anterior
conserva su hash y su resultado; no se presenta como verificación global del
runtime posterior. Código/modelos de integridad, sus pruebas, seed, CI y
configuración permanecen vinculados a los bytes probados, sujetos al readback.

Se lanzó un complemento nuevo con
`.venv-win/Scripts/python.exe -B .cache/integrity_delegate_supplement_20261020.py`.
El primer intento (`supplement/result.json`) detectó formato pendiente en el
script UX y se detuvo. Después de cambios externos, el segundo intento conservó
todos sus resultados en
`supplement-bd0aef8835bf4aaa9cbc37096ab0a5e3/result.json`, bajo el directorio de
esta entrega:

- VERIFIED: Ruff lint/formato del script UX, Prettier del CSS y navegador nuevo
  de 21 comprobaciones; fuentes estables durante el complemento, hash runtime
  `9f41b01e3fe11a0d8d8e8d0d11039fb24d72a040ff873940939341c72f8caaec`.
  Recibo de navegador en su subdirectorio `browser/result.json`; servidor y
  navegador cerrados. No se alteraron las fuentes UX para obtener estos resultados.
- FAILED: mypy Django, siete errores en `scripts/ux_acceptance.py` (líneas
  314, 356 y 365–369 en esos bytes: `len`/iteración sobre `object`). Log exacto:
  `supplement-bd0aef8835bf4aaa9cbc37096ab0a5e3/mypy-django.log`.
- PostgreSQL NOT REEXECUTED en el complemento: los dos cambios concurrentes
  afectan CSS y la medición UX, no la persistencia ni las pruebas de integridad.
  Las 260 pruebas pertenecen exclusivamente al gate original de esta delegación.

El complemento global queda FAILED por tipado, aunque su navegador pasó.
Corresponde al ejecutor UX corregir y verificar su archivo. No cerrar el ticket
ni integrar un candidato global rojo; cualquier cambio posterior necesita
readback y comprobaciones pertinentes. `delivery.json` separa mis dos documentos,
los cambios externos observados y los hashes de cada ejecución.

## Readback actual tras revisión independiente y Luna: 2026-10-20

La revisión independiente aprobó el código y confirmó el gate técnico del
candidato final. Su [recibo local](../.cache/independent-review-a5614455b6c040438616780d94269822/result.json)
está VERIFIED y conserva `sources_edited: false`, `candidate_unchanged: true`
y `runtime_unchanged: true`. Se leyó ese recibo y sus logs; esta actualización
documental no constituye otra ejecución de las suites ni CI remoto.

| Gate del revisor independiente | Readback |
| --- | --- |
| Mypy Django / núcleo | VERIFIED: 320 / 113 archivos; `mypy-django.log` y `mypy-core.log`. |
| Ruff lint/formato, djLint y Prettier | VERIFIED: todos los exit codes cero. |
| Arquitectura e imports | VERIFIED: arquitectura y ocho contratos. |
| Pruebas puras | VERIFIED: 174; `pure.log`. |
| Django y deriva de migraciones | VERIFIED: check y makemigrations dry-run. |
| Navegador final | VERIFIED: 21 comprobaciones; `browser/result.json`, servidor/navegador cerrados, sin errores JavaScript. |
| Runtime final | `d3ecd68ddced4c3d4bcc3de23c94be869ebdbf1847f7456d93b3fe251dc09533`; estable y coincidente en el readback documental. |
| PostgreSQL en esa revisión | NOT REEXECUTED: el recibo declara `postgres_reexecuted: false`; las 260 pruebas y ensayo de migración/restauración pertenecen al gate de integridad anterior, no se reasignan al hash final. |
| Integración y CI del futuro commit | NOT RUN; la aprobación local no demuestra publicación ni CI del candidato. |

El fallo de formato y los siete errores mypy del complemento histórico siguen
FAILED en sus recibos originales. La revisión posterior verifica mypy y formato
sobre sus propios bytes finales; resuelve aquel bloqueo actual sin cambiar los
resultados anteriores. Sus observaciones documentales R1/R2 se corrigen en
ROADMAP, README y ARCHITECTURE; esta entrega mantiene separados código aprobado,
corrección documental e integración pendiente.

### Criterios vivos de MAM-617 y cobertura concreta

Fuente: readback de Luna con modelo `opencode-go/gpt-6-luna`, sesión
`ses_ea48bb89affe113OniCrTc83lt`. Extracto verificable local:
`C:/Users/JONNAT~1/AppData/Local/Temp/opencode/luna-linear-20261020-ses_ea48bb89.md`.
Se consultó ese extracto, sin nuevas llamadas a Linear/Notion por este ejecutor.

| Criterio confirmado por Luna | Prueba o inspección que lo acredita |
| --- | --- |
| Archivar conserva y permite consultar sesiones y RM | `HistoricalIntegrityTests.test_archive_preserves_readable_rm_workout_session_and_export` archiva, comprueba salida del catálogo activo, GET de RM y registro histórico con 200, GET `/sessions/<id>/` con 200 y nombre del ejercicio archivado visible; verifica exportación y referencia RM de la serie intacta. Es consulta real de sesión/RM, además de conservación de filas. |
| Borrados y migraciones no destruyen historial inesperadamente | `test_deletion_cannot_cascade_through_catalog_profile_or_account` comprueba PROTECT, filas conservadas y DELETE API 409; `CatalogIntegrationTests.test_protected_delete_rolls_back_and_nonstaff_service_cannot_delete` cubre rollback/permisos. Gate de integridad: migrate desde vacío y repetido, snapshot de todos los modelos e historial de migraciones, backup/restore en otra base nueva con hashes idénticos. ADR-002 no autoriza migrar in situ la base retirada. |
| Un único clean y normalización por todas las vías soportadas | `test_model_sources_have_no_shadowed_clean_definition` inspecciona clases AST; pruebas de normalización ORM create/save, `update_fields`, vacíos, unicidad, API y admin; `AthleteIntegrationTests.test_profile_and_preferences_forms_change_only_owner` verifica la vía web. La revisión de `ValidatedModel.save` y `Exercise.save` confirma full_clean común, usado también por get_or_create del seed y por update_or_create; no se presenta una prueba dedicada de cada helper como ejecutada. Bulk/update/SQL directo son vías de bajo nivel excluidas explícitamente del contrato anterior. |
| Seed no destructivo por defecto y excluido de comandos de despliegue | `DemoIntegrityTests` verifica flags/contraseña, doble ejecución sin pérdidas, contraseñas/identidades previas y rollback ante ambigüedad. `test_retired_seed_rejects_execution_and_import_before_django` comprueba ambos modos antes de importar Django. Inspección de `Dockerfile` (collectstatic/gunicorn) y `compose.yaml` (web/worker process_ai_jobs): ningún comando de arranque/despliegue llama a seed.py o seed_demo. No se afirma un build/despliegue nuevo. |

Las pruebas focalizadas del gate PostgreSQL acreditan 29 casos, incluidos los 14
de integridad; el revisor independiente confirmó que los cambios posteriores no
afectaron los bytes de integridad/pruebas/seed. No se identificó un hueco de
consulta de sesión/RM ni un defecto de código que requiera ampliar esta entrega
documental. El límite de cobertura de helpers y de operaciones de bajo nivel
queda explícito en la matriz, sin prometer pruebas no ejecutadas.

### Estado operativo y siguiente integración

Luna confirmó BASIS-ARCH/MAM-821 Done, relacionado y no bloqueante para los 31
funcionales abiertos. MAM-617/MAM-626/MAM-627 siguen In Progress. La corrección
R1 elimina únicamente BASIS-ARCH de las dependencias actuales por código para
que coincidan con los IDs nativos; ROADMAP referencia el snapshot Git histórico
que conserva ese prerrequisito anterior. No cambia los estados funcionales.

Lista para integrar tras verificar JSON/DAG, rutas y diff documental. El cierre
de MAM-617 sigue condicionado a commit integrado en main, CI verde de ese mismo
SHA y readback posterior por el orquestador/Luna. Los gates humanos de UX, lector
de pantalla y aceptación del propietario no se cierran con esta revisión.
