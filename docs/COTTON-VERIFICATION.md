# MAM-627 · Alcance y verificación Cotton

## Identidad y estado

- Ejecución: `MAM627-20261023-cotton-v1`, misma `initial implementation_round1`.
- Snapshot: `c1f486008483f1cbb478983a40ced1fa3cb7f4c6a7ecd479634266784220102f`.
- Base: `de24ce7ef686c0b990342537d7a47a6fec5274a6`.
- Rama: `ticket/MAM-627-cotton-ui`.
- Contrato UX autorizado: MAM626 PR15 `c9bc2351a25e4f6f1038cdecba837e3d5bf89e83`.
- Riesgo congelado 2; MATH OFF; METHOD NONE. Sin cambio deportivo ni de dependencias.

Esta página describe las fuentes y el protocolo, **no certifica el candidato**.
El bloqueo histórico de atribución del gate architecture quedó conciliado en el
snapshot actual: es git-sensitive y debe repetirse tras cambios Git. No se ha
alterado su checker ni se reabre la decisión. La continuación conserva el formato
Ruff/djLint/Prettier aplicado por el coordinador.

## Alcance implementado

- Inventario de las 41 familias raíz instaladas de django-cotton-ui 0.3.4,
  integrado frente a diferido y parámetros realmente verificados en
  [COMPONENTS.md](COMPONENTS.md). Sin duplicación de primitivas ni wrappers vacíos.
- MIT instalado conservado en `static/vendor/LICENSE-cotton-ui.txt`.
- Catálogo anónimo, sintético, no persistente `/ui/components/` y fragmento GET;
  DEBUG falso devuelve 404. No-store; POST con middleware CSRF y errores Django.
- Matriz de botones, tarjetas, alertas, vacío/carga/error, input, tabla,
  navegación, collapse y diálogo del kit; composiciones BASIS existentes reutilizadas.
- Alias de tokens tipográficos, espaciado, radios, colores semánticos, bordes y
  foco; tema claro/oscuro sin editar plantillas ni alterar identidad canónica.
- Guardia HTMX same-origin para CSRF; Alpine es único propietario de inicialización.
  El padre sobrevive a tres swaps, cada hijo vuelve a cero y suma una vez por click.

## Gates y atribución exacta

| Gate / revisión | Estado de la entrega de fuentes |
| --- | --- |
| lint, format-python, format-html, format-assets | NOT RUN sobre las fuentes finales; coordinador |
| django-check, tests, architecture, mypy-core, mypy-django | NOT RUN sobre las fuentes finales; coordinador |
| browser | Ejecución dirigida por implementador; consultar exclusivamente el registro firmado y sus result.json/browser-result.json para resultado y candidato exactos |
| Revisión BT2 independiente | PENDING |
| Revisor externo | NOT RUN según autorización |
| Lector de pantalla real / dispositivo físico | NOT RUN |
| Aceptación del propietario | PENDING |

El coordinador informa que el proceso anterior completó 439 tests (62 skipped)
y mypy de 368 archivos, antes de esta continuación. Es contexto histórico, **no
PASS de las fuentes finales**. El intento browser previo falló esperando
`_x_dataStack` en el botón hijo: el estado pertenece al root `#component-fragment`.
La corrección espera el root y conserva las aserciones de comportamiento.
No se infiere aceptación de un archivo generado, una captura o un test anterior.

Los únicos comandos ejecutables son los gate IDs congelados. Tras estabilizar y
formatear el candidato, el coordinador debe ejecutar todos los gates finales y
atar los registros al hash exacto. Architecture depende de HEAD/HEAD^ e inventario
Git; no reutilizar su resultado tras staging/commit sin recheck.

## Evidencia de navegador reproducible

Gate `browser`: `python -B -m scripts.cotton_acceptance --output {OUTPUT}
--browser-executable <Chromium instalado y fijado en snapshot>`. No descarga ni
provisiona herramientas. Directorio nuevo y exclusivo fuera del worktree,
SQLite exclusiva `.cache/mam627-<uuid>/cotton.sqlite3`, servidor loopback propio
sin autoreload, proveedores/SMTP deshabilitados. Conserva DB y evidencia;
termina servidor y cierra navegador/contexto incluso ante fallo ordinario.

El worker ejecuta:

1. Controles analíticos independientes de screening: texto negro/blanco 21:1 y
   bajo contraste; teclado con disabled/hidden/inert/details cerrado; rechaza
   animación infinita y espera transición finita.
2. Catálogo a 390/768/1440 px, claro/oscuro, fuentes y animaciones asentadas,
   overflow, Tab/Shift+Tab real, cobertura de paradas elegibles y foco visible.
   Screening de texto (4.5:1 o 3:1 grande), foco y tamaños; bordes habilitados
   con mínimo 3:1 frente al fondo del control, sin redondear.
