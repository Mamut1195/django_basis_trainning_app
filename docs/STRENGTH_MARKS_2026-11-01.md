# MAM-625 — historial privado de marcas de fuerza

La vista ofrece filtros por ejercicio del catálogo y fechas inclusivas, con paginación independiente de mediciones y estimaciones. Los ejercicios archivados siguen disponibles. La consulta usa las fechas almacenadas en cada registro, sin reinterpretación de zona horaria. Las lecturas y sus enlaces fuente se limitan a la cuenta autenticada; las rutas son GET/HEAD.

Las mediciones positivas se rotulan **1RM medido declarado**: las registró el usuario y no representan certificación instrumental. Los valores históricos no positivos no se presentan como marcas válidas; permanecen intactos en el historial persistido y en la exportación. Las estimaciones Epley se muestran por cada serie elegible de una sesión completada, con ejercicio efectivo, bloque, orden, valores observados y enlace a la sesión. No se combinan estimaciones en un máximo ni se transforman en una referencia medida. La regla y fórmula existentes siguen siendo las de `docs/STRENGTH_METRICS.md`; no se han añadido cálculos o tablas nuevas. Los datos legacy no verificados conservan sus rutas y semántica anteriores.

Las consultas de ambas listas filtran y paginan en base de datos y precargan relaciones. El filtro SQL de elegibilidad se contrasta en pruebas con la propiedad de dominio existente, incluidas adaptaciones de ejercicio, tipo de carga y clase de serie. Esto no es una prueba de capacidad ni una garantía sobre el planificador de una base productiva. No se incluyen gráficos, máximos consolidados, análisis de mejora ni una certificación instrumental.

La validación de navegador local usa `StaticLiveServerTestCase`, SQLite temporal y cuenta sintética: filtro y marcas separadas, enlaces a ambas fuentes y respuesta 200 de `player.js`. Capturas de viewport 390 × 844: `.cache/mam625-marks-20261101/marks-mobile-viewport.png`, `marks-mobile-results.png`, `marks-mobile-estimates.png` y `marks-mobile-source.png`. No se han verificado dispositivos físicos ni proveedores reales. PostgreSQL y CI remoto del candidato quedan pendientes.

## Resultados locales

- **VERIFIED:** suite Django SQLite temporal: 599 pruebas, 66 omitidas, 63.811 s. Las omisiones incluyen pruebas dependientes de PostgreSQL y navegador opt-in; no se atribuyen a resultados PostgreSQL.
- **VERIFIED:** 228 pruebas de arquitectura, checker y ocho contratos de importación; mypy sin incremental core 130 archivos y Django 409; Ruff check y formato 419 archivos; djLint 51 plantillas; Prettier, migraciones sin cambios y `git diff --check`.
- **VERIFIED:** smoke Chromium con recursos estáticos servidos: una prueba en 2.335 s, `player.js` HTTP 200; filtros y enlaces a las dos fuentes. Coordinación informó revisión visual de las capturas móviles.
- **NOT RUN:** PostgreSQL y CI remota del candidato, pruebas de capacidad y dispositivos físicos. El lote no declara el cierre integral de MAM-625.