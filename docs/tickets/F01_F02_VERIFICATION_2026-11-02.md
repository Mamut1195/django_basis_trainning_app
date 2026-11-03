# MAM-635 / MAM-818 — verificación acotada F01/F02

Fecha: 2026-11-02. Base local: `2b9ed1c`. Candidato **sin commit**, en el worktree
aislado `C:/Users/Jonnathan/.t3/worktrees/django-basis-trainning-app/t3-cae78107`.
Árbol inicial limpio. No se modificó el estado remoto de ningún ticket:
**MAM-635 y MAM-818 permanecen In Progress**, con dependencias MAM-633/MAM-634
y criterios adicionales pendientes. Este recibo no acredita integración ni cierre.

## Comportamiento corregido

- **F01:** JSON no objeto, incluido un valor no vacío, devuelve el resultado
  ambiguo del contrato existente. El worker persiste `uncertain`, `cost=None`,
  fecha de finalización y error controlado; retiene la reserva y procesa el job
  válido posterior. No activa el bloqueo global por este caso ni reenvía el job.
- **F02:** contenido nulo se normaliza a texto vacío con `answer_is_text=False`.
  La aplicación también protege el caso de un proveedor inyectado que entregue
  directamente `ProviderReply(answer=None)`, incluso con una bandera de texto
  incoherente. `Job.answer` es `str`, compatible con la columna NOT NULL existente.
- Con uso válido y contenido nulo, el resultado es `failed`: se conservan modelo
  reportado, tokens, costo calculado y error; cuenta y fondo trial liquidan una
  sola vez. Los importes comprobados usan las tarifas ya presentes en el código;
  no verifican precios actuales del proveedor ni una factura real.
- Sin uso válido se conserva `uncertain` y la reserva de cuenta/fondo. Se mantiene
  la política previa de bloqueo ante uso inválido; su conciliación queda pendiente.

No se cambiaron modelos, migraciones, adaptador ORM ni composición de bootstrap.
No se alteraron tarifa, modelo, conciliación F03–F05, entrenamiento, progreso o billing.

## Archivos del candidato

1. `basis/modules/coach/adapters/provider.py`
2. `basis/modules/coach/domain/jobs.py`
3. `basis/modules/coach/application/jobs.py`
4. `tests_architecture/test_coach_jobs.py`
5. `tests_architecture/coach_jobs_contract.py`
6. `basis/bootstrap/tests/test_coach_jobs.py`
7. `basis/bootstrap/tests/test_coach_edges.py`
8. `docs/tickets/F01_F02_VERIFICATION_2026-11-02.md`

## Entorno y aislamiento ejecutados

Intérprete real:
`C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`.
Python 3.13.7; Django 5.2.18; httpx 0.28.1; psycopg 3.3.6; mypy 1.19.1;
Ruff 0.17.1; import-linter 2.11.

Pruebas con `config.test_settings`, secreto sintético, `AI_ENABLED=0` en el
entorno y credencial sintética. Los fixtures activan exclusivamente la configuración
de prueba necesaria para ejercer el worker, con puertos falsos o MockTransport.
El runner local bloquea transporte HTTP real y conexiones Python de red, salvo
el endpoint PostgreSQL autorizado. Psycopg usa la conexión nativa a esa instancia.

- SQLite: memoria, `file:memorydb_default?mode=memory&cache=shared`.
- PostgreSQL autorizado por coordinación:
  `postgresql://basis_wave0@127.0.0.1:55482/basis_hardening635`.
  Versión consultada: PostgreSQL **18.4**, Windows x86_64. Django creó y destruyó
  exclusivamente `test_basis_hardening635` en cada ejecución. No se creó servicio
  ni se modificó una base real o la base de otro agente.

Evidencia local conservada en `.cache/f01-f02-2026-11-02/`, incluidos runner,
versiones, plan, logs y patch revisable. La carpeta es ignorada por Git y debe
conservarse junto con este worktree para el handoff.

## Resultados ejecutados

