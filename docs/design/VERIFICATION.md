# MAM-626 · Verificación del boceto portable

23 de octubre de 2026. Complemento estático del contrato UX existente; no cierra el ticket ni certifica la aplicación Django. Aprobación del propietario **PENDING**, lector de pantalla y dispositivo físico **NOT RUN**.

## Evidencia de preparación ejecutada

`verify_prototype.py` se ejecutó contra `file://`, sin servidor ni recursos externos. Python 3.13.7, Playwright 1.64.0 y Chromium headless shell 153.0.8010.12 ya instalado. Ejecutable Chromium SHA-256 `addfa79abb060e1e514e155ed745d4bf96140bca402735958bb4e223aea0b98c`.

| Comprobación | Resultado observado |
| --- | --- |
| 5 vistas × 7 estados × 2 anchos × 2 temas | **VERIFIED**, 140 auditorías, 0 fallos y 0 pinturas pendientes de revisión |
| Inicio, entrenamiento, reprogramación, progreso, propuesta | **VERIFIED**; consultar/rechazar no cambia el plan, aceptar es explícito; observaciones anteriores conservadas |
| Estados y recarga | **VERIFIED**; no éxito remoto, vacío/carga sin resultados, error/conflicto bloquean acciones; recargar restablece memoria |
| Teclado | **VERIFIED**, 1.648 paradas Tab registradas con foco; orden único coincide con DOM, fechas incluyen segmentos nativos y botón calendario |
| Texto y controles | **VERIFIED**, 6.000 muestras de texto, 1.588 mediciones de controles, 1.760 bordes de input/select; controles medidos >= 44 px |
| Contraste mínimo observado | Texto **7,338:1**; foco **13,982:1**; bordes **4,548:1**, sin redondear para decidir |
| Regresiones del propio auditor | **VERIFIED**: blanco/negro 21:1, gris bajo 4,5 rechazado, alfa; foco invisible, bordes tenues, trampa y repetición de fecha rechazados |
| Fuentes antes/después | **VERIFIED**, estables durante la preparación; logo canónico idéntico byte a byte |
| Red y JavaScript | 0 intentos externos, 0 errores JavaScript; navegador cerrado |
| Formato dirigido | **VERIFIED** con Prettier fijado y Ruff format |
| Ruff / Django check / regresión web existente | **VERIFIED** localmente: sin hallazgos y 8 tests web OK; advertencia de staticfiles inexistente en entorno de test |
| pytest | **NOT RUN**: no está instalado ni configurado en este proyecto; regresión con el runner Django nativo |

Las cuatro capturas de Hoy se inspeccionaron visualmente en ambos temas y anchos. En móvil la barra inferior fixed aparece a la altura del viewport en la captura full-page; esta imagen no prueba ausencia de oclusión durante todo el scroll. No se atribuye revisión visual exhaustiva a las 140 combinaciones.

| Captura | SHA-256 |
| --- | --- |
| [390 claro](capturas/hoy-390-light.png) | `ead4b78209d9bbcdce7859318925130e4d12e4dcba53e245cd9ed93846e97dbd` |
| [390 oscuro](capturas/hoy-390-dark.png) | `5f58ff0e83019475dbf2336a86b2fa06c59fb84eefdf19c52a4198220ca5e4ca` |
| [1440 claro](capturas/hoy-1440-light.png) | `ed43e360ff6eda75bb1a67a7279264c7e13ebded660320d4b1a72e8d11a06d49` |
| [1440 oscuro](capturas/hoy-1440-dark.png) | `7820c7248648f0d1e99c5033f605d8002a562b60217271fb0d551d2fb95e2402` |

Informe completo local de preparación: `basis-runs/MAM-626-ux1/preparation-report-v4.json`, SHA-256 `8c02a4e8f967137bac61d18a780c90a83419a96bcd2c61a40f7de9f431c3872b`. Sus hashes documentales corresponden al estado anterior a este resumen. El runner Systems debe ligar los gates finales y la revisión al candidato exacto posterior; no reutilizar esta preparación como aprobación de un árbol diferente. Los logs y resultados sellados finales permanecen bajo `basis-runs/MAM-626-ux1`, sin secretos ni bases personales. El PR consigna el resultado final de gates/revisión y CI por separado.

## Reproducción desde la raíz

Elegir **otro directorio nuevo**; `capturas/` ya contiene PNG que se preservan. No instalar navegador ni sobrescribir informes:

```powershell
.venv-win/Scripts/python.exe -B docs/design/verify_prototype.py --output .cache/mam626-ux-nuevo --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
node node_modules/prettier/bin/prettier.cjs --ignore-path .gitignore --check docs/design/prototipo/index.html docs/design/prototipo/styles.css docs/design/prototipo/app.js
.venv-win/Scripts/python.exe -B -m ruff check .
.venv-win/Scripts/python.exe -B -m ruff format --check docs/design/verify_prototype.py
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DJANGO_SECRET_KEY = 'MAM626-local-test-only-not-production'
$env:BASIS_DATABASE_PATH = ':memory:'
.venv-win/Scripts/python.exe -B manage.py check
.venv-win/Scripts/python.exe -B manage.py test tests.regression.test_web --noinput
```

## Hallazgos corregidos y límites

- La copia UTF-8 inicial alteraba el SVG: reemplazada por copia byte-exacta canónica.
- `wait_for_function` requiere `arg=target`; corregido.
- Prettier excluye `docs/` por defecto: comprobación explícita con `--ignore-path .gitignore`, sin cambiar la política del repositorio.
- La fecha nativa tiene varias paradas con el mismo nodo. El auditor conserva todas, limita repeticiones y prueba el control siguiente; no las confunde con un bucle ni permite trampas ilimitadas.
- El botón nativo del calendario perdía el outline exterior. `input[type="date"]:focus-within` comparte tokens de foco y todos los criterios geométricos/de contraste siguen vigentes.
- Los separadores decorativos no sirven como borde de campo: `--control-border` distingue controles en ambos temas, sin alterar la marca.

Screening de colores sólidos y controles nativos, no certificación WCAG. No cubre todos los píxeles SVG, pseudo-elementos, placeholders, hover/disabled, área/recorte de foco, zoom, oclusión ni tecnología asistiva. No acredita persistencia, PWA instalada, sincronización real, backend o calidad deportiva IA. El boceto nunca promete guardar fuera de la pestaña. Las pruebas históricas de la aplicación conservan su propio alcance y no se sustituyen por estas muestras.
