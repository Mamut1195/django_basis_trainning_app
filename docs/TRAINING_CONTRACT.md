# BASIS-005 / MAM-618 — contrato deportivo ejecutable

Versión del documento y fixture: `basis-005-v1`. Alcance: describir la implementación
inspeccionada y ejecutar un ejemplo sintético, sin modificar dominio, modelos,
servicios ni [TRAINING_VARIABLES.md](TRAINING_VARIABLES.md). Este contrato permite
revisión e integración del nodo BASIS-005; no declara cerrado el producto, la
evaluación deportiva LIVE ni otros tickets.

## Población, propiedad y autoridad

Atletas autónomos adultos con cuentas independientes. No hay relación entrenador,
equipo ni permiso compartido implícito. `Owned.owner` vincula objetivos, planes,
prescripciones, ejecuciones y viajes a la cuenta; los hijos heredan la propiedad
del padre. Catálogo `Exercise` compartido no significa historial compartido.
Los tests rechazan importar un objetivo, empezar una prescripción, sincronizar una
ejecución, revisar un plan o reprogramar una sesión de otra cuenta.

La mayoría de edad se declara en `SignupForm.adult` y se valida al editar edad
en `AthleteForm` (18–120). El modelo legado `User.edad` permite edades menores
y ausencia de edad: **no existe una restricción adulta global de base de datos**.
`AthleteSettings` registra disponibilidad ISO 1–7, minutos, equipo, limitaciones
y zona horaria; estos datos no constituyen un optimizador ni comprueban que cada
sesión cumpla esa disponibilidad. `SportProfile` distingue experiencia por deporte
y umbral opcional con unidad, fecha y método. No se inventa un umbral ausente.

Autoridad para revisar este contrato:

| Fuente local | Responsabilidad comprobable |
|---|---|
| `training/domain.py` | Seis deportes, claves/unidades, normalización y funciones métricas. |
| `training/models.py` | Relaciones, validaciones, campos observados y estimadores. |
| `training/proposals.py` | Construcción/validación transaccional y aceptación explícita de propuestas. |
| `training/services.py` | Inicio, sincronización, revisión, informes y agregación de etapas. |
| `training/views.py::scheduled_reschedule` | Cambio manual de fecha con revisión y validación del microciclo. |
| [Variables aprobadas](TRAINING_VARIABLES.md) | Alcance deportivo y fuentes primarias ya disponibles. |
| [Fixture](fixtures/training_week.json) y [test](../training/tests/test_training_contract.py) | Ejemplo reproducible y resultados esperados independientes de las consultas del informe. |

## Jerarquía y separación entre intención y observación

```text
cuenta → Goal → TrainingPlan (lineage/version/previous)
                    └─ Cycle macro → meso → micro
                                             └─ PlannedSession (fecha/revision)
                                                  ├─ Block de prescripción → StrengthSet o Interval
                                                  └─ Session de ejecución (UUID/revision)
                                                       └─ Block de ejecución → StrengthSet o Interval
cuenta → TrekTrip → TrekStage ordenada → Session con al menos un Block hiking
```

`Goal` declara deporte, prioridad, valor/unidad, fecha objetivo y línea base opcional
con fecha; no representa una métrica calculada ni exige que todo el plan tenga su
deporte. El ejemplo tiene objetivo hiking y preparación multideportiva. La unidad
del objetivo es texto, no un catálogo dimensional validado por deporte.

El plan contiene sus ciclos y fechas. Macro carece de padre; meso exige macro y
micro exige meso del mismo plan. Fechas de hijos contenidas en padre y plan.
Una prescripción debe estar en un microciclo y dentro de sus fechas. No se impone
una duración deportiva universal a cada nivel ni se cubren automáticamente todos
los días del plan. El fixture define macro de cuatro semanas, meso de dos y solo
un micro detallado de siete días; no fabrica sesiones para el resto del macro.

Un `Block` tiene exactamente un padre: prescripción **o** ejecución. En la
prescripción `target` y campos `target_*` son intención; `actual` y resultados de
series/intervalos deben estar vacíos. `start_session` copia la intención a otra
estructura y deja resultados desconocidos. Una sesión puede mezclar deportes.
Series requieren strength; intervalos requieren un deporte distinto de strength.
Orden de bloques/filas sigue el orden de la lista en `save_blocks`.