| Comprobación | Resultado | Evidencia local |
| --- | --- | --- |
| Reproducción de los dos tests heredados | VERIFIED: ambos esperaban y recibían AttributeError/IntegrityError | `baseline.log` |
| Regresiones nuevas antes del fix | FAILED esperado: 3 tests, 1 fallo y 5 errores de subcasos | `red-regressions.log` |
| Focal fake + ORM + decoder, SQLite | VERIFIED: 50 tests, 2 omisiones de concurrencia PostgreSQL | `sqlite-focal.log` |
| Misma focal, PostgreSQL 18.4 | VERIFIED: 50 tests, cero omisiones | `postgres-focal.log` |
| Focal + regresión billing/IA, PostgreSQL | VERIFIED: 65 tests, cero omisiones, 7.919 s | `postgres-final.log` |
| Suite pura de arquitectura | VERIFIED: 237 tests, 4.112 s | `pure.log` |
| Checker de capas/public e inventario | VERIFIED | `architecture.log` |
| mypy-core estricto | VERIFIED: 130 archivos | `mypy-core-initial.log` |
| mypy-django estricto | VERIFIED: 411 archivos | `mypy-django.log` |
| Import Linter | VERIFIED: 8 contratos conservados | `imports.log` |
| Ruff focal / Ruff format focal | VERIFIED: 7 archivos | `ruff.log`, `format.log` |
| Detección de migraciones | VERIFIED: No changes detected | `migrations.log` |
| Django system check | VERIFIED: sin incidencias | `django-check.log` |
| Diff y propiedad de archivos | VERIFIED: 7 modificados y este recibo nuevo; índice sin cambios | `manifest.json` |
| Patch contra base e inversión contra worktree | VERIFIED: `git apply --check --cached` y `--check --reverse` | `patch-check.log` |

El contrato compartido se ejecuta con `Memory` y `DjangoJobsRepository` y comprueba:

- cuenta pagada y trial: contenido nulo, tokens/modelo/costo, reservas y fechas;
- repetición de liquidación con respuesta, ambigüedad o rechazo definitivo sin
  alterar el job terminal, gastar dos veces o liberar dos veces;
- fallo inyectado al guardar el job **después** de escribir saldos: rollback
  conjunto de cuenta/fondo/job; posterior persistencia de la misma respuesta
  recibida sin otra llamada al proveedor;
- respuesta ambigua y respuesta nula seguidas de una válida: dos llamadas para
  dos jobs, ningún tercer envío, reserva residual y gasto coherentes;
- uso desconocido: retención de ambas reservas, sin convertirlo en costo cero.

Los tests HTTP usan MockTransport con `[1]`, `true`, texto, número y contenido
nulo, cada uno seguido de una respuesta válida. Las carreras PostgreSQL usan
dos conexiones y locks reales: reclamación de jobs distintos y dos intentos
simultáneos de liquidar el mismo contenido nulo, tanto pagado como trial, con un
solo débito/liberación. La barrera se espera antes de adquirir los locks.

## Comandos de reproducción

Desde el worktree indicado; el runner aplica las variables sintéticas y la barrera
de red. No reutilizar estas instrucciones contra una base de datos real.

```powershell
$taskPython = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
$taskRunner = '.cache/f01-f02-2026-11-02/run_checks.py'
& $taskPython $taskRunner test tests_architecture.test_coach_jobs basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges --noinput -v 2
& $taskPython $taskRunner --postgres test tests_architecture.test_coach_jobs basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges tests.regression.test_billing_ai --noinput -v 2
& $taskPython $taskRunner makemigrations --check --dry-run
& $taskPython -m unittest discover -s tests_architecture
& $taskPython scripts/architecture_check.py

$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:DJANGO_DEBUG = '1'
$env:DJANGO_SECRET_KEY = 'f01-f02-synthetic-only'
$env:AI_ENABLED = '0'
& $taskPython -m mypy --config-file mypy-core.ini --no-incremental
& $taskPython -m mypy --config-file mypy-django.ini --no-incremental
& 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/lint-imports.exe'
$taskFiles = @(
  'basis/modules/coach/adapters/provider.py',
  'basis/modules/coach/domain/jobs.py',
  'basis/modules/coach/application/jobs.py',
  'tests_architecture/test_coach_jobs.py',
  'tests_architecture/coach_jobs_contract.py',
  'basis/bootstrap/tests/test_coach_jobs.py',
  'basis/bootstrap/tests/test_coach_edges.py'
)
& $taskPython -m ruff check @taskFiles
& $taskPython -m ruff format --check @taskFiles
git diff --check
```

## Límites y pendientes

NOT RUN: suite Django completa del candidato integrado, navegador/dispositivos,
CI remoto, servicios operativos, carga sostenida y proveedor/pagos reales.
No se hicieron commits, push, PR, tickets, despliegues ni llamadas pagadas.

Las reservas `uncertain` continúan pendientes de conciliación: este parche no
introduce un reconciliador ni reenvía solicitudes posiblemente facturadas. Los
casos de uso/modelo/precio y restricciones contables más amplias F03–F05 quedan
para MAM-818; la aceptación IA/contexto/propuestas de MAM-633/634/635 sigue abierta.
La integración y aceptación del árbol combinado corresponden a coordinación.
