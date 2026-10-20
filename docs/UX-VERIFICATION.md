# Verificación UX: foco y contraste

Fecha: 20 de octubre de 2026. Alcance: seguimiento técnico de BASIS-012/MAM-626 y BASIS-013/MAM-627. Ambos conservan su aceptación humana pendiente; este informe no cierra tickets.

## Causas reproducidas

| Hallazgo | Diagnóstico | Corrección |
| --- | --- | --- |
| `r3`: outline transparente, ratio 1:1, en botones Cotton | Falso positivo de tiempo. `transition` anima `outline-color`; el auditor llamaba a `focus()` y leía el estilo en el mismo turno. En el DOM mínimo, el mismo control tiene outline azul sólido de 3 px tras 300 ms. Estas variantes de Cotton 0.3.4 usan outline, no una sombra sustitutiva. | Esperar fuentes, un frame y animaciones finitas acotadas; medir el estado asentado de cada control. Una animación no acotada queda en revisión. |
| `r3`: «Ver mi plan», foco azul sobre hero azul, 1,31:1 en claro | Defecto real: `--accent` no distingue el indicador del fondo del hero. | `.hero :focus-visible { outline-color: var(--hero-foreground); }`. El foco efectivo mide **11,195:1** en ambos temas y los tres anchos. |
| El auditor ignoraba `outline:none` y ancho cero | Falso negativo: omitía comprobar si existía otro indicador. Un outline transparente tampoco demuestra ausencia de foco si hay un anillo por sombra. | Registrar estilos anterior/posterior, `:focus-visible` y resultado por selector. Ausencia de indicador medible produce `missing-indicator`; contraste insuficiente produce `low-contrast-indicator`. Un anillo exterior sólido, sin blur, de expansión positiva y diferente del estado inicial puede aportar el indicador. Sombras decorativas invariables no lo acreditan; sombras internas/borrosas quedan en revisión si no hay indicador válido. |
| 165 revisiones de campos de propuesta en el primer recorrido nuevo | Falso positivo de visibilidad. Chromium conserva rectángulos de inputs después de cerrar `<details>` previamente maquetados: se reprodujo rectángulo 177 × 21 y `checkVisibility() === false`. | Comprobar visibilidad nativa, opacidad e `inert`. Abrir además los disclosures mediante Enter y auditar los campos visibles en seis estados adicionales. |
| Contraste calculado sobre contenedores y etiquetas seleccionadas | Cobertura incompleta: no comprobaba correctamente todos los textos de `small`, `span`, celdas o campos agrupados; omitía opacidad de grupo. | Medir cada nodo de texto con su propietario y componer alfa/opacidad sobre fondos sólidos. Fondos con imagen/gradiente, filtros o mezcla se registran como revisión. Comparar umbrales sin redondearlos para decidir. |

## Cambios y preservación

- `basis/adapters/web/static/basis/css/app.css`: únicamente la regla de tres líneas del foco del hero se añadió en esta ejecución. Se preservaron los cambios anteriores de tokens de foco, labels clicables y enlace móvil de perfil.
- `scripts/ux_acceptance.py`: auditor asíncrono, cobertura de navegación/textarea/summary/controles con tabindex, registros `focus_checked`, `focus_review` y `contrast_review`, modo `--dom-only`, estados de propuesta expandida mediante teclado, identidad de herramientas y recibo de cierre del navegador. Se preservan los fixtures sintéticos y recorridos existentes.
- `docs/UX-VERIFICATION.md`: este informe nuevo.

Se inspeccionaron el contrato y plan UX, el roadmap local, el CSS efectivo instalado y la plantilla de progreso. La corrección previa del separador `·` se conservó y el recorrido de progreso la comprobó. No se editaron modelos, seed, pruebas de integridad, configuración, roadmap, snapshots ni documentación DEVELOPMENT. Los 24 archivos previos continúan presentes; este informe es el único archivo fuente nuevo adicional.

## Evidencia del candidato verificado

Binding de fuentes runtime/herramienta:

```text
d3ecd68ddced4c3d4bcc3de23c94be869ebdbf1847f7456d93b3fe251dc09533
```