`build_plan` recibe un objetivo propio, fechas ISO, ciclos con `key`/`parent` y
sesiones con `cycle_key`. Admite 3–100 ciclos y 1–14 sesiones, hasta 366 días de
intervalo de fechas. `save_blocks` admite 1–30 bloques y hasta 100 series y 100
intervalos por bloque. No son recomendaciones de volumen deportivo.
`validate_proposal` ejecuta la construcción y revierte la transacción.
`accept_proposal` exige acceso de escritura, acepta una propuesta pendiente y
rechaza una base con sucesor; una propuesta ya aceptada devuelve su plan.
El test usa `build_plan` directamente: no solicita ni evalúa un proveedor IA,
ni crea una falsa propuesta generada o un trabajo facturable.

## Variables, unidades y procedencia

| Deporte/registro | Intención y datos reales admitidos; límites |
|---|---|
| strength | Ejercicio y variante de catálogo; carga `external`/`bodyweight`/`assisted`; kg, repeticiones fijas o rango, descanso s, RPE 0–10, RIR, tempo, ROM, lado, isometría s y grupo. `target`/`actual` JSON no admiten métricas de fuerza: se usan las series. |
| cardio | Duración transcurrida s, distancia m, FC medida lpm, tipo/superficie e intervalos. |
| running | Lo anterior más ascenso/descenso m y cadencia medida pasos/min. Ritmo derivable en s/km. |
| cycling | Duración s, distancia/desnivel m, entorno indoor/outdoor; potencia W y cadencia rpm solo si registradas. La velocidad no genera potencia. |
| swimming | Duración s, distancia m, estilo, piscina m, largos, brazadas y técnica; ritmo s/100 m. Sin inferencia automática de distancia desde largos. |
| hiking | Distancia m; tiempo transcurrido/movimiento/pausas s; ascenso/descenso y altitudes m; mochila kg decimal; terreno/equipo. Dificultad solo con escala, grado y fuente juntos. |
| trekking | No es séptimo deporte: agrupa ejecuciones hiking en `TrekTrip`/`TrekStage`, orden y fechas coherentes, altitud de pernocta m y notas de recuperación. |
| bienestar | `Wellness`: sueño h/calidad, fatiga/estrés/molestias/disposición, dolor con región, FC reposo y HRV ms opcional con método. Sin adaptación automática ni diagnóstico. |

Los campos JSON numéricos se normalizan como cadenas decimales. Ausencia, `null`
y cadena vacía se omiten al validar; significan desconocido, no cero. Un cero
explícito se conserva (`ascent_m: 0` en ciclismo). Los campos numéricos de modelos
usan `None` cuando faltan; la escala decimal serializada puede cambiar al recargar
(`"5"`/`"5.0"` son el mismo RPE). Distancias y tiempos objetivo no rellenan resultados.

El dominio comprueba rangos, números finitos y unidades/claves admitidas, rechaza
booleanos como números, incoherencias movimiento + pausas > tiempo transcurrido,
altitud máxima menor que inicio/final y FC media mayor que máxima. La presencia
de datos no verifica su exactitud instrumental ni fuerza igualdad movimiento +
pausas = transcurrido. Tampoco comprueba que las sumas de intervalos igualen al bloque.

La procedencia del fixture es **sintética/manual**, declarada en `provenance`.
No son resultados recibidos de personas o dispositivos. `SportProfile` conserva
método y fecha del umbral, y `%RM` exige una referencia `UserExerciseRM` propia,
del mismo ejercicio y no futura. No calcula automáticamente kg o RPE desde `%RM`.
La referencia RM histórica tiene protección frente a edición de sus valores.
Fuera de esos campos, los modelos no tienen un esquema universal de dispositivo,
calibración, autor, incertidumbre o versión de fórmula por observación: se requieren
notas/procedencia externa, sin presentarlas como controles implementados.

## Estados persistidos y lecturas derivadas

