# Motor de cálculo y reglas del entrenador

**Estado:** implementado como funciones puras con pruebas (2026-11-04). Pendiente de
conectarlo al contexto del entrenador (MAM-1025 y MAM-1026).

- Métricas: `basis/modules/training/domain/analysis.py`
- Reglas: `basis/modules/coach/domain/decisions.py`
- Pruebas: `tests_architecture/test_training_analysis.py` (13) y
  `tests_architecture/test_coach_decisions.py` (16).

## Principios

1. **Los números los calcula el código.** El modelo recibe resultados, no hace aritmética.
2. **Lo desconocido no es cero.** Un dato ausente vuelve `None` y se informa como cobertura.
3. **No se suman deportes ni protocolos.** Hiking `elapsed` y ciclismo `elapsed` son cargas
   distintas; se comparan por separado.
4. **La regla explica.** Cada hallazgo lleva motivo, evidencia numérica y propuesta.
5. **Nada se aplica solo.** Un cambio es una propuesta hasta que la persona lo acepta.

## Fórmulas

### Carga de sesión

`minutos × RPE de sesión` (Foster et al. 2001). Ya existía en `sports.internal_load`.

### Carga semanal

Suma de cargas conocidas por semana ISO, separada por deporte y protocolo. Las sesiones sin
RPE se cuentan en `missing` y no aportan carga.

### Base y ratio

- Base: media de las últimas 4 semanas con al menos 3 semanas con dato.
- Ratio: `semana actual / base`.
- El ratio es **descriptivo**. No predice lesiones ni se usa como umbral médico
  (Impellizzeri et al. 2020).

### Monotonía y strain

- Monotonía: media de carga diaria / desviación estándar poblacional de 7 días.
  Los días de descanso son ceros reales; un día con sesión sin RPE es desconocido y anula
  el valor.
- Strain: `carga semanal × monotonía`.

### Tendencia

Pendiente por mínimos cuadrados sobre puntos `(fecha, valor)`, expresada por semana. Con
menos de 3 puntos devuelve `None`.

### 1RM estimado

`peso × (1 + (repeticiones + RIR) / 30)` (Epley con repeticiones en reserva; Zourdos et al.
2016). Requiere 1–12 repeticiones y 0–10 RIR. Es una **estimación**, nunca un máximo medido;
hereda el error del RIR reportado. Las ecuaciones de predicción tienen error conocido
(LeSuer et al. 1997).

### Volumen por músculo

- Cada serie cuenta una vez por cada músculo principal del ejercicio.
- `kg·rep` solo con carga `external`, peso y repeticiones conocidos.
- Una serie sin esos datos cuenta como serie y como `missing` de kg·rep; no se convierte en 0.

### Adherencia

`completadas / elegibles × 100`. Canceladas y fechas futuras no cuentan. Sin elegibles, el
porcentaje es `None`.

### Brechas musculares

Músculos con cero series registradas en todas las semanas consultadas. El llamador decide
cuántas semanas pasar; no se inventan semanas sin datos.

## Reglas de decisión

Los umbrales viven en `Thresholds` y son **política del producto**, no leyes universales.

| Regla | Dispara cuando | Propuesta |
| --- | --- | --- |
| `pain_stop` | Hay dolor o síntomas reportados | Detener y pedir valoración profesional |
| `load_spike` | 2 semanas seguidas > 120 % de la base | −20 % de volumen en accesorios |
| `high_rpe_low_load` | RPE ≥ 8 y carga < 80 % de la base | Revisar recuperación, no añadir carga |
| `load_drop` | 2 semanas seguidas < 80 % de la base | No subir; recuperar continuidad |
| `adherence_low` | Adherencia < 60 % | Simplificar el plan |
| `plateau_low_effort` | 3 sesiones sin mejorar 1RM y RPE ≤ 7 | +1 serie o +2,5 % de carga |
| `plateau_high_effort` | 3 sesiones sin mejorar 1RM y RPE > 7 | Revisar recuperación antes de cargar |
| `muscle_gap` | 0 series en un grupo durante ≥ 2 semanas | Elegir un ejercicio de la biblioteca |
| `missing_rpe` | Hay sesiones sin RPE | Preguntar antes de proponer cambios |

Cada hallazgo incluye `rule`, `severity` (`info` / `warn` / `stop`), título, motivo, evidencia
numérica y propuesta.

## Qué no hace

- No diagnostica ni programa rehabilitación.
- No predice lesiones ni usa ACWR como predictor.
- No rellena RPE, peso, repeticiones ni duración.
- No suma deportes ni mezcla `elapsed` con `moving`.
- No decide por su cuenta: propone.

## Ejemplo

Semana 45: 720 UA. Base de 4 semanas: 500 UA. Ratio 1,44 durante 2 semanas.

- `load_spike`: «Llevas 2 semanas por encima del 120 % de tu media reciente».
- Evidencia: «Hace 1 semana: 1,440x», «Hace 2 semanas: 1,300x».
- Propuesta: «Bajar un 20 % del volumen en accesorios y mantener los ejercicios principales».
- El modelo solo explica y prioriza; la persona acepta o descarta.

## Referencias

