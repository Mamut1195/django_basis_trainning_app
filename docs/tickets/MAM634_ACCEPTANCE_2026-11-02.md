# MAM-634 / BASIS-020 — aceptación local, 2026-11-02

**Estado actual:** correctivo 633 `47af985` incorporado completo como `5a22481`.
Conjunto local: **205 PG / 0 skips, 257 puras, mypy 133/424**, con los checks y
recorrido descritos al final. Los tres commits 634 originales se conservan.
**Revisiones independientes 633-R2 y 634-R2 PENDING; sin aceptación final
integrada, main, LIVE ni cierre de tickets.** Las secciones previas al seguimiento
final son recibos históricos y no sustituyen esta frontera de evidencia.

## Goal

Completar la validación y revisión local de propuestas versionadas reutilizando
`Proposals` y `CoachPlanning`; no crear un motor deportivo ni cerrar tickets.

## Context

Padre exacto `86024f8094f6dce08575107cc90158092639b4aa`, árbol inicial limpio.
Ticket vivo MAM-634 leído con relaciones y comentarios (ninguno): In Progress,
dependencia MAM-633; descripción y cuatro criterios leídos completos.
Arquitectura: dominio/aplicación puros, adaptadores propios, puertos públicos y
composición explícita. La planificación común ya valida estructura/prescripciones
y crea sucesores sin reescribir ejecuciones; ya existe restauración por versión.

## Constraints

Solo propuestas, su revisión y pruebas nuevas dedicadas. Sin contexto/codec/prompts,
training.public, jobs, modelos, migraciones, progreso, scripts compartidos, Linear
writes, push/PR/CI remoto ni IA/pagos reales. Coordinación autorizó únicamente
el import del guard y su conexión en `bootstrap/coach.py::proposals()`.
`contexts()` y `jobs()` permanecen intactos. No leer secretos.
Python del venv raíz `.venv-win`, `config.test_settings`, clave sintética,
`AI_ENABLED=0`, HTTP externo bloqueado. PostgreSQL exclusivo
`basis_wave3_634` en `127.0.0.1:55482`; solo su `test_basis_wave3_634` es descartable.

## Affected areas

`coach/{domain,application,adapters}/proposals.py`, `proposal_actions.py`,
`adapters/web/{views,forms}.py`, revisión Cotton, pruebas dedicadas en bootstrap y
tests_architecture; este documento. Composición solo con autorización explícita.

## Implementation steps

1. Auditar contratos y reproducir brechas con pruebas dedicadas, sin suites durante ediciones.
2. Validar fuente/contexto por puertos existentes, antes de mostrar y al aplicar.
3. Mostrar comparación, motivo/supuestos y conflictos explícitos; conservar versiones.
4. Probar rollback, reintentos y carreras PostgreSQL; navegador local sintético.
5. Ejecutar checks sobre árbol estable, registrar resultados y commit acotado.

## Required skills

task-planning, safe-git-workflow, verify-before-complete; systematic-debugging
para cada fallo reproducido. Sin agentes adicionales.

## Validation

| Criterio / riesgo | Evidencia prevista | Estado inicial |
| --- | --- | --- |
| Sesión y jerarquía macro/meso/micro; referencias/unidades/resultados | Decoder + preview común; pruebas de integridad | NOT RUN |
| Fuente autorizada, objetivos distintos/poco historial | Contexto congelado y actual; sin proveedor real | NOT RUN |
| Disponibilidad/equipo/perfil cambian tras borrador | Revalidación y bloqueo explícito | NOT RUN |
| Calendario incompatible | Días ISO, fechas y minutos declarados | NOT RUN |
| Comparación, motivos y supuestos antes de aplicar | HTTP y recorrido navegador | NOT RUN |
| Aceptar/editar/descartar/reintentar | Pruebas de conflictos y replay | NOT RUN |
| Versionar/restaurar sin tocar resultados históricos | Planificación existente, evidencia dedicada | NOT RUN |
| Atomicidad | Error después de crear plan revierte propuesta y calendario | NOT RUN |
| Dos aceptaciones concurrentes PG | Un sucesor y mismo resultado idempotente | NOT RUN |
| Tipos/arquitectura/lint/check Django | Comandos del repositorio | NOT RUN |

## Risks

Equipo y limitaciones son texto libre; el catálogo público de coach solo expone
id/nombre. No existe una taxonomía aprobada para inferir compatibilidad deportiva.
Separar checks deterministas de revisión humana de ese texto y no afirmar calidad
del modelo, seguridad deportiva ni aceptación LIVE por fixtures.

