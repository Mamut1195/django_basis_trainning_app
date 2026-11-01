# Correcciones locales BASIS — 2026-11-01

Base: `main` en `d514539e2ee9eed1d7e0a5fd4ffa889c3176289d`. MAM-1009 y MAM-1010 están In Review en Linear tras la revisión independiente y sus cambios están en la rama candidata; esta evidencia local no implica integración, cierre ni aceptación de producción.

## MAM-1009 — aislamiento de prueba Polar

La prueba de revalidación de caché parcheaba `basis.modules.billing.adapters.actions.polar_request`, mientras `billing()` toma `request` de `basis.bootstrap.billing`. Antes de corregirla se ejecutó solo esa prueba con `httpx.Client` bloqueado: **FAILED**, por `AssertionError: unexpected external HTTP client`, antes de abrir red. Esto reprodujo el uso del objeto equivocado.

La prueba ahora parchea `basis.bootstrap.billing.request` y comprueba cada llamada GET y su ruta. La clase de aceptación bloquea `httpx._client.HTTPTransport` y prueba explícitamente esa barrera; la prueba de contrato usa `MockTransport` en memoria. No se cambió la lógica de facturación ni se llamó al proveedor.

Una primera versión de la barrera parcheaba `httpx.HTTPTransport`, que no intercepta el alias usado internamente por el cliente. La primera suite después de añadirla falló con un error de permisos al cargar certificados. Esa misma ejecución tuvo dos fallos adicionales porque el ejecutor desactivó todo el logging para filtrar salida, interfiriendo con pruebas que lo verifican. Se corrigió el punto de parche y se conservó el logging normal; no se cuentan esos resultados como validación final.

## MAM-1010 — formato en Windows

`.gitattributes` declara `text eol=lf` para los patrones CSS/JS propios de `format:check`. Se normalizaron ocho archivos del checkout de CRLF a LF, sin cambio de contenido frente al índice. Los diez archivos coincidentes examinados quedaron sin CRLF. No se aplicó renormalización global ni se editaron archivos de terceros.

## Comprobaciones finales

| Comprobación | Resultado local |
| --- | --- |
| Suite de CI Django con `config.test_settings`, `DATABASE_URL=sqlite:///:memory:`, DEBUG y clave sintética | **VERIFIED**: 559 pruebas en 65.434 s, 65 omitidas. |
| `python -m unittest discover -s tests_architecture` | **VERIFIED**: 218 pruebas. |
| `python -m mypy --no-incremental --config-file mypy-core.ini` | **VERIFIED**: 126 archivos. |
| `python -m mypy --no-incremental --config-file mypy-django.ini` | **VERIFIED**: 395 archivos tras el ajuste final de la barrera. |
| `ruff check .`; `ruff format --check tests/regression/test_billing_polar.py` | **VERIFIED**. |
| `npm.cmd run format:check` | **VERIFIED** con la configuración existente. |
| `git diff --check`; `git check-attr text eol` para ejemplos propios | **VERIFIED**: sin errores de whitespace; atributos LF aplicados. |

Revisión independiente informada por coordinación: los dos tests focales de revalidación y barrera pasaron en 0.104 s con SQLite en memoria; `git check-attr` confirmó LF en `app.css` y `offline.js` y sin atributo especificado para el vendor HTMX; `npm.cmd run format:check` pasó. El ejecutor de este documento no repitió esa revisión independiente.

**NOT RUN:** PostgreSQL para el candidato, CI remoto del candidato, pruebas LIVE de Polar y aceptación de producción. Las omisiones SQLite incluyen pruebas dependientes de capacidades de PostgreSQL; el resultado no demuestra concurrencia PostgreSQL. Los dos documentos de handoff y revisión preexistentes permanecen fuera del cambio.
