# MAM-813 — verificación de ciclismo manual

## Alcance y auditoría reutilizada

Continuación **solo documental**, 2026-10-23. Snapshot Systems:
`8471fcaed1ac1cee0895968b42239345a75066f561ac2e2cb03a0e6fbf642676`.
La ejecución local de once gates comunicada y firmada por el coordinador corresponde
al candidato fuente `446c261ed1875db950984a93b4daeac05197b9382b503fdcac2d5a2b713f8764`,
posteriormente registrado en el commit `fdc8198`. No se han ejecutado gates en esta
continuación. **Esta documentación cambia el candidato e invalida los bindings
anteriores: el coordinador debe renovar los gates finales tras esta escritura.**

La auditoría previa de MAM-811 se reutiliza, no se reimplementa:
[ENDURANCE_VERIFICATION.md](ENDURANCE_VERIFICATION.md) y
`tests/regression/test_endurance.py` ya cubren el diccionario deportivo compartido,
validación de unidades/rangos, ausencia frente a cero, referencias privadas,
snapshots históricos y copia de objetivos/intervalos. Su evidencia histórica de
PostgreSQL y revisión no constituye evidencia nueva ni aprobación de MAM-813.
Se conservan dominio, persistencia, formularios y contratos existentes de
`basis/modules`; no se duplican umbrales ni flujos de entrenamiento.

El único cambio de producto es la etiqueta de opciones en `MetricsForm`, en
`basis/modules/training/adapters/web/forms.py`: **Interior / Exterior**, manteniendo
los valores wire **`indoor` / `outdoor`** y «Sin registrar». Se añadieron **seis tests
Django HTTP/ORM y cuatro tests puros** específicos de ciclismo. Sin migraciones,
fórmulas, conversiones, cambios de política de umbrales ni de API pública.
El alcance es manual: sin GPS, importaciones ni wearables.

## Contrato y trazabilidad de aceptación

En las filas siguientes, **VERIFIED** significa cobertura local ejecutada sobre el
candidato fuente por el coordinador, no aceptación ni revisión independiente.
Los nombres se dan completos respecto a la clase/archivo indicados:

- **D** = `tests/regression/test_cycling.py::CyclingTests` (seis tests nuevos).
- **P** = `tests_architecture/test_cycling.py::CyclingDomainTests` (cuatro nuevos).
- **E** = `tests/regression/test_endurance.py::EnduranceTests` (reutilizados,
  incluidos en la suite Django global; no son tests nuevos de esta entrega).