## Results históricos — primer candidato, anterior al correctivo P1/P2 de 633

**VERIFIED local, no aceptación final integrada.** MAM-634 y sus dependencias
permanecen abiertos. Coordinación comunicó un posible deadlock en la ruta oficial
de inserción de deporte (perfil → FK cuenta frente a cuenta → perfil en aceptación)
y un defecto de fecha por zona horaria. MAM-633 está reproduciendo/corrigiendo
ambos. Este candidato conserva la evidencia realmente ejecutada, pero requiere el
nuevo SHA validado de 633 y otra ronda integrada antes de aceptación final local.
No se han editado sus contratos ni `DjangoPersonalAuthorization` desde 634.

### Dependencias consumidas con autorización

| Fuente original | Cherry-pick en esta rama | Alcance ajeno a 634 |
| --- | --- | --- |
| `1b61b35c68a5b041546eb3de7e6c7780edbd32d8` | `c688385` | Fuente/contexto MAM-633 |
| `b46b4ee5708ef77dab4c851b83ff1618d1ddca0e` | `72a64a8` | Lecturas bloqueantes MAM-633 |
| `4136170a9efd0efee48dee8b9fa6ac8f911cff2b` | `bc15f23` | Recibo documental MAM-633 |
| `8d0ebcce8f91ab7639bd35862762fac5f6954ca6` | `99c0c828495b365b0aa9edc91715dafe1da3a22d` | Orden determinista de snapshots, PR35 |

El commit propio 634 contiene solo sus diez archivos de implementación/pruebas y
esta matriz. Coordinación integrará las dependencias por separado; no volver a
aplicar estos cherry-picks como si fueran trabajo propio de 634.

### Brechas reproducidas y corrección

La primera ejecución PG dedicada (4 pruebas) dio tres fallos: aceptación de un
objetivo ausente del contexto autorizado, aceptación tras cambiar disponibilidad y
rechazo aceptado sin excepción. Los dos primeros eran brechas reales; el tercero
se corrigió en la expectativa de prueba al confirmar coordinación la semántica
histórica de rechazo como no-op. El rechazo **revisado** ahora informa conflicto;
rechazo legado y replay aceptado siguen sin decodificar contenido histórico ni
revalidar perfil. No se ocultó esa distinción.

El primer mypy Django detectó el callback 633 todavía ausente en esta rama y seis
ajustes locales de identificadores/atributos. Se incorporaron únicamente commits
633 validados y se corrigieron esos usos. La primera ronda ampliada 634 detectó
tres errores de las pruebas nuevas (tipo de excepción de dominio y `None` en POST);
se corrigieron las pruebas. La siguiente ronda dedicada dio 27/27 y las rondas
integradas posteriores dieron 86/86 y, con la dependencia PR35, 97/97.

### Matriz local ejecutada

| Criterio / riesgo | Evidencia ejecutada | Resultado y límite |
| --- | --- | --- |
| Sesión/macro/meso/micro y referencias/unidades/resultados | Decoder y preview común; datos malformados/unidad desconocida/resultados reales rechazados | VERIFIED; sin otro motor deportivo |
| Fuente autorizada | AIJob propio, tipo plan y base coincidente; objetivo y ejercicios incluidos en fuente y contexto actual | VERIFIED; catálogo acotado existente |
| Objetivos distintos y poco historial | Fixtures running/cycling/swimming/hiking; sin ejecuciones ni proveedor | VERIFIED estructural; no acredita adecuación deportiva del modelo |
| Disponibilidad/calendario | Días ISO y suma de totales de bloque declarados frente a minutos de sesión | VERIFIED; duración ausente queda desconocida, no se estima |
| Perfil/equipo/restricciones cambian | Revalidación al crear, revisar y aceptar/editar | VERIFIED de campos capturados; extractos de texto de 500 caracteres |
| Comparación y motivos | Nombre, objetivo, fechas, notas, ciclos y prescripciones antes/después; comparación obligatoria de campos editados | VERIFIED HTTP y navegador sintético |
| Decisiones y conflictos | Firma de revisión vinculada a propuesta/contenido; edición posterior obliga nueva comparación; rechazo stale explícito | VERIFIED; rechazo legado conserva no-op histórico |
| Versiones/restauración | Aceptación v2 y restauración v3 con planificación existente; filas de plan previo/ejecución/bloques idénticas antes/después | VERIFIED sin archivar ni reescribir resultados |
| Atomicidad | Fallo inyectado después de crear plan, en persistencia final de propuesta; rollback de contenido/plan/ciclos/sesiones/bloques; posterior reintento | VERIFIED sobre PG real |
| Concurrencia | Dos aceptaciones del mismo borrador devuelven mismo ID y un sucesor; dos ediciones y aceptar/rechazar no sobrescriben al ganador | VERIFIED sobre dos conexiones PG |
| Locks de guard hasta commit | Pausa de coordinación de prueba en `DjangoCoachPlanning.create`, con snapshot/guard/persistencia reales; UPDATE preferencias oficial y UPDATE catálogo/meta reales esperan | VERIFIED `wait_event_type=Lock` y `pg_blocking_pids` contiene holder; no certifica la inversión de locks P1 pendiente |
| Tipos/arquitectura/lint/Django | Comandos siguientes | VERIFIED en este candidato |