`source-before.json` y `source-after.json` coinciden en ambos directorios siguientes. La comprobación posterior contra las fuentes actuales también coincidió. El binding heredado incluye fuentes de `basis`, `config`, dependencias y herramientas de aceptación; excluye documentación y pruebas. No es una identidad de todo el árbol Git.

| Evidencia nueva, propiedad de esta ejecución | Resultado |
| --- | --- |
| `.cache/ux-executor-dom-20261020-final2/result.json` | **VERIFIED**, alcance `LOCAL_DOM_REGRESSION_NOT_APPLICATION_ACCEPTANCE`, sin DB ni puerto. Seis combinaciones de CSS instalado + un caso adversarial con varios controles positivos/negativos; comprobación adicional de expansión por teclado de tres disclosures cerrados y uno ya abierto. |
| `.cache/ux-executor-dom-20261020-final2/dom-audits.json` | Se detectan intencionalmente seis defectos de indicador, dos sombras pendientes de revisión, dos textos de bajo contraste y un gradiente pendiente de revisión. El anillo negro sólido sobre blanco pasa a 21:1; los campos ocultos/disabled/inert no se cuentan. |
| `.cache/ux-executor-dom-20261020-final2/dom-hero-{390,768,1440}-{light,dark}.png` | Capturas del fixture DOM representativo con foco en el enlace del hero. Se inspeccionó la captura móvil clara. |
| `.cache/ux-executor-app-20261020-final2/result.json` | **VERIFIED**, alcance `APPLICATION_UX_ACCEPTANCE`: **60 combinaciones de ruta/ancho/tema + 6 estados de propuesta expandida**. **1.208 comprobaciones de foco**, 0 fallos de foco, 0 revisiones de foco, 0 fallos/revisiones de texto y 0 hallazgos de tamaño en los selectores medidos. Sin errores JavaScript `pageerror`. |
| `.cache/ux-executor-app-20261020-final2/browser-closed.json` | Navegador cerrado. `result.json` también confirma servidor detenido y binding estable. |
| `.cache/ux-executor-app-20261020-final2/*.png` | 66 capturas de la aplicación. Se inspeccionaron Hoy móvil claro y propuesta expandida móvil oscura; no se atribuye revisión visual exhaustiva a las 66. Las capturas full-page conservan elementos fixed/sticky respecto del viewport de captura. |

Herramientas efectivamente usadas: **Python 3.13.7**, **Playwright 1.64.0**, **Chromium headless shell 153.0.8010.12**, **django-cotton-ui 0.3.4**. Se reutilizaron el entorno y el navegador instalados, sin descargas. La aplicación usó exclusivamente `.cache/ux-executor-app-20261020-final2/ux.sqlite3` y `http://127.0.0.1:59279`; proceso de servidor 56288 terminado. El entorno hijo deshabilitó proveedores y SMTP. No se utilizó PostgreSQL ni un servidor ajeno.

### Recorridos reales ejecutados

1. Formulario de registro en su ruta real.
2. Hoy, planes, progreso, entrenador, perfil, preferencias, suscripción, programada, propuesta y offline a 390/768/1440 px, en claro/oscuro; seis expansiones de propuesta por teclado.
3. Tab al enlace de salto, Enter a `#main`, foco y activación del cambio de tema.
4. Reprogramación mediante POST real y comprobación de fecha persistida.
5. Creación manual de entrenamiento mediante POST real.
6. Progreso real y ausencia del antiguo separador literal `?`.
7. Tres swaps HTMX del resultado de trabajo, conservando un único resultado y enlace de revisión.
8. Revisión y aceptación de propuesta **sintética**, creación del plan real. Esto no verifica generación ni calidad de proveedor IA.

## Checks técnicos

