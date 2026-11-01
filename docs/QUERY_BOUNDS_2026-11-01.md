# MAM-625 — consultas de calendario y paginación de bienestar

Este lote reduce consultas repetidas y pagina el historial de bienestar. No cierra MAM-625: quedan por contrastar requisitos de períodos, procedencia, detalle y datos incompletos con su aceptación funcional.

## Medición SQLite

El fixture de `scripts/benchmark_calendar_queries.py` crea por cuenta 10, 100 y 1.000 sesiones sintéticas para el mismo día, con sucesor y fecha de corte; la mitad tiene ejecución completada. Se contó por separado selección efectiva, consultas adicionales de estado, selección para adherencia y render completo de Hoy. Los resultados se verificaron en SQLite temporal, con la misma entrada antes y después:

| Sesiones | Selección antes → después | Estados adicionales | Adherencia | Hoy |
| --- | --- | --- | --- | --- |
| 10 | 12 → 2 | 15 → 0 | 22 → 2 | 36 → 11 |
| 100 | 102 → 2 | 150 → 0 | 202 → 2 | 261 → 11 |
| 1.000 | 1.002 → 2 | 1.500 → 0 | 2.002 → 2 | 2.511 → 11 |

La revisión independiente de coordinación repitió el benchmark optimizado: los mismos conteos, una prueba en 2.201 s. No se midió latencia comparable, concurrencia ni capacidad para usuarios reales. Hoy renderiza las 1.000 filas del fixture, no simula 1.000 usuarios.

Reproducir desde la raíz con Python del entorno de desarrollo:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:DJANGO_DEBUG = '1'
$env:DJANGO_SECRET_KEY = 'synthetic-test-only-key'
$env:AI_ENABLED = '0'
$env:PYTHONPATH = 'scripts'
.venv-win/Scripts/python.exe manage.py test benchmark_calendar_queries --noinput
```

Las anotaciones `Exists` conservan la consulta por raíz o copia de intención; las pruebas comparan los resultados con esa consulta y cubren ejecución de raíz/copia, versión y otra cuenta. Un objeto no anotado mantiene el comportamiento anterior. Se guarda por sucesor el cálculo de su fecha de corte durante la selección.

**Límites:** `effective_sessions` aún materializa el historial seleccionado; las subconsultas siguen costando trabajo dentro de SQL y Hoy filtra la fecha después. El conteo de consultas no demuestra menor latencia bajo todos los planes de ejecución. Se añadió el benchmark al job PostgreSQL de CI; el resultado PostgreSQL del candidato queda **NOT RUN** hasta su ejecución real.

## Bienestar

El historial usa páginas de 20 filas con filtros y orden existentes. Enlaces anterior/siguiente conservan el rango; el aislamiento por cuenta y la exportación completa se verifican en pruebas. No se añade límite arbitrario al rango ni se truncaron datos exportados.

## Comprobaciones del candidato local

- **VERIFIED:** suite Django SQLite de 582 pruebas, 65 omitidas, 72.666 s; se ejecutó antes del ajuste posterior de tipos y formato, sin cambios en la lógica de esa suite. Después del ajuste, 46 pruebas focales de progreso, bienestar y versionado pasaron en 8.367 s.
- **VERIFIED:** arquitectura (223 pruebas y checker), 8 contratos de importación, mypy sin incremental core (127 archivos) y Django (399 archivos), Ruff check y formato (408 archivos, incluido el benchmark), djLint 49 plantillas, migraciones sin cambios y Prettier.
- **NOT RUN:** CI y benchmark PostgreSQL del candidato; los controles anteriores no demuestran capacidad ni aceptación integral MAM-625.