### Transacción y composición

Hay una sola composición de producción de `Proposals`, en
`basis/bootstrap/coach.py::proposals()`. El sink y las acciones HTTP consumen esa
factoría; los otros constructores encontrados son fakes de pruebas puras.
La factoría inyecta `DjangoProposalChecks(contexts().snapshot_for_acceptance)`.

Crear abre la UoW exterior y el guard toma `lock_account`; aceptar/editar/revisar
abren UoW y la autorización comercial toma cuenta antes del `SELECT FOR UPDATE`
de propuesta. El guard confirma la cuenta y llama al snapshot bloqueante con los
IDs de **todos** los sets, ordenados y deduplicados. El lector 633 bloquea perfil,
preferencias existentes, perfiles de deporte, metas/base y catálogo referenciado.
Se compara antes de `planning.create` y los locks adquiridos en la UoW exterior
persisten a través de los savepoints del preview hasta commit/rollback final.
Los replays aceptados y el rechazo no llaman al guard de contexto.

Esta descripción demuestra el orden del lado 634; la ruta inversa de inserción
de deporte comunicada posteriormente por coordinación queda **PENDING** hasta
la corrección y nueva prueba de 633. No se atribuye cierre integral TOCTOU a los
tests de lectura ni a los tres probes integrados ejecutados aquí.

### Comandos y entorno realmente ejecutados

Python: `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`.
Se verificó `SHOW server_version`: **18.4**, y `current_database()`:
**basis_wave3_634**. Django creó/destruyó exclusivamente `test_basis_wave3_634`.
Configuración `config.test_settings`, `DJANGO_SECRET_KEY` sintética, `AI_ENABLED=0`,
`DEEPSEEK_API_KEY` vacía. El wrapper local `.cache/mam634_run.py` fija esas variables
y rechaza conexiones/DNS no loopback antes de cargar Django; no carga `.env`.

```powershell
# Bajo el wrapper de aislamiento descrito; sin cambios de fuente mientras corren.
python .cache/mam634_run.py manage.py test basis.bootstrap.tests.test_mam634_proposals basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_planning tests.regression.test_training_contract tests.regression.test_coach_context_633 tests.regression.test_coach_context_locks_633 --noinput -v 1
python .cache/mam634_run.py -m unittest discover -s tests_architecture
python .cache/mam634_run.py -m mypy --config-file mypy-core.ini
python .cache/mam634_run.py -m mypy --config-file mypy-django.ini
python .cache/mam634_run.py scripts/architecture_check.py
lint-imports
python -m ruff check .
python -m ruff format --check <los nueve Python propios de este commit>
python -m djlint basis/modules/coach/adapters/templates/coach/proposals/review.html --check
python .cache/mam634_run.py manage.py check
python .cache/mam634_run.py manage.py makemigrations --check --dry-run
git diff --check
```

Resultado final del candidato previo a P1/P2: **97 PG, 0 skips, 26.068 s**;
**253 puras**; mypy **133 núcleo / 421 Django**; checker VERIFIED; imports
**8 kept / 0 broken**; Ruff repo y format de 9 Python verdes; djLint sin cambios;
Django check sin hallazgos y migrations sin cambios. Los 27 casos dedicados 634
incluyen seis casos de concurrencia/locks. Logs locales:
`.cache/mam634-pg-validated.log`, `.cache/mam634-pure-final.log` y
`.cache/mam634-validated-files.json` (10 archivos de código/pruebas, sin este recibo).
SHA256 del manifiesto ordenado:
`04cf7c8762da26541415005ed19578819c42b68038c8a0aade12af2626828231`.
Los mensajes 400/409 de pruebas negativas son esperados; el warning por
`staticfiles/` ausente no impidió la carga de recursos por el servidor de desarrollo.

