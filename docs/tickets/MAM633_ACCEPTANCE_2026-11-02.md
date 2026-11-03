# MAM-633 / BASIS-019 — contexto IA verificable: aceptación local

Fecha: 2026-11-02, America/Guayaquil. Resultado: **VERIFIED en el alcance local; LIVE e integración final NOT RUN**. No declara Done de MAM-633 ni de sus dependencias.

## 1. Goal

Completar la proyección mínima y privada del entrenador, con procedencia determinista, faltantes, límites y snapshots compatibles; comprobar preparación/envío mediante transporte simulado. La extensión autorizada proporciona una lectura con locks para el guard de propuestas de MAM-634, sin implementar ese guard ni su composición.

## 2. Context

Se leyó el ticket vivo completo [MAM-633](https://linear.app/mamutsystems/issue/MAM-633/basis-019-crear-contexto-y-herramientas-de-ia-sobre-servicios) y sus comentarios: In Progress, sin comentarios. Se revisaron instrucciones, arquitectura hexagonal, implementación, contratos públicos y `MAM815_ACCEPTANCE_2026-11-02.md`. MAM-815 tiene backend aceptado localmente; render/integración pertenecen a UX630 y no se declaran Done. No se encontraron AGENTS.md adicionales en el árbol/ancestros examinados.

Worktree aislado `t3/mam-633-ai-context-tools`, inicialmente limpio, desde `ab08dc3a645e770dea3ab4eea4c153ba925aec12`.

Commits locales de implementación validados:

- **`1b61b35c68a5b041546eb3de7e6c7780edbd32d8`** — contexto privado acotado, codec versionado, procedencia e instrucciones, resguardo de preparación y pruebas dedicadas.
- **`b46b4ee5708ef77dab4c851b83ff1618d1ddca0e`** — puertos/entrada explícitos de lectura para aceptación, locks y pruebas PostgreSQL reales; depende del anterior.

Este recibo se entrega en un commit documental posterior que referencia ambos SHA. Coordinación autorizó consumir exclusivamente commits validados mediante cherry-pick, en ese orden. Se enviaron SHA, firma, comandos y resultados directamente a 634 y coordinación; no se copió WIP.

## 3. Constraints

- Sin cambios en jobs/modelos/contabilidad 818, pruebas compartidas coach_jobs/edges, plantillas/vistas/gráficos 630, offline632, bootstrap/coach.py, planning.py, seed/manage, migraciones, lockfiles o workflows.
- La ampliación de athlete/catalog fue autorizada expresamente para el lector de aceptación. La comprobación pequeña de fingerprints en `coach/adapters/provider.py` evita despachar un snapshot v2 con instrucciones diferentes de las registradas; no altera cuotas ni liquidación.
- Solo PostgreSQL exclusivo autorizado: `127.0.0.1:55482/basis_wave3_633`; Django creó/destruyó exclusivamente `test_basis_wave3_633`. Datos y credenciales sintéticos. Sin lectura de archivos de secretos ni credenciales reales.
- `config.test_settings`, `AI_ENABLED=0`. Transporte HTTP únicamente `httpx.MockTransport`; sin HTTP real, IA pagada, pagos, producción, push, PR, CI remoto ni escrituras Linear. Sin agentes adicionales.

## 4. Affected areas y contrato

### Proyección y wire

`training/application/coach.py` añade `CoachScope` y `CoachSessionEvidence`; `TrainingCoachContext.scope/evidence` tienen defaults compatibles. `training/public.py` exporta los tipos necesarios de dominio/aplicación, incluidos Coverage y StageRecovery. No se cruzan ORM ni adaptadores por contratos públicos.

`training/adapters/coach.py` selecciona **14 fechas inclusivas**, desde hoy−13 hasta hoy, **14 sesiones** como máximo, con orden `-date,-created_at,-pk`, y **8 objetivos** por prioridad/PK. Consulta un registro adicional para señalar recorte. Sesiones futuras y anteriores al período quedan fuera; las sesiones en curso siguen identificadas y no aportan totales de completadas. Un Exists privado valida la referencia a prescripción; una referencia administrativa de otra cuenta no sale. El plan base requiere cuenta y objetivo propios.

`report` e `internal_load` siguen siendo los servicios deterministas originales. Se calculan sobre la selección, y después se conserva solo la evidencia necesaria: sesión, fecha, disciplinas, protocolo, operandos/carga, secuencia observada y etapa propia. No se serializan todas las series, intervalos, notas de sesión, contactos ni historial completo. Las notas de etapa son extractos de hasta 300 caracteres; equipo/limitaciones hasta 500. El catálogo habitual conserva su límite existente de 50 ejercicios.

La adherencia queda **no consultada** en este contexto: obtener el calendario efectivo anterior requería una consulta histórica sin límite. `scope.adherence_included=False` y el faltante correspondiente lo indican; el wire v2 omite los tres campos de adherencia. Los ceros internos necesarios para construir el DTO compartido no constituyen observaciones de calendario. Un consumidor debe respetar scope/faltantes y no presentarlos como ceros medidos. La vista/servicio de progreso general no cambian.

`coach/application/context.py` compone exclusivamente puertos públicos por cuenta. Explicita ausencia de objetivos estructurados, disponibilidad, equipo, historial, bienestar y umbrales. No consulta/inventa RM. Descarta del contexto actual bienestar fuera del período o futuro y umbrales con fecha futura. Minimiza bienestar a los campos que el codec consume. Ninguna fecha, pernocta, nota o cero de sueño demuestra recuperación efectiva.

`coach/adapters/context_wire.py` escribe **schema_version=2** para nuevas capturas. Preserva Decimal/fechas/ceros, coberturas e intensidad, scope y referencias. Las coberturas compactas usan el orden declarado `known, missing, not_applicable, unknown_applicability`, comprobado al decodificar. `session_evidence.id` referencia los operandos/fecha/disciplinas ya capturados en `recent_sessions`; el decoder copia esos campos capturados, exige referencia a sesión completada y no recalcula métricas. No duplica cada operando en JSON.

Un snapshot sin versión se interpreta como v1. La recodificación conserva las omisiones históricas de versión, preferencias/bienestar, momento, fuente/tipo de umbral, IDs/estado/prescripción y método. Conserva el método histórico y sus cifras; no vuelve a consultar la DB, recalcular progreso, atribuir un período ni añadir evidencia/coberturas/procedencia que no se capturaron. Se rechazan versiones/tipos incompatibles y decimales no finitos; no se convierten cargas ausentes en cero. La extensión de locks no modifica este codec ni la semántica antigua.

### Instrucciones, proveedor y herramientas

Las nuevas capturas registran `basis-coach-633-v2`, hashes SHA-256 del SYSTEM y, para planes, PLAN_FORMAT, y referencias de los puertos de datos utilizados. Los textos efectivos siguen en `domain/prompts.py`, asociados al SHA de código; los modelos solicitado/reportado y respuesta/uso continúan en los contratos existentes Job/ProviderReply, sin editar 818. El resguardo del proveedor comprueba los hashes/versiones v2 **antes de HTTP**. Una captura incompatible debe revisarse de nuevo; no se sustituye silenciosamente su trazabilidad. En v1 la procedencia de instrucciones no registrada sigue desconocida.

La preparación conserva su separación respecto del envío. El límite previo de request sigue vigente: un contexto rico puede excederlo y se rechaza antes de HTTP; los topes de selección no garantizan que todo conjunto quepa en ese presupuesto. Se verificó también que una proyección real mínima con una sesión cabe como consulta corta. No se modificaron precios, cuotas ni límites de 818.

Los puertos son lecturas autorizadas; no se entregan herramientas arbitrarias al modelo. El esquema existente de propuesta y su validador determinista siguen separando un borrador de su aplicación. Las notas maliciosas permanecen dentro del contenido JSON del mensaje de usuario; no producen mensajes de sistema adicionales. Esto prueba estructura/aislamiento, **no garantiza** que un modelo real obedezca ni que sus recomendaciones sean válidas.

### Entrada bloqueante para 634

```python
Contexts.snapshot_for_acceptance(
    owner: AccountId,
    kind: JobKind,
    base_plan_id: PlanId | None,
    *,
    exercise_ids: tuple[ExerciseId, ...] = (),
) -> CoachContext
```

Requiere `kind='plan'`. El caller mantiene una **UoW abierta y lock_account antes de bloquear la propuesta**; debe pasar todos los IDs de ejercicio referenciados por la PlanDefinition. Los adaptadores rechazan ausencia de transacción con TransactionManagementError; no abren ni confirman una transacción interna. `snapshot()` y `read()` normales siguen sin locks de aceptación. Preferencias ausentes causan CoachInvalid; no se crean defaults para aceptar.

Orden interno: **perfil → preferencias existentes → SportProfile existentes por PK → objetivos proyectados y objetivo de base por PK → plan base propio → ejercicios referenciados por PK**. Los locks permanecen hasta el commit/rollback de la UoW del caller, que debe abarcar comprobación y aplicación.

Se confirmó en código: `DjangoAthleteRecords.save_sport()` toma `lock_profile` antes de insertar/editar; la edición oficial de perfil también lo toma. Esto serializa las inserciones oficiales de deportes. El editor gratuito de preferencias no lo toma: su fila necesita el lock explícito nuevo. `DjangoPlanRepository.save_goal/create` y el anchor de linaje en `training/adapters/locking.py` toman `lock_account`, que el caller ya mantiene antes de estos locks.

`CoachExercises.read_for_acceptance(referenced)` bloquea filas existentes referenciadas y rechaza las ausentes. Retorna el mismo catálogo acotado que read(); **no protege filas no referenciadas ni nuevas inserciones**. La comprobación del guard debe comparar ejercicios referenciados. También debe comparar los datos efectivamente capturados/minimizados; los extractos de 500/300 caracteres no son un fingerprint de todo el texto original.

Estos lectores no implementan el guard de propuesta, no conceden autorización de escritura y no acreditan cierre integral de TOCTOU. Falta validar su uso con la comprobación/aplicación de 634 dentro de la misma UoW. SQL administrativo que omita los anchors oficiales, inserciones arbitrarias y operación multibase quedan fuera de esta garantía.

## 5. Implementation steps

1. Releer ticket/instrucciones/arquitectura/contrato815 y comprobar aislamiento/árbol: realizado antes de editar.
2. Corregir historial sin límite, futuro, minimización y fuentes mediante contratos aditivos: realizado.
3. Añadir versión, compatibilidad legada, faltantes y trazabilidad; contrastar preparación sin HTTP: realizado.
4. Con autorización posterior, acordar firma con 634 y añadir puertos/locks, manteniendo composición ajena: realizado.
5. Validar con pruebas puras, PostgreSQL concurrente real y controles estáticos; revisar diff y crear commits locales acotados: realizado.
6. Entregar recibo/SHA y pendientes LIVE/integración, conservando tickets abiertos: este documento y mensajes a coordinación/634.

## 6. Required skills

Se aplicaron task-planning, safe-git-workflow y verify-before-complete: plan previo específico, límites de propiedad, revisión del árbol/diff y estados sustentados en ejecuciones. No se delegó trabajo.

## 7. Validation — matriz criterio/evidencia

| Criterio | Evidencia ejecutada | Estado/límite |
| --- | --- | --- |
| Perfil autorizado y referencias privadas | dedicated633 comprueba objetivos/sesiones, plan ajeno, enlace administrativo de etapa, prescripción y objetivo ajenos; test_private_access verifica matriz de cuentas/CSRF. | **VERIFIED** PostgreSQL; el owner se suministra por las fronteras autenticadas existentes. |
| Contexto mínimo y faltantes | Pruebas puras y PG de objetivos/prefs/bienestar ausentes, futuro/antigüedad, ceros reales y recortes. Sin RM ni recuperación inferida. | **VERIFIED** proyección y wire; no calidad deportiva. |
| Período y consultas limitados | Hoy incluido, futuro/hoy−14 excluidos; 14 sesiones/8 objetivos con recorte; orden estable; caso poblado usa 4 consultas y LIMIT 15/9 en SQL. | **VERIFIED**; no prueba de capacidad ni límite de detalle dentro de una sesión. |
| Cifras, unidades y referencias deterministas | dedicated633 compara contra report; fuerza 200 kg·rep, carga 50 UA y cero UA, fechas/etapa propias; multisport815/training_contract vuelven a pasar. | **VERIFIED** sintético, sin fórmulas nuevas, sin sumar deportes/protocolos incompatibles. |
| Codec nuevo y antiguo | Roundtrip de contexto v2 completo con datos PG; v1 conserva método, cifras y omisiones; rechazo de versiones/tipos/cargas no finitas/metadata incompatible. | **VERIFIED**; no se migran ni reescriben snapshots persistidos. |
| Inyección desde notas | Perfil/equipo/etapa/request maliciosos dentro de datos; dos roles system/user; SYSTEM sin interpolar esas notas; sesión completa no serializada. | **VERIFIED** estructura; resistencia del modelo LIVE **NOT RUN**. |
| Preparación, errores y esquema | MockTransport prueba cero HTTP al preparar, rechazo por presupuesto/hash, respuesta válida con modelo/uso, 400/401/429, 500, JSON inválido, timeout y contenido no textual. Validador rechaza propuesta incompleta; borrador válido no crea un plan. | **VERIFIED LOCAL_SIMULATED**. Nunca acredita smoke real. |
| Prefs/profile/sport protegidos durante aceptación | Doce pruebas de locks nuevas. El UPDATE oficial gratuito de preferencias espera en AthleteSettings; escrituras oficiales de perfil y deporte edit/insert esperan en el perfil; UPDATE directo de SportProfile también espera. | **VERIFIED** PostgreSQL real: wait_event_type=Lock y pg_blocking_pids(writer) contiene al holder; el statement se comprueba y termina después del commit. |
| Goals/base/catálogo referenciado | UPDATE directo de objetivo proyectado, plan base y ejercicio referenciado espera su fila; ejercicio no referenciado sigue editable; referencia ausente falla. | **VERIFIED** lectores, anchors oficiales revisados; integración guard/aplicación634 **NOT RUN aquí**. |
| UoW y preferencias ausentes | Cada puerto bloqueante falla fuera de atomic; callback rechaza prefs ausentes sin crearlas; snapshot normal permite UPDATE concurrente de prefs. | **VERIFIED** PG, sin atribuir locks a un simple mock/atomic. |
| Regresiones y límites arquitectónicos | Tanda PG89, pure247, mypy y controles detallados abajo; archivos compartidos de jobs/edges ejecutados sin editarlos. | **VERIFIED** commits locales. |
| Dependencias, main y LIVE | Backend815 local; UX630 y guard634 pertenecen a otros dueños; no integración en main en este worktree. | **NOT RUN / pendiente externo**. No cerrar633/815. |

### Entorno y comandos reproducibles

Comprobación ejecutada de versión y `select current_database(), version()`: **Python 3.13.7, Django 5.2.18, PostgreSQL 18.4 x64 Windows, basis_wave3_633**.

```powershell
$python633 = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DJANGO_SECRET_KEY = 'mam633-synthetic-test-only'
$env:DJANGO_DEBUG = '1'
$env:AI_ENABLED = '0'
$env:DEEPSEEK_API_KEY = 'mam633-synthetic-not-a-key'
$env:DATABASE_URL = 'postgresql://basis_wave0@127.0.0.1:55482/basis_wave3_633'

& $python633 manage.py test tests.regression.test_coach_context_locks_633 tests.regression.test_coach_context_633 tests.regression.test_multisport_815 tests.regression.test_training_contract tests.regression.test_private_access tests.regression.test_execution_records basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges --noinput --verbosity 2
& $python633 -m unittest discover -s tests_architecture
& $python633 -m mypy --config-file mypy-core.ini
& $python633 -m mypy --config-file mypy-django.ini
& $python633 scripts/architecture_check.py
& 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/lint-imports.exe'
& $python633 manage.py check
& $python633 manage.py makemigrations --check --dry-run
```

- **VERIFIED:** PostgreSQL **89 pruebas OK, 0 omitidas, 20.562 s**, incluida concurrencia de jobs existente y 12 pruebas nuevas de locks. Creación/destrucción exclusiva de test_basis_wave3_633 observada. Log local ignorado `.cache/mam633-evidence/postgres-focused.log`, SHA-256 `5f936c08feeca9988220718ee107356b31cdd7a604020a6330029918a7c5b4d1`.
- **VERIFIED:** suite pura **247 pruebas OK, 2.985 s**. Log `.cache/mam633-evidence/pure.log`, SHA-256 `4d0214fed9504fb1de05e006630d6317a46c5578d12418b2a3f2a9f1b7c3b1f4`.
- **VERIFIED:** mypy core **132 archivos** y Django **417 archivos**, sin errores; checker de capas/inventario; Import Linter **8 kept / 0 broken**; Django check sin problemas y dry-run de migraciones sin cambios.
- **VERIFIED:** Ruff check y format --check en cada Python cambiado de ambos commits; `git diff --check` y revisión del alcance. Árbol limpio al cerrar cada commit de implementación.
- **FAILED inicial, corregido:** fixture readiness=0, excepción esperada del validador y atributo goal_id del DTO PlanDefinition eran incorrectos; se corrigieron a escala válida/ValidationError/goal. También se corrigieron alias de fecha y tipos de pruebas detectados por mypy. Una primera representación demasiado extensa rebasaba el presupuesto de short con una sesión mínima; se compactó sin ampliar límites y se añadió prueba PG de preparación mínima. Los resultados definitivos anteriores incluyen las correcciones. Una invocación de inspección por `python -c` tuvo quoting inválido en PowerShell; la comprobación de versiones/DB se repitió correctamente por stdin.
- Aviso no bloqueante: no existe staticfiles/ en el worktree. El cliente Django no acredita descarga de assets/JavaScript ni revisión visual.
- **NOT RUN:** suite Django completa, CI35 combinado (coordinación trata el orden de ciclos en planning.py), navegador/UI/dispositivos, lector de pantalla, offline, capacidad, CI remoto, integración/main, proveedor LIVE y evaluación de calidad deportiva. No se usan resultados históricos para acreditarlos.

## 8. Risks y entrega

El resultado local es reproducible y los commits de código están listos para integración autorizada. El recibo no autoriza cambios en main ni demuestra el conjunto final con 634/630/818. 634 debe conectar el callback, pasar todos los ejercicios, mantener los locks/UoW a través de la aplicación y validar su guard en PostgreSQL. La comprobación de datos minimizados y la protección de filas existentes no son un bloqueo global de cualquier escritura administrativa posible.

El smoke real de proveedor permanece **NOT RUN** hasta acceso y autorización concretos. El aislamiento del contexto, un prompt, un esquema y mocks no acreditan precisión deportiva ni ausencia de alucinaciones. MAM-633 continúa abierto y MAM-815 conserva sus gates de presentación/integración.