| Check | Estado y ejecución |
| --- | --- |
| Regresión DOM del auditor | **VERIFIED**: `python -m scripts.ux_acceptance --dom-only`, recibo final2 anterior. |
| Runtime UX de rutas/POST/HTMX | **VERIFIED**: `python -m scripts.ux_acceptance`, recibo final2 anterior. |
| Ruff | **VERIFIED**: `.venv-win/Scripts/python.exe -m ruff check scripts/ux_acceptance.py`. |
| Formato Python | **VERIFIED**: `.venv-win/Scripts/python.exe -m ruff format --check scripts/ux_acceptance.py`. |
| Formato CSS | **VERIFIED**: `node_modules/.bin/prettier.cmd --check basis/adapters/web/static/basis/css/app.css`. |
| Tipado dirigido | **VERIFIED**: mypy estricto con `--config-file mypy-django.ini --cache-dir .cache/ux-executor-typecheck-20261020-final/mypy scripts/ux_acceptance.py`, entorno hijo creado con `child_environment` y DB nominal aislada sin uso. `Success: no issues found in 1 source file`. |
| Diff | **VERIFIED**: inspección de estado/diff y `git diff --check` para rutas autorizadas; script/documento nuevos se revisan directamente porque aún no están tracked. |
| Build | **NOT APPLICABLE**: CSS servido directamente; no cambia el empaquetado ni se requiere compilar recursos. |
| Gate PostgreSQL/integridad completo | **NOT RUN** por este ejecutor; responsabilidad del ejecutor paralelo. |
| Lector de pantalla / aprobación del propietario | **NOT RUN / PENDING**. |

### Intentos diagnósticos conservados

- `ux-executor-dom-20261020-01`: FAILED. La inyección de CSS en el fixture también dispara transición de color de texto; motivó estabilizar estilos antes del análisis, no relajar contraste.
- `ux-executor-dom-20261020-02` y `03`: verificaciones DOM de candidatos intermedios; no sustituyen al recibo final2.
- `ux-executor-app-20261020-01`: VERIFIED_WITH_FINDINGS de candidato intermedio, 165 revisiones por visibilidad de disclosures, resueltas y cubiertas por regresión.
- `ux-executor-app-20261020-final`: FAILED por timeout en la propia herramienta. `.all()` sobre `details:not([open])` crea locators lazy cuyo índice cambia al abrir elementos. `expand_details` ahora recorre un conjunto estable y tiene una regresión específica. El servidor de ese intento se detuvo.
- `ux-executor-dom-20261020-final`: regresión de candidato intermedio. Sólo los directorios **final2** están vinculados al hash publicado arriba.

El recibo histórico `.cache/ux-acceptance-20261020-r3/result.json` se utilizó como diagnóstico, no como evidencia del candidato actual.

## Límites y pendientes

- El auditor es un **screening DOM de colores sólidos**, no una certificación WCAG. Los ratios no prueban área/geometría completa del indicador, recorte, superposición/oclusión, todos los estados hover/error/disabled ni contraste de iconos SVG, placeholders, imágenes o pseudo-elementos.
- Se establece modalidad de teclado y se comprueba `:focus-visible`, pero el barrido de elementos usa foco programático: no certifica orden Tab completo, ausencia de trampas ni uso con tecnología asistiva. El enlace de salto, cambio de tema y disclosures sí se activaron con teclado.
- La medición de targets conserva su alcance previo; no certifica todas las excepciones/espaciados de WCAG 2.5.8. El viewport móvil no equivale a dispositivo físico.
- Pendientes de BASIS-012: revisión de comprensión/decisiones visuales por el propietario, lector de pantalla real y dispositivo físico. Offline completo, conflictos y replay corresponden además a la suite específica de navegador; aquí se visitó la ruta offline.
- Pendientes de BASIS-013: aceptación del catálogo completo y sus variantes, licencias/versiones y cobertura integral de estados/HTMX/Alpine según contrato. Tres swaps de un fragmento no equivalen a aceptar toda la biblioteca.
- Tras integrar cambios runtime del ejecutor paralelo, volver a ejecutar la aceptación bajo un **nuevo directorio** y comprobar su binding. No reutilizar este PASS si cambia el candidato.

## Comando para gate coordinado de integración

Desde la raíz, después de estabilizar las fuentes de los ejecutores:

```powershell
$out = Join-Path '.cache' ('ux-coordinated-' + [guid]::NewGuid().ToString('N'))
.venv-win/Scripts/python.exe -m scripts.ux_acceptance --output $out --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

La herramienta exige directorio nuevo, crea SQLite propia y elige puerto dinámico. Cualquier cambio de fuentes durante el recorrido invalida el resultado. Para repetir sólo los controles de medición sin DB/servidor, añadir `--dom-only` y usar otro directorio nuevo. Los artefactos de `.cache` son run-owned: conservarlos como evidencia del candidato sin limpiar recursos de otros ejecutores ni el caché de navegador compartido.