### Navegador

Se siguió `preview_status` → `preview_open` (perfil incognito) →
`preview_navigate`/snapshot/interacciones. Servidor propio en `127.0.0.1:8764`,
base exclusiva 634 y cuenta/objetivos/planes sintéticos. No se usó IA real.
Se inspeccionaron escritorio **1280×800** y viewport **390×844 CSS px**; este
último es emulación, no dispositivo real. `scrollWidth` fue igual a `innerWidth`
en ambos. Se editó nombre, se comparó 1800 s → 1500 s y se aceptó la versión 2;
se comprobó la página del plan resultante. Una propuesta malformada mostró 0
campos de edición/ningún botón aceptar y pudo descartarse sin tocar calendario.
En móvil se detectó y corrigió el contenedor fijo de tres acciones que tapaba el
descarte; el contenedor final usa el flujo normal sin modificar CSS compartido.
Recursos observados: todos loopback, sin errores de consola en las capturas.

Capturas inspeccionadas (artefactos locales del navegador T3):

- Escritorio final: `browser-screenshot-127-0-0-1-mw01zeeb-0c7f83f0.png`.
- Móvil final, tres botones completos: `browser-screenshot-127-0-0-1-mw01x5pd-3deacae4.png`.
- Propuesta inválida: `browser-screenshot-127-0-0-1-mw01y1ei-d3d145da.png`.

Se encuentran en `C:/Users/Jonnathan/.t3/userdata/browser-artifacts/`.

### Límites y pendientes explícitos

- **PENDING** nuevo SHA 633 y revalidación de P1 (inversión cuenta/perfil) y P2
  (fecha local del propietario); no aceptación final integrada de este candidato.
- Equipo/limitaciones son extractos de 500 caracteres; objetivos textuales también
  están minimizados por el lector. No se detectan cambios fuera de lo capturado.
  Comparar texto no demuestra compatibilidad, seguridad ni interpretación clínica.
- Se bloquean referencias existentes del catálogo. No se certifican inserciones ni
  cambios a filas no referenciadas, ni SQL arbitrario que eluda las rutas oficiales.
- Duración total ausente sigue desconocida; no se inventa duración con distancias,
  repeticiones o intensidad ni se suman intervalos de nuevo sobre totales de bloque.
- Una taxonomía de equipo/limitaciones o nuevas reglas deportivas requieren decisión
  de producto; no se implementan por inferencia en esta entrega.
- **NOT RUN** suite global de todo el repositorio por este executor, CI remoto,
  proveedor IA/pagos LIVE, dispositivos reales, lector de pantalla, producción y
  aceptación humana. **NOT RUN** integración a padre/main y cierre de tickets.

## Seguimiento 634 — procedencia de RM, posterior a ef6e5ee

Se conserva sin reescribir `ef6e5eedb18f0bdef474e98d7e57bee707905b80`, candidato
anterior con las verificaciones y gates P1/P2 descritos arriba.

**Hallazgo propio del executor 634**, no una ejecución de coordinación: el probe
PostgreSQL `.cache/mam634_rm_source_probe.py` creó un borrador con `rm_reference`
de una RM existente y propia más `target_percent_rm=70`, aunque el snapshot declara
`strength_rm_not_consulted` y no contiene ninguna proyección de RM autorizadas.
Ambas ejecuciones del probe se revirtieron explícitamente; no dejaron calendario
ni registros de ese atleta de prueba. La validación común de propiedad de una RM
no sustituye la procedencia del contexto enviado al proveedor.

Coordinación aprobó el guard y una regresión dedicados. `validate_context` rechaza
ahora la presencia de `rm_reference` **o** `target_percent_rm` con `is not None`:
cero también es presencia. Este contrato de coach no proporciona RM consultadas;
no se agregaron tipos/campos, lecturas de RM, fórmulas ni reglas deportivas. La
planificación manual mantiene sus servicios existentes. `None` conserva ausencia.

La regresión previa al fix (5 tests y subcasos) falló en creación, sink, revisión
y edición; los subcasos porcentaje aislado/cero alcanzaban errores del validador
común en lugar de la negativa de procedencia esperada. Tras el guard, la creación
desde sink no expone propuesta, revisión HTTP no muestra campos, aceptación y
edición rechazan antes de persistir, y estado/contenido/calendario no quedan
parcialmente guardados. También se verifica que prescripciones sin RM se aplican.