| Criterio / alcance | Prueba exacta y archivo mediante las claves anteriores | Estado |
|---|---|---|
| AC1: no inferir potencia ni umbral desde velocidad, distancia o duración; ausencia sigue desconocida incluso al iniciar | D.`test_distance_duration_never_infer_power_or_threshold_even_after_start`; P.`test_distance_duration_are_not_power_cadence_or_heart_rate` | VERIFIED |
| AC2: unidades explícitas W, rpm, lpm; opciones españolas sin cambiar wire | D.`test_form_units_spanish_labels_and_unchanged_wire_values`; D.`test_manual_http_create_optional_unknown_then_measured_zero` | VERIFIED |
| Ciclismo interior/exterior, duración, distancia, ascenso/descenso, FC/potencia/cadencia medidas e intervalos en flujo web | D.`test_manual_http_create_optional_unknown_then_measured_zero`; D.`test_http_lifecycle_preserves_targets_intervals_and_frozen_provenance` | VERIFIED |
| AC3: prescripción y resultados separados en bloque/intervalo al iniciar, editar y completar; objetivos y descanso originales conservados | D.`test_http_lifecycle_preserves_targets_intervals_and_frozen_provenance`; P.`test_interval_actual_zero_does_not_change_prescribed_target_or_rest` | VERIFIED |
| Opcionales: null/vacío no son cero; el cero medido se conserva en HTTP y sync | D.`test_manual_http_create_optional_unknown_then_measured_zero`; D.`test_optional_null_and_zero_in_sync_remain_distinct`; E.`test_dictionary_every_numeric_boundary_missing_zero_and_units` | VERIFIED |
| Umbral: valor/unidad/fecha/método/tipo/fuente guardados; procedencia congelada y referencia ausente no inventada | D.`test_http_lifecycle_preserves_targets_intervals_and_frozen_provenance`; D.`test_distance_duration_never_infer_power_or_threshold_even_after_start`; E.`test_threshold_units_dates_values_and_provenance`; E.`test_absent_reference_stays_unknown_after_profile_created` | VERIFIED |
| Aislamiento: crear/leer/escribir/exportar solo datos propios; POST con owner inyectado no cambia propietario; sync ajeno no modifica estado | D.`test_foreign_reads_posts_sync_and_export_cannot_access_cycling`; D.`test_manual_http_create_optional_unknown_then_measured_zero`; P.`test_foreign_owner_reads_and_writes_roll_back_with_permissive_port` | VERIFIED |
| Validación de disciplina, unidades, límites y opciones; cobertura unitaria/de dominio | P.`test_cycling_rejects_foreign_units_nonfinite_and_invalid_choices`; E.`test_incompatible_discipline_variable_and_pause_without_movement` | VERIFIED |
| Comandos/resultados reales; LIVE/dispositivos explícitamente no ejecutados | Once gates y límites documentados abajo | VERIFIED (documentación; LIVE NOT RUN) |

Ausencia/null/vacío opcional se normaliza como dato desconocido (clave ausente en
métricas, snapshot `null`), **no** como cero. Un cero explícito permanece cero,
incluidos potencia, cadencia, FC, descanso y RPE real. Distancia/duración no generan
potencia, FC, cadencia ni umbral; una potencia objetivo explícita de intervalo no es
una medición ni una referencia de umbral.

Los umbrales reutilizan validación de valor positivo, unidad compatible, fecha no
futura, método, tipo medido/estimado y fuente. El snapshot conserva identidad,
deporte, valor, unidad, fecha, método, tipo y fuente al prescribir/iniciar. Editar
luego el perfil no reinterpreta el historial ni rellena resultados. `target` y
`actual` permanecen separados tanto en bloques como en intervalos; completar por
sync no altera objetivos ni procedencia. La edición posterior al cierre se rechaza.

Las lecturas y los POST de recursos ajenos devuelven **404** (incluido el endpoint
privado de snapshot). Sync ajeno devuelve **400** con
`{"detail": ["La sesión no está disponible."]}`, no 404: es su contrato existente,
no una relajación del aislamiento. No se persiste el ataque y la exportación de la
otra cuenta excluye la referencia privada. Los tests puros usan dobles de puertos
permisivos para comprobar autorización/rollback; no prueban operación real externa.

## Entorno y once gates del snapshot

**VERIFIED según instalación/ejecución del coordinador:** Windows, Python
**3.13.7**, Django **5.2.18**, venv propia `.venv-win` instalada con **uv** conforme
al brief local. No se instala ni descarga nada en esta continuación. `pytest` no
está declarado/configurado: **NOT RUN**; se usan runners nativos unittest/Django.

Los comandos siguientes reproducen exactamente el ejecutable y los argumentos de
los once gates congelados (sintaxis PowerShell; `$py` es el ejecutable absoluto).
Entorno aislado común del snapshot, sin proveedores ni credenciales reales:

```powershell
$py = 'C:/Users/Jonnathan/Mamut system/basis-wt/MAM-813/.venv-win/Scripts/python.exe'
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:BASIS_DATABASE_PATH = '.cache/mam813-isolated-tests.sqlite3'
$env:DJANGO_SECRET_KEY = 'mam813-public-isolated-test-key-not-a-secret'
$env:DJANGO_DEBUG = '1'
$env:AI_ENABLED = '0'
$env:BASIS_DEVELOPMENT_ACCESS = '0'
$env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:DEEPSEEK_API_KEY = ''
$env:EMAIL_HOST_PASSWORD = ''
$env:EMAIL_HOST_USER = ''
$env:POLAR_ACCESS_TOKEN = ''
$env:POLAR_ORGANIZATION_ID = ''
$env:POLAR_PRODUCT_ID = ''
$env:POLAR_WEBHOOK_SECRET = ''

# cycling
& $py -B manage.py test tests.regression.test_cycling --noinput --verbosity 2
# pure
& $py -B -m unittest discover -s tests_architecture -v
# regression
& $py -B manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput
# ruff
& $py -B -m ruff check .
# format
& $py -B -m ruff format --check basis/modules/training/adapters/web/forms.py tests/regression/test_cycling.py tests_architecture/test_cycling.py
# mypy-core
& $py -B -m mypy --config-file mypy-core.ini
# mypy-django
& $py -B -m mypy --config-file mypy-django.ini
# architecture
& $py -B scripts/architecture_check.py
# imports
& $py -B -c 'from importlinter.cli import lint_imports; lint_imports()'
# django-check
& $py -B manage.py check
# migration-drift
& $py -B manage.py makemigrations --check --dry-run
```

| Gate | Resultado local firmado comunicado por el coordinador (candidato fuente) |
|---|---|
| cycling | PASS: 6 tests, 0 skips |
| pure | PASS: 195 tests (incluidos los 4 nuevos puros) |
| regression | PASS: 465 totales, 403 pasados y 62 skips por SQLite; incluye los 6 de ciclismo, no se suman dos veces |
| ruff | PASS |
| format | PASS: 3 archivos |
| mypy-core | PASS: 120 archivos |
| mypy-django | PASS: 367 archivos |
| architecture | PASS |
| imports | PASS: 8 contratos conservados, 0 rotos |
| django-check | PASS: 0 incidencias |
| migration-drift | PASS: 0 cambios de migración |

Fuente de estos resultados: reporte externo derivado de gates firmados
`basis-runs/MAM813-20261023-cycling-v1/coordinator-gates-1792768209230.json`,
proporcionado por el coordinador; no se accedió al almacén de control desde esta
continuación. No se atribuye esta ejecución al redactor del documento.

Historial, no resultado final: el primer entorno con `DATABASE_URL=''` seleccionó
el backend dummy y falló por falta de ENGINE. Se corrigió **solo el entorno del
gate** a `sqlite:///:memory:`, sin tocar settings del producto. Hubo fallos previos
de formato y mypy en los tests (anotaciones precisas de argumentos int/UUID y texto
de aserción), y una expectativa equivocada de 404 para sync ajeno; se corrigieron
antes de la ejecución completa. Los fallos históricos no se presentan como PASS ni
como defectos pendientes; no se debilitaron contratos ni configuraciones de tipos.

## Límites y pendientes

- SQLite **no prueba PostgreSQL ni concurrencia real**. PostgreSQL local y Docker:
  **NOT RUN** en MAM-813. Los 62 skips se declaran, no equivalen a pruebas pasadas.
- Navegador físico/real, LIVE, dispositivos y proveedores: **NOT RUN**. El cliente
  HTTP de Django verifica HTML y persistencia, no interacción de navegador real.
- AUTH vigente: revisor externo independiente **NOT RUN (HTTP 401)**;
  **revisión independiente: BT2 PENDIENTE**, incluida la revisión de UI/etiquetas.
  No se reclama aprobación, aceptación ni se traslada la revisión de MAM-811.
- Renovación de los once gates y binding del candidato con este documento:
  **PENDIENTE del coordinador**. CI sobre el SHA publicado: **PENDIENTE en el PR**;
  los resultados locales anteriores no sustituyen ese CI.
- Esta entrega no hace commit, push, merge/integración, cambios de tracker ni cierre.
  El estado descrito es evidencia de implementación, no publicación ni Done.