3. Mutación computada y restauración exacta de tipografía, spacing, radios y
   fondo en catálogo, Hoy, Plan, Progreso, Entrenador y Perfil.
4. CSRF HTTP rechazado sin token/con token inválido y aceptado con token real;
   envío inválido, foco del resumen y enlace al campo; tres swaps HTTP,
   contador padre conservado, hijo reiniciado y listener único por comportamiento.
5. Apertura del diálogo con teclado, foco contenido, Escape y retorno al trigger;
   guardia de origen HTMX; ausencia de errores JS/peticiones externas.
6. Service worker real: inventario solo público, 18 recursos estáticos más
   `/offline/`; igualdad SHA-256 de recursos obtenidos online/offline, API privada
   rechazada sin conexión y navegación privada sustituida por shell público.

Se generan hasta seis `catalog-{ancho}-{tema}.png`, `catalog-errors.png`,
`catalog-dialog.png` y `offline-public-shell.png`, según avance real. Los reportes
incluyen mapa SHA-256 de PNG existentes después de capturarlos; los artefactos
sellados son `result.json` y `browser-result.json`. El reporte registra versiones,
hashes de fuentes antes/después, resultado, errores y cierre de procesos. Un PNG
ausente o un resultado parcial no acredita la matriz completa. El resultado
firmado del gate, no esta documentación estática, determina PASS/FAIL.

## Límites y pendientes

Screening DOM no es certificación WCAG ni auditoría exhaustiva de píxeles:
no cubre todo hover/disabled, SVG, pseudo-elementos, placeholder, recorte/oclusión
de foco, zoom, lectores de pantalla o dispositivos físicos. Las 33 familias
instaladas pero diferidas no se declaran probadas ni integradas. No se migran
formularios deportivos, no se cambian métricas, persistencia ni sincronización.
El cache offline comprueba recursos públicos, no aprueba offline privado.

Pendientes: formato y gates finales del coordinador, revisión independiente BT2,
revisión visual de capturas exactas y aceptación del propietario. Sin integración,
publicación, sincronización, cierre ni mutaciones Git por el implementador.

## Continuación y entrega DRAFT · 23 de octubre de 2026

La ejecución conserva implementación round 1, fix round 0 y review round 0. El snapshot más reciente al preparar esta entrega es `d8efd5502ce7c04f71232ed61236433a55a5af231f8fa8d58f31642e5bb47183`; las revisiones son explícitas y conservan el historial en `basis-runs/MAM627-20261023-cotton-v1`.

Hallazgos diagnosticados sin modificar el kit ni debilitar ratios: el auditor antiguo interpretaba OKLCH como canales RGB; el auditor Cotton normaliza colores con el motor del navegador y rechaza los no soportados/fuera de gamut. Los avisos del catálogo tienen mapeo sRGB semántico en tokens. El controlador instalado del diálogo no asigna role=dialog; la composición de accesibilidad del catálogo añade ese rol al contenedor interno y conserva apertura/trap/Escape del kit. Se distingue tipografía heredada de controles frente a las utilidades del kit.

**BLOQUEO DE ACEPTACIÓN: browser FAILED.** El último intento antes de los gates finales falló en la regresión de transiciones finitas encadenadas del auditor: `ended=1`, `opacity=0.5`, `transform=matrix(1,0,0,1,0,0)`, `active=1`. No se omite esa regresión ni se afirma PASS. Las seis capturas y el avance por CSRF y tres swaps de candidatos anteriores son evidencia histórica, no validación integral de estas fuentes. Los resultados finales, comandos y CI del SHA publicado se registran en el PR draft; esta página no los anticipa.

| Criterio | Archivo o comprobación | Estado antes del readback final |
| --- | --- | --- |
| Catálogo e inventario sin copiar primitivas | COMPONENTS.md, component_catalog.py, test_components.py | Fuentes completas; gate Django por confirmar |
| Propagación de marca/tipografía/espaciado/radios a pantallas | cotton_acceptance.py, token_mutation | NOT RUN integral del candidato final |
| Temas y contraste del catálogo | cotton_acceptance.py, matriz seis combinaciones | FAILED gate global; candidatos anteriores no acreditan el final |
| Móvil/tablet/escritorio y teclado | cotton_acceptance.py | NOT RUN integral del candidato final |
| Swaps HTMX/Alpine y caché pública PWA | cotton_acceptance.py | NOT RUN integral del candidato final |

**revision independiente: BT2 — PENDIENTE**. Revisor externo NOT RUN por instrucción BT0; no se solicitan ni usan claves. Aprobación humana PENDING; lector de pantalla, dispositivos físicos y servicios LIVE NOT RUN. El draft no autoriza integración ni cierre. No hay cambios de dominio, modelos, migraciones o versiones de dependencias. El checker de arquitectura permanece protegido e intacto.