```powershell
python .cache/mam634_run.py manage.py test basis.bootstrap.tests.test_mam634_rm_provenance basis.bootstrap.tests.test_mam634_proposals --noinput -v 1
python .cache/mam634_run.py -m unittest discover -s tests_architecture
python .cache/mam634_run.py -m mypy --config-file mypy-core.ini
python .cache/mam634_run.py -m mypy --config-file mypy-django.ini
python .cache/mam634_run.py scripts/architecture_check.py
lint-imports
python -m ruff check .
python -m ruff format --check basis/modules/coach/domain/proposals.py basis/bootstrap/tests/test_mam634_rm_provenance.py tests_architecture/test_mam634_proposals.py
git diff --check
```

**VERIFIED local:** 32 PG / 0 skips / 8.869 s, 254 puras, mypy 133/422, checker,
imports 8/0 y Ruff check/format. Un error inicial de invariancia de `dict` en el
helper nuevo se corrigió con `Mapping`; tipos y focal PG se repitieron verdes.
Logs: `.cache/mam634-rm-before.log`, `.cache/mam634-rm-validated.log`,
`.cache/mam634-rm-pure.log`; manifiesto de esos tres archivos de código/prueba en
`.cache/mam634-rm-validated-files.json`. **P1/P2 de 633 y aceptación integrada
siguen PENDING.** Esta corrección de procedencia no acredita calidad del modelo,
seguridad deportiva, IA LIVE ni cierre de MAM-634 o sus dependencias.

## Seguimiento 634 — respuesta a revisión independiente de ef6e5ee

Se atendieron los tres hallazgos P2 del reviewer sobre `ef6e5ee`: RM en el commit
separado `a4254d689ce7c3049df2ead7b06b09826d5a040c`; frontera numérica y estado
visible en este seguimiento. El dictamen independiente usó reproducciones en
memoria, sin PostgreSQL ni navegador; las pruebas siguientes son del executor 634.

- **NaN/finitud:** la nueva regresión PG reprodujo una excepción decimal no
  controlada en sink/revisión/aceptación. Se amplió a NaN, sNaN, ±Infinity y
  exponentes extremos ±1E9999999; el caso extremo también reprodujo Overflow.
  El guard ahora llama a **`training.public.validate_sport_metrics`** para cada
  target de bloque antes de sumar/comparar. Se reutiliza la regla vigente de
  finitud/rangos y se traduce `InvalidSportMetrics` a `CoachInvalid`; no se añadió
  una fórmula, regla deportiva ni excepción amplia en jobs/worker.
- **Estado oculto:** una cancelación realizada mediante `Planning.change_session`
  producía una comparación sin diferencias frente a una propuesta programada.
  Ahora se muestra `Estado: Cancelada / Omitida / Programada` por sesión. La
  regresión verifica Cancelada → Programada, que el texto difiere y que revisar
  todavía no crea un sucesor. La prueba numérica adicional conserva duración cero
  como cero, sin convertirla en dato faltante.

Reproducción anterior: 4 tests, 1 fallo de estado y 5 errores numéricos (incluye
subcasos), `.cache/mam634-review-before.log`. Después: **36 PG / 0 skips /
13.331 s**, 255 puras, mypy 133/423, checker/imports 8/0, Ruff check repo y format
de los cuatro Python afectados verdes. Comandos de la misma configuración aislada:

```powershell
python .cache/mam634_run.py manage.py test basis.bootstrap.tests.test_mam634_review_regressions basis.bootstrap.tests.test_mam634_rm_provenance basis.bootstrap.tests.test_mam634_proposals --noinput -v 1
python .cache/mam634_run.py -m unittest discover -s tests_architecture
python .cache/mam634_run.py -m mypy --config-file mypy-core.ini
python .cache/mam634_run.py -m mypy --config-file mypy-django.ini
python .cache/mam634_run.py scripts/architecture_check.py
lint-imports
python -m ruff check .
python -m ruff format --check basis/modules/coach/domain/proposals.py basis/modules/coach/adapters/proposal_actions.py basis/bootstrap/tests/test_mam634_review_regressions.py tests_architecture/test_mam634_proposals.py
git diff --check
```

