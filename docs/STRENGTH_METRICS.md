# BASIS-003 / MAM-619: métricas de fuerza

Contrato de esta implementación: `legacy-strength-v3`. El servicio puro
`daily_trainning_app.strength_metrics.calculate_strength_metrics` no consulta BD,
no infiere esfuerzo y devuelve `Decimal` o `None`. `WorkoutData.clean()` lo usa;
`save()` ejecuta validación de modelo. Los formularios reales del admin, el inline,
la API y los guardados ordinarios comparten estas reglas. Las dos properties de
`StrengthSet` usan el mismo servicio y conservan sus condiciones de aplicabilidad.

## Unidades y método

| Resultado | Método y unidad | No aplica / dato ausente |
| --- | --- | --- |
| `total_reps` | series × repeticiones; conteo | Un factor cero produce cero; entradas ausentes o inválidas se rechazan en legacy. |
| `carga` | repeticiones totales × kg externos; kg·repetición | Cero es una carga externa registrada. No es carga interna ni una equivalencia de cargas corporales/asistidas. |
| `intensidad_relativa` | kg / RM medido de referencia × 100; % | Sin RM positivo fechado: `None` en servicio/API. |
| `volumen_relativo` | repeticiones totales × porcentaje sin redondeo intermedio; repeticiones·puntos porcentuales | Sin referencia: `None`. No es porcentaje ni carga en kg. |
| `rm_sesion` / `estimated_1rm` | Epley: kg × (30 + reps) / 30; kg estimados. Una repetición devuelve los kg levantados. | Solo carga positiva, 1..10 reps y RPE **observado** 10. Sin series realizadas: no aplica. En serie detallada, además requiere `kind=work` y `load_type=external`. |

Las salidas decimales se cuantizan a `0.01` con `ROUND_HALF_UP`, precisión local
40, independientemente del modo de redondeo del llamador. Se calcula volumen
relativo antes de redondear el porcentaje: 3×5×80 con RM 120 produce 1000.00,
no 1000.05. Ejemplos: 3×5×80 = 1200.00 kg·rep; editar a 40 = 600.00;
3×5×80.25 = 1203.75; Epley de 80.25×5 a RPE real 10 = 93.63 kg.
Con series, repeticiones o peso cero se limpian carga, intensidad y volumen;
e1RM no aplica. El conteo de repeticiones sigue siendo series × reps, incluso
con kg cero.

## Esfuerzo observado, objetivo y limitación legacy

`rpe_objetivo` es prescripción, `rpe_real` es observación opcional (0..10).
El objetivo no genera RPE real ni e1RM. Un RPE observado 0 se conserva como
0; ausencia se conserva como `None`. No se estima RPE desde %RM, fatiga del
ejercicio o repeticiones. El admin y el inline permiten registrar ambos campos;
los derivados, la referencia y la versión no se pueden editar en el admin.

`WorkoutData` es un agregado de series homogéneas con una sola carga y un
solo RPE real: no permite identificar qué serie fue máxima, descansos, tipo de
serie ni tipo de carga. Su e1RM es una estimación limitada a esa declaración
agregada; no prueba que todas las series se realizaran al máximo. No representa
carga corporal/asistida como kg externos ni reconstruye series históricas.
`StrengthSet` ya separa objetivos/resultados RPE y RIR por serie; RIR 0 y RIR
ausente son distintos. Esta versión no convierte RIR a RPE ni activa Epley solo
por RIR 0; exige RPE observado 10. No se añaden campos de RIR al agregado.

## Referencia histórica

Al calcular por primera vez se selecciona un RM positivo del mismo atleta y
ejercicio, con fecha ≤ entrenamiento. Se ordena por fecha descendente y después
PK descendente: ante empate gana el registro con mayor PK, no el mayor peso.
La fecha carece de hora; esta es una convención determinista, no prueba de orden
intradiario de medición. Un RM futuro nunca se aplica al pasado.