| Lectura del contrato | Representación existente |
|---|---|
| Planificada / pendiente | `PlannedSession` sin ejecución completada. No hay columna `status` en la prescripción. |
| Parcial | `Session.status="in_progress"` con algunos resultados; parcial es descripción del ejemplo, no tercer estado. |
| Completada | `Session.status="completed"`. No exige cumplir objetivos ni rellenar todas las mediciones. |
| Omitida (lectura humana) | Fecha pasada sin ejecución; permanece sin ejecución y entra como programada pendiente en adherencia cuando corresponde a la versión vigente/histórica. No existe `omitted`, transición automática, motivo de omisión ni contador persistido de omisiones. |
| Reprogramada | Fecha/revisión de prescripción cambiadas manualmente; no es un estado ni un enlace explícito entre sesiones versionadas. |
| Evaluada | Lectura del informe y revisión humana; no hay entidad ni estado `evaluated`, ni evaluación automática de un objetivo. |

`progress_report` cuenta prescripciones con fecha **hasta hoy inclusive**: no se
debe llamar omitida a una sesión de hoy solo por no tener ejecución. Usa
prescripciones con ejecución completada, de planes sin sucesor, o con fecha
anterior al día `created_at` de su sucesor. Cuenta prescripciones distintas y las
que tienen al menos una ejecución completada. Incluye pendientes/parciales elegibles
en el denominador; solo completadas en el numerador. No es porcentaje de repeticiones,
distancia realizada ni logro del objetivo. Sin denominador devuelve `None`.

## Versionado, conservación y reprogramación reales

`TrainingPlan.lineage` se mantiene; `version` aumenta y `previous` apunta al anterior.
Solo hay un sucesor por plan. `revise_plan` copia todos los ciclos y exclusivamente
prescripciones desde hoy sin **ninguna** ejecución. Conserva las prescripciones
originales, las ejecuciones pasadas y las parciales vinculadas al plan original.
No mueve fechas, cancela copias antiguas ni enlaza cada copia con su original.

El ejemplo revisa el jueves 15 y reprograma **la copia nueva** de ciclismo al
viernes 16 mediante el endpoint existente. Este valida propietario, ausencia de
ejecuciones, revisión optimista y pertenencia temporal al microciclo; aumenta
`PlannedSession.revision`. No permite ese cambio si ya hay ejecución. La revisión
del plan no es igual a la revisión de la prescripción ni a `Session.revision`.

`sync_session` reemplaza hijos solo durante ejecución en curso, dentro de una
transacción; exige revisión actual e identifica mutaciones para reintentos.
Una ejecución completada rechaza edición por este servicio mediante `Conflict`.
Estas garantías de servicio no convierten todo el ORM en inmutable: escrituras
directas pueden alterar planes/sesiones. `start_session` reutiliza una ejecución
en curso, pero puede crear otra si solo hay completadas; no existe unicidad global
de una ejecución por prescripción. El informe deportivo cuenta ejecuciones y la
adherencia prescripciones distintas: no se promete deduplicación de ejecuciones
repetidas. El endpoint de reprogramación tampoco bloquea por sí solo todo plan
con sucesor. El test certifica la ruta descrita, no todos los posibles historiales
de copias/reprogramaciones ni concurrencia de producción.

## Semana completa: intención, observación y revisión

Atleta adulta recreativa ya familiarizada con estas actividades. La combinación
es un ejemplo revisable de registro, no una dosis prescrita para toda persona.
Fechas fijas y reloj controlado en tests; zona `America/Guayaquil`.