Logs: `.cache/mam634-review-after.log` y `.cache/mam634-review-pure.log`.
Se repitió el recorrido T3 en 1280×800 y 390×844, sobre servidor propio reiniciado
y datos sintéticos: la comparación muestra Cancelada → Programada sin marca
«sin cambios» para esa fila; `scrollWidth == innerWidth`. Capturas inspeccionadas:
`browser-screenshot-127-0-0-1-mw02qmq4-a2d6c309.png` y
`browser-screenshot-127-0-0-1-mw02qwsp-843173ed.png`, en el mismo directorio T3
indicado arriba. No se aceptó esta propuesta de demostración ni se llamó al
proveedor. **P1/P2 de 633 y aceptación integrada continúan PENDING.**

## Conjunto local con el correctivo 633 — pendiente dictámenes R2

Se incorporó **únicamente el commit completo validado**
`47af9855197a972dd901975e316bace83489e3ce`, como
`5a22481364a30c9068d0d8e0b0cfc83bb1f4cc6d`; no se editaron sus archivos desde
634. Los commits propios preservados son `ef6e5ee`, `a4254d6` y `056b06f`.
La dependencia alinea autorización personal atómica con cuenta → perfil y deriva
la fecha del propietario de un único instante con su zona. Sus firmas y codec
histórico permanecen intactos. Ver el recibo de 633 para la reproducción RED
anterior de los ciclos/40P01; aquí no se vuelve a atribuir esa reproducción al
executor 634.

La prueba propia del escritor oficial de preferencias se adaptó al nuevo contrato:
su primera sentencia contenciosa es ahora `SELECT ... FROM auth_user ... FOR UPDATE`.
Se añadió un escritor directo de `AthleteSettings.availability` para demostrar que
el guard **también retiene la fila de preferencias** desde el chequeo hasta el
commit real del plan. Se conserva la observación real `Lock` y la relación con el
backend holder mediante `pg_blocking_pids`; no se sustituye por sleeps o mocks.
Los otros probes integrados de catálogo/meta y las carreras de decisiones siguen
verificando el camino guard → `planning.create` → persistencia → commit/replay.

Comando integrado, ejecutado con árbol de código estable y el mismo aislamiento:

```powershell
python .cache/mam634_run.py manage.py test basis.bootstrap.tests.test_mam634_proposals basis.bootstrap.tests.test_mam634_rm_provenance basis.bootstrap.tests.test_mam634_review_regressions tests.regression.test_coach_context_review_633 tests.regression.test_coach_context_locks_633 tests.regression.test_coach_context_633 tests.regression.test_multisport_815 tests.regression.test_training_contract tests.regression.test_private_access tests.regression.test_execution_records tests.regression.test_profile_onboarding basis.bootstrap.tests.test_identity basis.bootstrap.tests.test_wellness basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_planning --noinput --verbosity 2
```

**VERIFIED por el executor 634:** **205 tests PG / 0 skips / 76.845 s**, que incluyen
37 propios 634, 157 de la selección 633 y 11 de planificación. Los ocho órdenes de
escritores oficiales registran `cycle_observed=false`, SQLSTATE nulo y contención
inicial en cuenta. Se ejecutaron además las pruebas Tokyo/Honolulu, rango temporal,
DST, permisos gratuitos y autocommit del correctivo. Ningún test usó proveedor
real; creación/destrucción exclusiva de `test_basis_wave3_634`.

Checks repetidos en este conjunto: **257 puras**, mypy **133 núcleo / 424 Django**,
checker VERIFIED, imports **8 kept / 0 broken**, Ruff repo, Django check sin
hallazgos y `makemigrations --check --dry-run` sin cambios. Los comandos de puras,
tipos, arquitectura y lint son los ya registrados arriba. Logs locales:
`.cache/mam634-integrated-after-633.log` y `.cache/mam634-integrated-pure.log`.

El servidor propio se reinició con el conjunto corregido y se repitió el recorrido
T3 incognito de revisión/confirmación/aceptación en 390×844. La comparación mostró
Cancelada → Programada y aceptar creó **versión 4** del plan sintético en
`/plans/28/`, conservando la navegación a versiones 1–3. Se verificó
`scrollWidth=390`, `innerWidth=390` y recursos externos observados vacíos. Este
recorrido posterior sí aceptó la propuesta sintética del seguimiento anterior;
no acredita dispositivo físico ni proveedor LIVE.

Los correctivos solicitados están incorporados y los checks locales pasan, pero
**633-R2 y 634-R2 siguen PENDING** a esta captura. No se declara aceptación final
integrada ni aprobación independiente por ejecutar las pruebas del autor.
