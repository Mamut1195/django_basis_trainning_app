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

## R2 · Readback de preparación verificada · 23 de octubre de 2026

Esta sección es la referencia para la R2; los 140 casos, cuatro PNG y hashes anteriores describen R1 y se conservan como historia (capturas R1 en Git, commit `59fa795`). Los PNG actuales de `capturas/` son R2. La revisión de diseño y onboarding fue autorizada en `basis-runs/DESIGN-MAM-626-R2.md`. No cambia runtime ni convierte este boceto en un registro real.

El informe `basis-runs/MAM-626-ux1/R2-diagnostic4/report.json` pasó y se comprobó que sus hashes de fuentes coinciden con las fuentes antes de añadir este readback. El runner vuelve a ligar la batería final al candidato documental/capturas definitivo; el PR registra el resultado final y CI remoto por separado.

| Comprobación R2 | Resultado de preparación |
| --- | --- |
| 7 rutas × 7 estados × 2 temas × 2 anchos | **VERIFIED**, 196 auditorías base con herramientas plegadas |
| 7 rutas con disclosures abiertos × 2 temas × 2 anchos | **VERIFIED**, 28 auditorías adicionales; total **224**, 0 fallos y 0 pinturas pendientes |
| Hoy móvil 390×844 | **VERIFIED** en ambos temas: scrollY=0, sesión termina en y=603,83 y CTA en y=587,83; barra empieza en y=763. CTA ancho 322 px = contenido 322 px; una acción primaria, iconos/texto visibles |
| Registro rápido y descanso | **VERIFIED**, tabla por serie, previos separados de entradas vacías, kg/reps/RPE inválidos no marcan, check >=48×48, bloqueo/desmarcado, RIR independiente y cero distinto de ausencia |
| Descanso automático | **VERIFIED** con reloj virtual Playwright: 90 s ilustrativos, un único intervalo, navegación conserva deadline; expirar/omitir no envía ni marca otras series |
| Plan | **VERIFIED**, semana de ejemplo, fecha oculta hasta Reprogramar; cancelar descarta borrador, aplicar modifica solo el futuro plan |
| Onboarding | **VERIFIED**, bienvenida/registro, validación de campos vacíos/email/contraseña ficticia corta/mayoría de edad, recuperación y resultado local que niega cuenta/correo/servidor |
| Datos de alta | **VERIFIED**, contraseña redactada en auditoría de color y borrada tras envío/navegación; no se refleja ni persiste; recargar restablece todos los inputs y resultado |
| Texto/teclado/targets/bordes | **VERIFIED**, 8.668 muestras de texto, 2.384 paradas de teclado, 2.372 controles medidos y 1.136 bordes de campos |
| Contraste | Todos los textos >=4,5:1, incluso grandes; mínimos observados texto **7,338:1**, foco **13,982:1**, borde **4,548:1**. Decisión sin redondear |
| Geometría de foco | **VERIFIED**, margen libre de 6 px; scroll nativo deja controles enfocados fuera de la barra móvil y evita recorte exterior en escritorio |
| Propuesta, estados y recarga | **VERIFIED**, consulta/rechazo no aplican, aceptación explícita conserva sesión A; estados no simulan éxito remoto; memoria se pierde al recargar |

Herramientas: Python 3.13.7, Playwright 1.64.0, Chromium 153.0.8010.12 ya instalado, SHA-256 del ejecutable `addfa79abb060e1e514e155ed745d4bf96140bca402735958bb4e223aea0b98c`. Sin descargas de navegador. Se conservaron las pruebas negativas previas y se añadieron rechazo de texto grande por debajo de 4,5, label menor de 14 px, control oculto por barra y controles dentro de disclosures. No se rebajaron umbrales.

### Diez capturas R2 actuales

| PNG | SHA-256 |
| --- | --- |
| [Hoy 390 claro](capturas/hoy-390-light.png) | `d454466d6a7fc7752821be86dda53fa53edf5021cc127dae8eb6bd3de195375b` |
| [Hoy 390 oscuro](capturas/hoy-390-dark.png) | `38d5f0946c1844c8f10f0593d60152014124278044763ab3a08b49846c39b1df` |
| [Hoy 1440 claro](capturas/hoy-1440-light.png) | `6360aa8a221fd9de3fc8b35dd0d7541b66da00f8981f997cfda07a9cd716c591` |
| [Hoy 1440 oscuro](capturas/hoy-1440-dark.png) | `7b81fd6979921329ed7251177b3756a87223e10ee2906a2176e62f5d1fcc5c65` |
| [Plan 390 claro](capturas/plan-390-light.png) | `9703816e33b26dfe5c34a7444aa521a313be9cd237e2d50d8133bb273ac10412` |
| [Plan 390 oscuro](capturas/plan-390-dark.png) | `d7919c52381289d2ae72364e01891f91c5d4c0cdeda79ec168ddf9a48e92e89e` |
| [Bienvenida 390 claro](capturas/onboarding-390-light.png) | `05726d27c08a539f6278243853270bf96a5fc3b96ed96c399d4f08060733b29c` |
| [Bienvenida 390 oscuro](capturas/onboarding-390-dark.png) | `6fdb8d3cb37f63938b8481359a6272ca894af5a2bf45d30a54537bba7cef190e` |
| [Registro 390 claro](capturas/registro-390-light.png) | `50be2657278087b459af093a1617da1781b11cbab92c64e2b9b862abbe831ba0` |
| [Registro 390 oscuro](capturas/registro-390-dark.png) | `7a71ff3b4fd7b5005e32fe63739d9b39c4038f4ee8ba02b2703293217d8c4ae2` |

El coordinador inspeccionó visualmente Hoy 390 claro, Plan 390 oscuro, bienvenida 390 claro y registro 390 oscuro; no se atribuye revisión visual a las 224 combinaciones. En full-page Chromium compone la barra fixed en la posición de su viewport original; la imagen larga no demuestra por sí sola oclusión durante todo el scroll. La prueba de geometría registra el scroll nativo de cada control enfocado, no lo corrige artificialmente.

Correcciones reproducidas durante R2: esperar hashchange/render antes de cerrar herramientas con teclado; ampliar enlaces de texto de 21/24 px a targets de 48 px; aplicar scroll-padding/scroll-margin también en escritorio para no recortar el outline. Se corrigió la UI donde falló, sin silenciar el auditor.

**revision independiente: BT2 — PENDIENTE. Revisor externo, aprobación humana, lector de pantalla y dispositivo físico: NOT RUN.** Screening no equivale a certificación WCAG, aceptación humana, sincronización/backend reales o cierre de MAM-626. Sin merge.