| Jornada | Prescripción v1 | Observación y lectura al terminar la semana |
|---|---|---|
| Lunes 12/10 | Fuerza técnica (40 min de contexto, pausas incluidas): calentamiento 8×10 kg; trabajo 2×8 y 1×6–8 a 25 kg, descanso 120 s; 8 repeticiones corporales. Elíptica 15 min. | Completada, 55 min transcurridos, RPE de sesión 5. Trabajo 3×8×25 kg; calentamiento 80 kg·rep; total externo 680 kg·rep. La serie corporal no añade kg externos. Cardio sin distancia conocida. |
| Martes 13/10 | Running cómodo 4.000 m/1.800 s; 2 intervalos de 2.000 m/900 s, descanso 60 s. | Parcial guardada: 2.500 m/1.200 s; un detalle de intervalo 2.000 m/900 s, RPE de sesión desconocido. Sigue `in_progress`; no entra en totales de completadas. |
| Miércoles 14/10 | Natación técnica 800 m/1.200 s; piscina 25 m, 32 largos; 4×200 m y descansos 60 s. | Sin ejecución. El jueves ya es pasada: “omitida” en lectura humana, pendiente en datos. No suma 800 m de natación realizada. |
| Jueves 15/10 | Ciclismo indoor fácil, 1.800 s/10.000 m. | Revisión humana por disponibilidad; v2 conserva pasado y copia ciclismo y las dos etapas. Se traslada la copia de ciclismo al viernes. Jueves queda sin sesión ejecutada/descanso; no se crea ejecución cero. |
| Viernes 16/10 | Descanso en v1 (día sin prescripción). | Recibe ciclismo de v2 y se completa: 1.800 s/10.000 m, ascenso registrado 0; potencia, cadencia y RPE desconocidos. No hay carga interna conocida para esta sesión. |
| Sábado 17/10 | Hiking etapa 1: 8.000 m; 10.800 s total, 9.000 movimiento, 1.800 pausas; +350/−150 m; altitudes 1.800/2.050/2.000 m; mochila 5,5 kg. | Completada con esos valores; RPE 4 sobre tiempo total. Etapa 1 de viaje, pernocta 2.000 m y recuperación en notas. Detalles 2×4.000 m no se añaden de nuevo al bloque. |
| Domingo 18/10 | Hiking etapa 2: 6.000 m; 9.000 s total, 7.200 movimiento, 1.800 pausas; +150/−350 m; altitudes 2.000/2.050/1.800 m; mochila 5,5 kg. | Completada; RPE 4 sobre tiempo **activo** de sesión (7.200 s). Etapa 2, pernocta desconocida. El bloque conserva 9.000 s transcurridos; los dos protocolos no se suman como la misma carga. |

Hay siete jornadas explícitas en `days` y seis prescripciones iniciales. Descanso
es ausencia intencional de prescripción/ejecución, no deporte ni estado nuevo.
El traslado deja seis prescripciones efectivas en la semana, aunque se conservan
nueve filas históricas de prescripción entre v1 y v2.

El test alternativo finaliza el mismo running parcial con 3.000 m/1.500 s y RPE 5:
estado completed aun por debajo de 4.000 m objetivo; ritmo 500 s/km y carga 125 UA.
No se combina esa alternativa con los totales del escenario principal. El fixture
incluye resultados completos por bloque/fila para los registros ejecutados;
natación deliberadamente carece de resultado. Las repeticiones del intervalo son
prescritas: no hay campo de conteo separado de repeticiones realmente completadas;
por eso los bloques siguen siendo autoridad para sus totales reales.

## Evaluación reproducible y límites de los estimadores

| Punto de evaluación principal | Resultado esperado del servicio |
|---|---|
| Jueves antes de revisar | 4 programadas hasta hoy; 1 completada; adherencia 25 %. |
| Tras clonar v2 sin mover fecha | Sigue 4/1; no duplica el ciclismo de hoy. |
| Tras mover ciclismo al viernes | 3 programadas hasta hoy; 1 completada; 33,3 %. No borra la natación pendiente ni el running parcial. |
| Domingo | 6 programadas; 4 completadas; 66,7 %. 4 ejecuciones completadas y 1 parcial persistida. |
| Deportes completados | strength: 680 kg·rep; cardio: distancia desconocida; cycling: 10.000 m y ascenso 0; hiking: 14.000 m y ascenso 500 m. Running parcial y swimming pendiente excluidos. |
| Carga de tiempo total | 995 UA conocidas: lunes 55×5 = 275 y sábado 180×4 = 720; 2 conocidas y 1 ausente (ciclismo). |
| Carga de tiempo activo | 480 UA: domingo 120×4; 1 conocida, ninguna ausente en ese protocolo. |
| Viaje | 2 etapas completadas; 14.000 m, +500/−500 m, 19.800 s transcurridos y 16.200 s activos. No genera una tercera sesión ni otra carga. |

