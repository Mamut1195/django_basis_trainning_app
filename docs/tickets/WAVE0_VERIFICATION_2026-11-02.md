# Tanda 0 — scope estricto del probe de auditoría

Fecha: 2026-11-02. Rama de trabajo: `codex/basis-wave0-20261102`, base indicada
`d3501a78b37050cfc352af175b898a5aa9a4f11b`. Recibo local; no acredita
integración, cierre de tickets ni CI remoto.

## Problema y cambio

Antes del cambio, `.venv-win/Scripts/python.exe scripts/architecture_check.py`
terminó con código 1 y este mensaje:

```text
Python file outside strict scope and legacy inventory: docs/tickets/evidence/probes_2026_11_02.py
```

El checker obtiene las rutas estrictas de la propiedad `files` de
`mypy-core.ini` y `mypy-django.ini`. Se añadió la ruta exacta del probe a esta
última. No se modificó el checker, el inventario legacy ni las exclusiones.
El probe ya cumple el tipado estricto; no necesitó cambios de código ni
supresiones de errores. Conserva los comportamientos auditados.

## Verificación ejecutada

Todos los comandos Python usaron `.venv-win/Scripts/python.exe` desde el
checkout principal. Para mypy y los probes se fijaron explícitamente:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:DJANGO_SECRET_KEY = 'wave0-synthetic-only'
$env:AI_ENABLED = '0'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

| Comando, después del cambio | Resultado real |
| --- | --- |
| `python scripts/architecture_check.py` | VERIFIED, código 0: límites de capas/public e inventario legacy |
| `python -m mypy --config-file mypy-core.ini --no-incremental` | VERIFIED, código 0: 130 archivos sin errores |
| `python -m mypy --config-file mypy-django.ini --no-incremental` | VERIFIED, código 0: 411 archivos sin errores, incluido el probe |
| `python -m unittest discover -s tests_architecture` | VERIFIED, código 0: 229 pruebas, 5.629 s |
| `python -m ruff check docs/tickets/evidence/probes_2026_11_02.py` | VERIFIED, código 0 |
| `python -m ruff format --check docs/tickets/evidence/probes_2026_11_02.py` | VERIFIED, código 0: un archivo ya formateado |
| `python manage.py test probes_2026_11_02.AuditProbes --noinput` | VERIFIED, código 0: tres pruebas, 0.145 s, base de prueba creada y destruida |
| `git diff --check -- mypy-django.ini docs/tickets/evidence/probes_2026_11_02.py` | VERIFIED, código 0: sin errores de whitespace en el diff propio rastreado |

La ejecución focal añadió `DJANGO_DEBUG=1` y
`PYTHONPATH=docs/tickets/evidence`. Usó SQLite en memoria, cuentas sintéticas y
proveedores falsos. Su salida conservó:

```text
AUDIT historical_rows=10 selection_and_status_queries=21
AUDIT historical_rows=100 selection_and_status_queries=201
AUDIT same_queued_job_usage costs_before_after_rate_change=[Decimal('0.00036120'), Decimal('0.00060120')]
AUDIT requested=deepseek-v4-flash reported=reported status=succeeded cost=0.00036120
```

Estos resultados reproducen el N+1 histórico, el uso de tarifa mutable y la
aceptación de un modelo reportado distinto. No verifican sus correcciones ni
una pérdida monetaria real. F01/F02 y las pruebas que los reproducen no se
modificaron.

## Alcance y límites

Archivos propios: `mypy-django.ini` y este recibo. El probe queda intacto.
Se conservaron los documentos ajenos no rastreados y los cambios concurrentes
de otros responsables. No se hicieron commits, integración, push, PR ni cambios
del tracker. No se leyeron `.env`, secretos ni `db.sqlite3`.

**NOT RUN:** suite Django completa, PostgreSQL/concurrencia, navegador, CI
remoto, imagen de producción, operación y auditoría de dependencias. No se
contactó a proveedores ni se modificaron bases reales.