- Foster C, et al. A new approach to monitoring exercise training. *J Strength Cond Res*.
  2001. https://pubmed.ncbi.nlm.nih.gov/11708692/
- Session-RPE: validez y límites. https://pubmed.ncbi.nlm.nih.gov/29163016/
- Impellizzeri FM, et al. Training load and injury prevention, part 2: conceptual and
  methodologic pitfalls. *J Athl Train*. 2020. https://pubmed.ncbi.nlm.nih.gov/32991699/
- Zourdos MC, et al. RIR-based RPE scale. *J Strength Cond Res*. 2016.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4961270/
- Schoenfeld BJ, et al. Dose-response of weekly resistance training volume. *J Sports Sci*.
  2017. https://pubmed.ncbi.nlm.nih.gov/27433992/
- LeSuer DA, et al. Accuracy of 1RM prediction equations. *J Strength Cond Res*. 1997.
  https://www.mendeley.com/catalogue/5e186f30-ab23-376b-9ca8-9c46d9d49e82/
- Ratamess NA, et al. ACSM progression models in resistance training. *Med Sci Sports
  Exerc*. 2009. https://pubmed.ncbi.nlm.nih.gov/19204579/

## Biblioteca de ejercicios

`seed_exercise_library` crea 66 ejercicios en la clasificación **Fuerza**, sin duplicar ni
renombrar los existentes (`--dry-run` para revisar).

- 12 grupos: pecho, espalda, hombros, bíceps, tríceps, antebrazo, abdomen, cuádriceps,
  isquiotibiales, glúteos, gemelos y aductores. Al menos 3 ejercicios por grupo.
- 12 patrones: empuje horizontal/vertical, tracción horizontal/vertical, sentadilla,
  bisagra, core anti-extensión/anti-rotación/flexión, acarreo, aislamiento y gemelo.
- Equipo declarado y nivel de fatiga (Bajo/Medio/Alto).
- Vocabulario canónico en `basis/modules/catalog/adapters/management/commands/seed_exercise_library.py`.

Cargado en staging el 2026-11-04: 66 creados, 0 duplicados. Pruebas:
`basis/bootstrap/tests/test_exercise_library.py` (4).

## Herramientas del entrenador

El modelo no consulta la base ni calcula: pide una herramienta con argumentos tipados y
recibe un resultado con unidades y cobertura.

| Herramienta | Argumentos | Devuelve |
| --- | --- | --- |
| `get_load_trend` | `sport`, `protocol`, `weeks` (1–12) | Carga por semana ISO de ese deporte y protocolo |
| `get_load_summary` | `sport`, `protocol` | Semana actual, base de 3 de 4 semanas y ratio |
| `get_adherence` | — | Elegibles, completadas y porcentaje |
| `get_missing_rpe` | — | Sesiones sin RPE (nunca cero) |
| `estimate_1rm` | `weight_kg`, `reps` (1–12), `rir` (0–10) | 1RM estimado en kg |

Contrato:

- Nombre, argumentos y tipos se validan antes de leer datos; desconocido o fuera de rango se
  rechaza.
- Cada resultado es `{tool, ok, data, units, coverage, notes}` y los decimales viajan como
  texto para no perder precisión.
- Sin datos devuelve `ok: false` o `baseline: null` con una nota; nunca inventa.
- El `Toolbox` recibe muestras ya acotadas por cuenta; no accede a la base.

Pruebas: `tests_architecture/test_coach_tools.py` (14, incluidas las de esquema).

**Límite actual:** el contexto del entrenador lee solo 14 días, así que
`get_load_summary` suele responder "faltan semanas" para una base de 4. MAM-1026 debe
ampliar la ventana del contexto (con su prueba de privacidad y tamaño) antes de que la
regla `load_spike` pueda dispararse en producción.

## Diagnóstico en la pantalla del Entrenador

`basis/bootstrap/diagnosis.py` lee **35 días** de sesiones completadas, arma muestras de un
solo deporte y protocolo, y llama a `diagnose` (`basis/modules/coach/application/diagnosis.py`).

- Elige el deporte/protocolo con más sesiones; nunca mezcla deportes.
- Excluye sesiones de varios deportes y lo dice en las notas.
- Calcula carga semanal, base de 3 de 4 semanas y ratio; ejecuta las reglas.
- Si faltan semanas, lo informa y no inventa una base.
- La ventana de 35 días es independiente del contexto del proveedor, que sigue en 14 días
  para no inflar el prompt.

Visible en `/coach/` como tarjeta **Diagnóstico de tu entrenamiento**, antes del formulario.
Pruebas: `tests_architecture/test_coach_diagnosis.py` (7).

Ejemplo real en staging: “Carga por encima de tu base · Llevas 2 semanas por encima del
120 % · 1.622x y 1.440x · Bajar un 20 % del volumen en accesorios”. La misma pantalla
mostró “4 sesiones sin RPE” y la propuesta de preguntar antes de cambiar cargas.

## Siguiente

1. **MAM-1025**: exponer estas funciones como herramientas con esquema.
2. **MAM-1026**: incluir los hallazgos en el contexto del entrenador y validar la propuesta.
3. **MAM-1027**: casos de decisión en el corpus de evaluación.