Los totales de distancia/desnivel provienen únicamente de `Block.actual` de
ejecuciones completadas; no se añaden prescripciones, intervalos o viaje. Una
sesión mixta cuenta una vez globalmente y una vez dentro de cada deporte presente;
sumar sus contadores deportivos duplicaría esa sesión. El reporte no publica un
total de distancia entre deportes. Ni metros nadados, de bicicleta o a pie, ni
kg·rep de fuerza son datos equivalentes para evaluar el objetivo hiking.

Volumen externo es `actual_kg × actual_reps` para carga external, incluidas series
de calentamiento que tengan ambos datos. El nombre de propiedad/campo del reporte
es `external_volume_kg`; la magnitud es **kg·repetición**, no masa levantada única ni
trabajo mecánico en joules. Cargas corporales/asistidas y valores ausentes retornan
`None`. El total conocido no garantiza cobertura de todas las series/mediciones.
Los informes suman valores presentes; salvo carga interna no exponen todos los
conteos de faltantes, así que un subtotal conocido no prueba registro completo.

`StrengthSet.estimated_1rm` implementa la variante Epley documentada en variables:
solo carga externa, serie work, 1–10 repeticiones, kg positivos y `actual_rpe == 10`.
Con una repetición devuelve la carga; con 2–10 calcula kg×(30+reps)/30 y redondea
a 0,01 kg con `ROUND_HALF_UP`. El test aislado usa 25 kg×8 con esfuerzo 10 declarado
y verifica 31,67 kg **estimados**. En la semana principal no se declara esfuerzo
máximo y no se obtiene 1RM. No se transforma la estimación en referencia medida ni
se presupone exactitud individual. El algoritmo no guarda versión de fórmula por
serie; su procedencia aquí es el código y esta versión documental.

`pace_seconds` usa tiempo/distancia positiva, redondeado a dos decimales, por 1.000 m
en running y por 100 m en natación; sin entradas conocidas devuelve `None`.
No certifica calidad del desplazamiento ni homogeneidad de tramos.

`Session.load` aplica `internal_load`: duración de sesión/60 × RPE **reportado de
sesión**, cuantizado a 0,01 UA solo cuando completed. No toma RPE de intervalos o
series, `%RM`, FC ni datos objetivo para rellenarlo. `progress_report.method`
declara `session-rpe-v1`; separa protocolos elapsed y moving. Puede sumar cargas
numéricas conocidas dentro de un protocolo, sin afirmar equivalencia fisiológica
entre modalidades ni validación individual. No se suman las filas de carga de
distintos protocolos. Desconocido no es cero: ciclismo incrementa `missing`.

La evaluación humana del goal compara la etapa del sábado (8.000 m registrados)
con su meta de 8.000 m y referencia manual de 6.000 m, bajo las limitaciones de
comparabilidad de esos registros. No es una evaluación calculada del servicio ni
prueba de mejora causal o adaptación. La revisión humana consulta además el
running incompleto y la natación pendiente en sus registros: el informe agregado
no lista esos resultados; solo incluye sus prescripciones elegibles en el
denominador. No los reprograma automáticamente ni interpreta una puntuación como lesión.

## Fuentes y calidad deportiva pendiente LIVE

