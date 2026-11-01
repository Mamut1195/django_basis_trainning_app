# MAM-625 — matriz de aceptación de progreso

Este recibo cubre el compromiso original de BASIS-011 y el último cambio de agenda e intensidad descriptiva. El cierre del ticket requiere además que este candidato se integre en `main` y complete su CI PostgreSQL; esos pasos todavía no están acreditados aquí.

| Criterio original | Evidencia funcional y límites |
| --- | --- |
| Los totales coinciden con series e intervalos de origen | `tests/regression/test_training_contract.py` contrasta la semana sintética: volumen externo 680 kg·rep (incluye calentamiento), adherencia 66,7 % y cargas 995/480 UA por protocolo. Distancia y desnivel usan resultados de bloque; los intervalos se consultan como detalle y no se suman otra vez. Las sesiones parciales no se suman como completadas. |
| Se distingue dato medido, estimado, incompleto y ausente | Cobertura por bloque o serie distingue dato, ausencia y no aplicación; cero permanece dato. `docs/STRENGTH_MARKS_2026-11-01.md` documenta marcas medidas declaradas y estimadas con método/fuentes separados. RPE de sesión por disciplina muestra mínimo/máximo y conteos conocidos/faltantes, sin convertir ausencia en cero. |
| Los filtros de fecha respetan zona horaria del usuario | Día y semana ISO se resuelven con la zona de cuenta; rangos inclusivos usan fechas de sesión almacenadas. `basis/bootstrap/tests/test_progress_periods.py` cubre zonas a ambos lados de medianoche y límites del calendario. Las versiones se resuelven antes de filtrar agenda. |
| Puede explicarse cada indicador y consultarse su detalle | El reporte nombra unidades, cobertura, protocolo y fuentes. Sesiones ejecutadas y prescripciones efectivas se listan con fecha, estado y enlaces privados; omisiones y pendientes permanecen consultables. Canceladas y futuras indican por qué no cuentan en adherencia. Se paginan las fuentes y las marcas. |

La frecuencia es el número de sesiones completadas que incluyen cada disciplina en el período. La intensidad es el rango mínimo/máximo del RPE observado de **sesión completa** en esas sesiones; una sesión con varios bloques de la misma disciplina cuenta una vez. En sesiones mixtas el mismo RPE de sesión aparece para cada disciplina presente, sin suma entre disciplinas ni inferencia sobre cada bloque. No se calculan promedios entre deportes, diagnósticos o predicciones. Sin observaciones se muestra «Sin datos».

La agenda resuelve primero las versiones efectivas y cortes, luego aplica el rango y pagina 20 registros. Solo consulta en lote las ejecuciones propias de las raíces de la página. Las anotaciones de estado filtran por cuenta; un enlace inconsistente de otra cuenta no cambia el estado ni la adherencia. La resolución efectiva aún materializa el historial en memoria: no se afirma un límite de capacidad o de latencia. La exportación no se modifica. Los objetivos de escala y dispositivos reales se validan por separado en MAM-638.

Los recibos anteriores conservan evidencia detallada: `docs/QUERY_BOUNDS_2026-11-01.md`, `docs/PROGRESS_PERIODS_2026-11-01.md` y `docs/STRENGTH_MARKS_2026-11-01.md`.

## Verificación local del candidato

- **VERIFIED:** suite Django SQLite en memoria: 602 pruebas, 66 omitidas, 104.711 s, con `config.test_settings`, clave sintética y `AI_ENABLED=0`. Las omisiones incluyen pruebas dependientes de PostgreSQL y navegador opt-in.
- **VERIFIED:** 229 pruebas de arquitectura, checker y ocho contratos de importación; mypy sin incremental core 130 archivos y Django 410; Ruff check y formato 420 archivos, djLint 51 plantillas, Prettier, migraciones sin cambios y `git diff --check`.
- **VERIFIED:** smoke Chromium `StaticLiveServerTestCase`, SQLite temporal y cuenta sintética: una prueba en 3.036 s, `player.js` HTTP 200, RPE cero, estados y enlaces. Capturas 390 × 844: `.cache/mam625-final-20261101/intensity-mobile.png` y `agenda-mobile.png`, revisadas por coordinación.
- **NOT RUN:** CI PostgreSQL del candidato, integración en `main`, pruebas de capacidad y dispositivos físicos. El estado de los cuatro criterios arriba expresa cobertura funcional local; no sustituye esos controles de integración.
