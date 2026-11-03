# MAM-815 / BASIS-030 — aceptación local multideporte

Fecha: 2026-11-02. Base padre: `98ea2923f6a675001bc9951f971d8a43759b58a3`.
Resultado: **VERIFIED en servicios y pruebas focales; aceptación completa pendiente de presentación e integración**.
Este recibo pertenece al commit que lo incorpora. No declara Done ni modifica Linear.

## 1. Goal

Completar la proyección de contexto concurrente y verificar los criterios multideporte reutilizando los cálculos de progreso ya integrados.

## 2. Context

Se consultaron el ticket vivo [MAM-815](https://linear.app/mamutsystems/issue/MAM-815/basis-030-carga-concurrente-y-analitica-multideporte-con-procedencia) y sus comentarios (ninguno) en esta sesión. Estado leído: **In Progress**. Su conciliación exige reutilizar MAM-625/819 y verificar recuperación, jornadas consecutivas y ausencia de doble conteo tras MAM-820. Se leyeron `docs/MAM820_VERIFICATION.md`, `docs/PROGRESS_ACCEPTANCE_2026-11-01.md`, README y arquitectura/entradas actuales. Sus pruebas históricas no se atribuyen a este candidato.

No se encontraron AGENTS.md adicionales en el árbol ni en los ancestros comprobados; se aplicaron las instrucciones proporcionadas en la tarea. El árbol inicial estaba limpio.

## 3. Constraints

- Sin plantillas, `public.py`, bootstrap, migraciones, otros módulos ni fórmulas deportivas nuevas. Se informó antes de ampliar los DTO de dominio de progreso.
- Solo datos manuales sintéticos y PostgreSQL autorizado: `127.0.0.1:55482/basis_wave2_815`; Django creó y destruyó exclusivamente `test_basis_wave2_815`.
- Sin lectura de secretos/archivos de credenciales, HTTP real, proveedores, producción, pagos, IA pagada, push, PR, CI remoto ni cambios Linear. El flujo web se ejercitó con el cliente interno de Django.
- Sin agentes adicionales ni operaciones Git destructivas.

## 4. Affected areas

| Archivo | Cambio |
| --- | --- |
| `basis/modules/training/domain/progress.py` | DTO aditivos `StageRecovery`, `SessionContext`, campo opcional de sesión y colección de contexto en `ProgressReport`; secuencia pura de fechas observadas. |
| `basis/modules/training/adapters/progress.py` | Proyecta etapa, notas y pernocta con propiedad compatible; etapas en lote y filtro defensivo de cuenta en resúmenes. Retira el prefetch de intervalos que el cálculo no consume. |
| `basis/modules/training/adapters/progress_wire.py` | Expone procedencia por sesión, operandos/protocolo de carga, método, faltantes y contexto al consumidor web existente. Usa `domain.sports.internal_load`, sin copiar su fórmula. |
| `tests_architecture/test_multisport_815.py` | Cuatro pruebas puras de secuencia, mismo día, huecos, fechas desconocidas y límite del período. |
| `tests/regression/test_multisport_815.py` | Cuatro pruebas PostgreSQL de disciplinas, carga, etapas/intervalos, privacidad, cliente web y consultas. |
| Este recibo | Plan, criterio-evidencia, comandos, resultados y pendientes. |

No fue necesario cambiar `application/progress.py`: `Progress.read` ya valida el rango, consulta únicamente sus sesiones y llama a la regla pura. Se conservan sus puertos y composición. Los argumentos nuevos de los DTO tienen valores predeterminados; consumidores actuales conservan su construcción anterior. El contexto todavía no se incorpora al formato de contexto IA de MAM-633.

## 5. Implementation steps

1. Contrastar ticket, recibos y servicios integrados: realizado.
2. Añadir contexto descriptivo por sesión y proyección privada de notas de etapas: realizado.
3. Verificar disciplinas, fuentes, faltantes y aislamiento con datos sintéticos en PostgreSQL: realizado.
4. Entregar contrato aditivo a UX630, conservar propiedad de plantillas y registrar límites: realizado mediante este recibo; render nuevo pendiente del dueño UX.
5. Revisar diff y crear commit local acotado: el commit portador de este documento contiene exclusivamente los seis archivos listados.

## 6. Required skills

Se aplicaron `task-planning`, `safe-git-workflow` y `verify-before-complete`: inspección previa, alcance explícito, preservación del árbol y resultados ejecutados diferenciados de pendientes.

## 7. Validation — matriz criterio-evidencia

| Criterio | Evidencia actual | Estado y límite |
| --- | --- | --- |
| Volumen específico por disciplina; sin equivalencia kg/metros/deportes | `test_all_disciplines_keep_units_protocols_missingness_and_source_totals`: fuerza 200 kg·rep; cardio 50 m; running 3000 m; ciclismo 20000 m; natación 800 m; hiking 1000 m. No agrega unidades entre disciplinas ni convierte trekking en otro deporte. | **VERIFIED** PostgreSQL. Ejemplo sintético, no medición de atleta real. |
| Carga común minutos × RPE con protocolo consistente | Mismo test: 7 sesiones, carga elapsed 150 UA (4 conocidas/2 faltantes), moving 50 UA (1 conocida). Sesión mixta una vez, bloques repetidos una vez por frecuencia/RPE. `domain.sports.internal_load` sigue siendo el cálculo canónico. | **VERIFIED** PostgreSQL y pruebas existentes de cero/ausencia. UA es descriptiva; no equipara demanda específica de deportes. |
| Recuperación declarada y procedencia | Etapas conservan trip/stage/session, orden, notas y altitud de pernocta. Cero altitud se conserva; vacío/None sigue faltante. `test_web_range_context_is_private_and_wellness_remains_declared` verifica el bienestar existente, sueño cero y privacidad. | **VERIFIED** servicio y vista existente. Nuevas filas de etapa disponibles en contexto; render de esas filas pendiente UX630. No se infiere recuperación efectiva ni se agrega un índice de bienestar. |
| Sesiones concurrentes y jornadas consecutivas | Cuatro pruebas puras nuevas y escenario multideporte PostgreSQL. Fechas distintas ordenadas para la secuencia; sesiones del mismo día comparten conteo. La sesión parcial del día intermedio no establece continuidad. | **VERIFIED** dominio/servicio. Secuencia limitada al período seleccionado; primer día es 1 y no acredita inicio histórico de una racha. No establece horas entre sesiones. Render pendiente UX630. |
| Excluir doble conteo de intervalos y etapas | El intervalo hiking de 1000 m no aumenta el bloque de 1000 m. Dos etapas producen 1000 m conocidos y dos jornadas; ni las etapas ni pernoctas suman otra carga. `test_training_contract` vuelve a contrastar la semana contractual. | **VERIFIED** PostgreSQL. Se consultan fuentes de sesión; intervalos no se usan como otra fuente de totales. |
| Mostrar faltantes y métodos | Vista existente probada para Sin datos/No aplica, RPE cero, protocolo y cobertura; nuevos `load_method`, `load_unit`, `context_method` y operandos por sesión. | **VERIFIED** métodos/faltantes actuales y contrato nuevo. Presentación nueva pendiente UX630; no se atribuye al usuario un render todavía inexistente. |
| Aislamiento entre cuentas | Nuevos tests de cliente web, bienestar, sesiones y enlace de etapa corrupto por SQL administrativo. El resumen de viaje también excluye sesiones de otra cuenta. Tests existentes de progreso/trekking y agenda vuelven a pasar. | **VERIFIED** PostgreSQL. La inconsistencia se crea deliberadamente en el test mediante `QuerySet.update`, no mediante una vía oficial de escritura. |
| Sin ACWR predictor ni diagnóstico | Diff revisado: solo fechas observadas, fuentes, carga canónica y notas declaradas. `context_method` explicita límites; la vista existente conserva su advertencia sobre lesiones/equivalencias. | **VERIFIED** inspección del código de este alcance; no se añade ACWR ni otro predictor. |
| Pruebas pertinentes y aceptación sobre main final | Batería local detallada abajo. | **VERIFIED** candidato local; **NOT RUN** integración en main, candidato combinado con UX630 y CI remoto. No cierra MAM-815. |

### Entorno y comandos ejecutados

Intérprete real: `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`.
Comprobación de versión y `select current_database(), version()` sobre la base autorizada: **Python 3.13.7, Django 5.2.18, PostgreSQL 18.4, basis_wave2_815**.

Todos los comandos Django/mypy usaron entorno del proceso:

```powershell
$python815 = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DJANGO_SECRET_KEY = 'mam815-synthetic-test-only'
$env:DEBUG = '1'
$env:AI_ENABLED = '0'
$env:DATABASE_URL = 'postgresql://basis_wave0@127.0.0.1:55482/basis_wave2_815'

& $python815 manage.py test tests.regression.test_multisport_815 tests.regression.test_training_contract tests.regression.test_trekking_820 basis.bootstrap.tests.test_progress basis.bootstrap.tests.test_progress_periods basis.bootstrap.tests.test_progress_agenda basis.bootstrap.tests.test_wellness --noinput --verbosity 2
& $python815 -m unittest discover -s tests_architecture
& $python815 -m mypy --config-file mypy-core.ini
& $python815 -m mypy --config-file mypy-django.ini
& $python815 scripts/architecture_check.py
& 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/lint-imports.exe'
& $python815 manage.py check
& $python815 manage.py makemigrations --check --dry-run
& $python815 -m ruff check basis/modules/training/domain/progress.py basis/modules/training/adapters/progress.py basis/modules/training/adapters/progress_wire.py tests_architecture/test_multisport_815.py tests/regression/test_multisport_815.py
& $python815 -m ruff format --check basis/modules/training/domain/progress.py basis/modules/training/adapters/progress.py basis/modules/training/adapters/progress_wire.py tests_architecture/test_multisport_815.py tests/regression/test_multisport_815.py
git diff --check
```

- **VERIFIED:** Django PostgreSQL focal, **61 pruebas OK, 0 omitidas, 14.805 s**, incluida `TrekkingConcurrencyTests`. Log local ignorado por Git: `.cache/mam815-evidence/postgres-focused.log`, SHA-256 `88362bdb2272269ff9a9c106d109a7dda5b62b683ea4ac1274fabbd8f79feb3c`. Creación/destrucción de `test_basis_wave2_815` observadas.
- **VERIFIED:** arquitectura, **233 pruebas OK, 3.934 s**; checker de capas/inventario; Import Linter **8 kept, 0 broken**.
- **VERIFIED:** mypy core **131 archivos**, Django **414 archivos**, sin errores.
- **VERIFIED:** Django check sin problemas y makemigrations sin cambios.
- **VERIFIED:** Ruff check y formato en los cinco Python cambiados; `git diff --check`.
- **VERIFIED:** prueba de proyección: cuatro sesiones con etapas/intervalos se obtienen en **3 consultas**. Comprueba consulta en lote, no capacidad de 1000 usuarios, memoria ni latencia.
- **FAILED inicial, corregido:** primer intento de las cuatro pruebas nuevas tuvo un error de test: se accedía a `WellnessData.owner_id`, que no existe en ese DTO. Se corrigió para contrastar fecha/sueño/campos privados; la batería final de 61 pasa. Primer Ruff señaló imports separados y luego formato de una asignación; ambos corregidos, chequeo final OK.
- Aviso observado: falta `staticfiles/` en el worktree. No impidió las pruebas del cliente Django; esas pruebas no verifican descarga de recursos ni JavaScript.
- **NOT RUN:** suite Django completa del repositorio, navegador/JavaScript, revisión visual móvil, lector de pantalla, PWA/offline, carga/capacidad, CI remoto y conjunto final integrado con UX630.
- Proveedores, wearables y GPS quedan fuera del alcance manual de MAM-815; no se ejecutaron HTTP real, pagos ni IA.

## 8. Risks y entrega a UX630/coordinación

`report.context` es una lista en el mismo orden de las sesiones fuente (habitualmente fecha descendente). Cada elemento contiene:

- `session_id`, `date`, `sports` (códigos sin repetir), `protocol`, `duration_seconds`, `reported_rpe`, `internal_load` (Decimal o None).
- `previous_date`: fecha distinta anterior **dentro de la selección**, o None. `days_since_previous`: diferencia de fechas; no es tiempo de descanso. `consecutive_days`: días distintos consecutivos observados hasta esa fecha. `sessions_on_date`: número de sesiones completadas de esa fecha. Dos sesiones del mismo día no implican orden intradía.
- `stage_recovery`: None si no hay etapa propia compatible; si existe, diccionario con `trip_id`, `stage_id`, `order`, `overnight_altitude_m` (Decimal/None) y `recovery_notes` (puede estar vacío). Sus notas deben renderizarse con escape normal de Django.
- `report.context_method`, `report.load_method`, `report.load_unit` explican límites/unidades. UUID y IDs permiten usar los enlaces privados existentes mediante `{% url %}`; la vista continúa aportando `period_start`, `period_end` y `source_sessions`.

La nueva secuencia usa únicamente el período del informe; bienestar, viajes e historial reciente mantienen el alcance que ya explicaba la vista. Ninguna ausencia equivale a cero ni acredita descanso; las notas no son diagnóstico. El reporte sigue materializando las sesiones del rango en memoria, ahora con contexto: este cambio no resuelve límites de escala de MAM-638.

**Pendientes reales para aceptación final:** UX630 presenta las filas nuevas y valida legibilidad/faltantes, escape y enlaces privados; coordinación integra este commit y UX630, revalida el conjunto pertinente y decide el cierre en main. La tarea prohíbe modificar esas plantillas compartidas, hacer push/PR/CI remoto o cambiar Linear; se conserva MAM-815 abierto.