Se reutiliza [TRAINING_VARIABLES.md](TRAINING_VARIABLES.md#referencias-de-alcance)
como inventario de fuentes primarias ya aprobadas: Foster/session-RPE, consenso
sobre seguimiento de cargas, límites del ACWR, SAC y UIAA. Este documento describe
el código y el contrato aprobado; no añade afirmaciones clínicas ni investigación
médica nueva. No calcula riesgo de lesión con ACWR, mochila universal segura,
grado de dificultad, diagnóstico, RPE desde `%RM` ni sensores inexistentes.

Separar aceptación técnica de calidad deportiva:

| Criterio | Evidencia que aporta este contrato | Pendiente LIVE / gap |
|---|---|---|
| Propiedad, jerarquía y resultados | Construcción/validación real, rechazo de cruces de cuentas y de resultados en prescripción. | Auditoría completa de todos los accesos y restricciones frente a ORM directo. |
| Semana, cambios y adherencia | Siete días; parcial y completada; pendiente pasada; nueva versión y endpoint de fecha; pasado intacto. | Otros historiales, cambios entre microciclos, ejecución repetida y concurrencia PostgreSQL. |
| Métricas y estimadores | Unidades y valores esperados, no duplicación, cero/faltante y protocolos separados. | Procedencia instrumental, cobertura completa y validez individual de estimadores. |
| Programación y adaptación | Ejemplo sintético revisable con razón humana de cambio. | Idoneidad individual, progresión, recuperación, objetivos, síntomas y respuesta a datos incompletos; revisión deportiva y evaluación LIVE de IA con rúbrica separada. |

El test no acredita calidad de recomendaciones IA, operación de proveedores,
cobros, correo, despliegue, migración de datos reales, capacidad multiusuario bajo
carga ni validación clínica. No cambia gates de otros nodos.

## Reproducción aislada

Desde la raíz, en PowerShell, sin leer `.env` ni credenciales. Se fuerza configuración
de pruebas, SQLite con nombres UUID dentro de `.cache` y clave pública exclusiva
de pruebas para evitar leer el secreto local. `DATABASE_URL` vacío impide heredar
PostgreSQL compartido. El runner usa un archivo de test distinto del nombre base;
ninguno apunta a `db.sqlite3` original. Los únicos cambios fuente son estos tres
archivos; `.cache` y cachés de Python son artefactos locales de verificación.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'basis_trainning_app.test_settings'
$env:DJANGO_DEBUG = '1'
$env:DJANGO_SECRET_KEY = 'basis005-contract-tests-only-public-placeholder'
$env:DATABASE_URL = ''
$env:BASIS_DATABASE_PATH = '.cache/basis005-contract-' + [guid]::NewGuid().ToString('N') + '.sqlite3'
New-Item -ItemType Directory -Force -Path .cache | Out-Null
@'
from pathlib import Path
from django.conf import settings
from django.core.management import execute_from_command_line

database = settings.DATABASES['default']
assert database['ENGINE'] == 'django.db.backends.sqlite3'
path = Path(database['NAME']).resolve()
assert path.parent == (Path.cwd() / '.cache').resolve()
assert path.name.startswith('basis005-contract-')
database.setdefault('TEST', {})['NAME'] = str(path.with_name('test_' + path.name))
print('Exclusive SQLite:', database['TEST']['NAME'], flush=True)
execute_from_command_line(['manage.py', 'test', 'training.tests.test_training_contract', '--noinput', '--verbosity=2'])
'@ | & .venv-win/Scripts/python.exe -
.venv-win/Scripts/python.exe -m ruff check training/tests/test_training_contract.py
.venv-win/Scripts/python.exe -m ruff format --check training/tests/test_training_contract.py
```

El JSON es un escenario, **no** un fixture para `loaddata` ni una API de producción.
El test sustituye referencias simbólicas de ejercicios por PK creadas en la base
exclusiva e inyecta el `goal_id` propio antes de llamar servicios existentes; usa
cuenta adulta, correo verificado y derecho de escritura ficticio de las factories
locales. No activa suscripción ni realiza llamadas externas. El reloj se fija en
cada jornada, incluida la creación de versiones, para reproducir la consulta de
adherencia basada en `created_at`.

### Registro de verificación de esta entrega

| Comprobación | Estado y alcance |
|---|---|
| Tests del contrato | **VERIFIED**: 6 tests, SQLite exclusiva `test_basis005-contract-d8533b0e1f964f4ca4801bfda31847e7.sqlite3` dentro de `.cache`; migraciones y system check correctos. El runner destruyó su base de test. |
| Lint/formato | **VERIFIED**: `ruff check` y `ruff format --check` sobre el nuevo test. |
| Archivos fuente y revisión de alcance | **VERIFIED**: solo se escribieron los tres archivos asignados; comprobación de existencia, JSON y espacios finales. El worktree conserva cambios preexistentes y concurrentes ajenos. |
| Suite completa / PostgreSQL / integración main | **NOT RUN** por este implementador; corresponde al coordinador. |
| Calidad deportiva LIVE y servicios externos | **NOT RUN**; este escenario no aporta esa evidencia ni cierra sus gates. |
| Build / estáticos | **NOT APPLICABLE** al cambio de documentación, fixture y test. |