Una vez persistida la referencia, editar peso/repeticiones/esfuerzo conserva
ese FK aunque aparezca un RM retroactivo del mismo día. **La ausencia también
es snapshot**: `legacy-strength-v3` y la versión preexistente `legacy-volume-v2`
con FK nulo permanecen sin referencia. Vaciar un FK histórico existente lo
restaura; sustituirlo dentro del mismo contexto se rechaza. Cambiar atleta,
ejercicio o fecha constituye otro contexto y selecciona referencia compatible.
Una referencia explícita ajena, de otro ejercicio o futura se rechaza en modelo.
La API rechaza cualquier entrada `rm_referencia` (incluso nula) y la asigna en
servidor. Los RM son mediciones inmutables: una nueva medición requiere otra fila.

`legacy-unverified` significa que no hay evidencia de cálculo con estas reglas.
Leerlo no recalcula ni modifica datos. Solo una edición explícita calcula la fila
con v3 y, si no había referencia, selecciona una compatible. No se ejecuta una
migración de datos ni se convierte el antiguo RPE objetivo en observación.

## Compatibilidad y persistencia

No hay cambios de esquema ni migraciones nuevas. `rm_sesion`, intensidad y
volumen mantienen sus campos `FloatField(default=0)` por compatibilidad. Solo
la frontera de almacenamiento convierte el Decimal final a float; cero puede
ser un sentinel legacy de ausencia/no aplicabilidad, no una observación.
La API devuelve `null` para e1RM no aplicable, intensidad/volumen sin referencia
positiva y esos tres derivados de versiones anteriores a v3. `metrics_version`
permite reconocer el método. Las lecturas conservan intactos los valores
históricos almacenados. El objetivo legacy por defecto 0 sigue siendo ambiguo;
no se afirma que sea una prescripción declarada. Los helpers de consulta RM
devuelven `None` cuando no hay dato; el helper desde entrenamientos evalúa la
última fila hasta la fecha, no busca la mejor estimación de todo el historial.

En `save(update_fields=...)`, los derivados se calculan con el estado persistido
más los campos solicitados. Los atributos modificados y excluidos no influyen
ni se guardan; pueden seguir pendientes en memoria hasta `refresh_from_db()`.
En RM se aplica la misma composición antes de validar inmutabilidad.
`update_fields=[]` no guarda. Formularios incompletos producen errores de campo,
sin multiplicaciones sobre `None`. Los errores de modelo se traducen a HTTP 400.
El cálculo rechaza `total_reps > 2147483647` (rango portable de PositiveInteger)
y `carga > 999999999999.99` kg·rep (Decimal 14,2). `clean()` valida también los
campos derivados después de asignarlos: el orden normal de `full_clean()` no
valida automáticamente esas asignaciones. Los errores de derivados se presentan
como errores generales, porque esos campos son readonly en formularios. POST y
PATCH con overflow devuelven 400 antes de escribir: no queda creación parcial
ni se altera el entrenamiento previo.

`QuerySet.update()`, `bulk_create()`, `bulk_update()` y SQL directo omiten las
reglas de `save()` de Django: no están certificados como vías de escritura de
métricas. Esta entrega no incorpora bloqueo para escrituras simultáneas ni
certifica PostgreSQL compartido; la integración corresponde al coordinador.

## Incertidumbre y evidencia

Epley es una estimación aritmética, no una medición de RM, evaluación clínica,
prescripción de carga ni validación de seguridad. Técnica, ejercicio, rango de
movimiento, exactitud de la carga y del esfuerzo declarado afectan su utilidad.
El redondeo explícito aporta reproducibilidad, no precisión fisiológica.

`training.tests.test_strength_metrics` cubre cálculo puro, Decimal fraccionario,
límites e1RM, equivalencia agregado/serie, cero/ausencia, create/update_fields,
historial legado, RM futuro/empates/snapshots, HTTP POST/PATCH e inyección RM.
También obtiene ModelForms y formsets del registro real `admin.site._registry`
para validar registro, edición, esfuerzo ausente, entradas incompletas e
inmutabilidad de RM. Las pruebas usan settings de test y SQLite aislado; no son
evidencia de pruebas clínicas, navegación visual ni cierre global del ticket.
