# MAM-624 — bienestar y recuperación

El check-in es opcional y registra observaciones declaradas para una cuenta y fecha: general, antes o después de entrenar. Los campos pueden quedar vacíos; los ceros se conservan. El historial muestra los campos registrados con unidades y escalas, sin diagnóstico ni predicción. La duración y el RPE de sesión conservan el modelo existente y no se confunden con el RPE por serie.

El formulario, el límite de fecha futura y el rango inicial del historial usan la zona horaria configurada por la cuenta, con la zona de la aplicación como alternativa. La consulta requiere autenticación, escritura mantiene la política comercial existente y cada registro pertenece a su cuenta. Exportación y contexto conservan los momentos; para seleccionar una observación se ordena por fecha descendente y, el mismo día, después > antes > general. El wire acepta contextos anteriores sin `moment` como general.

La migración `0004_wellness_checkin_moment` asigna `day` a registros anteriores y cambia la unicidad a cuenta, fecha y momento. **Reversión limitada:** si existen varios momentos de una cuenta en una fecha, volver directamente a `0003` no puede reinstaurar la unicidad anterior sin conflicto. No se deben borrar ni fusionar observaciones automáticamente. La recuperación operativa requiere respaldo y una restauración probada, con decisión humana sobre el estado de destino; no se ha probado reversión de datos de producción.

## Evidencia local

La fuente no comprometida se recuperó de `MAM-624` con manifiesto SHA-256 de 18 archivos en `.cache/mam624-20261101/source-manifest.json`; no se modificó el worktree origen. Base candidata `c716a294b6366299c5f1def6335362212c809de1`.

- **VERIFIED:** suite Django completa de CI en SQLite temporal: 579 pruebas en 51.962 s, 65 omitidas. La batería focal incluye 20 pruebas wellness; incluyen captura parcial, cero y ausencias, edición, fechas en Nueva York y Tokio al cruzar medianoche, CSRF negativo y positivo, aislamiento, constraint, migración previa, exportación y contexto.
- **VERIFIED:** navegador Chromium headless local y `LiveServerTestCase`, SQLite temporal y cuenta sintética: captura antes/después e historial. Es un smoke focal, no aceptación en dispositivos físicos.
- **VERIFIED:** 223 pruebas de arquitectura y 8 contratos de importación; mypy sin caché incremental en 127 archivos core y 398 Django; Ruff check y format, djLint de 49 plantillas, y `makemigrations --check --dry-run`.
- **NOT RUN:** PostgreSQL del candidato, carreras reales PostgreSQL y CI remoto del candidato. No se conectaron proveedores externos ni datos existentes.

La batería usa `DJANGO_SETTINGS_MODULE=config.test_settings`, `DATABASE_URL=sqlite:///:memory:`, `DJANGO_DEBUG=1` y clave sintética. Los resultados no acreditan integración en `main` ni aceptación de producción.
