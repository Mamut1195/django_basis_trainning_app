# MAM-627 · Alcance y verificación Cotton

## Identidad y estado

- Ejecución: `MAM627-20261023-cotton-v1`, misma `initial implementation_round1`.
- Snapshot: `c1f486008483f1cbb478983a40ced1fa3cb7f4c6a7ecd479634266784220102f`.
- Base: `de24ce7ef686c0b990342537d7a47a6fec5274a6`.
- Rama: `ticket/MAM-627-cotton-ui`.
- Contrato UX autorizado: MAM-626 PR #15, **ronda 2 (R2)**, head `cdcbac5f1e305f2609710422aeae4e1215a4d604` (sustituye la ronda 1, `c9bc2351a25e4f6f1038cdecba837e3d5bf89e83`).
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

**Aceptación de navegador (ronda 2, resultados reales).** La corrida completa de `scripts.cotton_acceptance` (Chromium headless shell 1243, navegador 153.0.8010.12, solo Windows local) pasó por todas las etapas: `status=VERIFIED`, `stage=browser_complete`, sin errores JavaScript ni peticiones externas bloqueadas, fuentes antes/después iguales. Evidencia local: `basis-runs/MAM627-r2-acceptance-3` (y repetición `MAM627-r2-acceptance-4`); no son artefactos de CI.

Causas de los fallos previos, todas del auditor y no de la UI (diagnosticadas y corregidas en commits separados, sin relajar ratios ni omitir pruebas):

1. Asentamiento de animaciones: `SETTLE` salía tras 2 fotogramas quietos y cortaba las transiciones encadenadas de la fixture (`ended=1, opacity=0.5, active=1`; reproducido 3/3 por BT3). Ahora exige `quietFrames<4` (`settle_quiet_frames: 4`). La cadena infinita sigue rechazada por el plazo global de 1500 ms.
2. Medición de padding de tarjeta en `/coach/`: una tarjeta sin título rellena la propia tarjeta; el auditor medía el último hijo (0px). Ahora usa la caja realmente rellenada y sigue exigiendo que el padding cambie con `--space-1`.
3. Botón del kit en `/coach/`: esa página no renderiza botón mientras el proveedor IA está deshabilitado. Las aserciones de botón se aplican solo donde hay un botón (igual que las de input); catálogo, `/`, `/plans/` y `/progress/` sí lo verifican.

| Criterio | Archivo o comprobación | Estado |
| --- | --- | --- |
| Catálogo e inventario sin copiar primitivas | COMPONENTS.md, component_catalog.py, test_components.py | VERIFIED (Django); ver gates en el PR |
| Propagación de marca/tipografía/espaciado/radios a pantallas | cotton_acceptance.py, token_mutation en catálogo, `/`, `/plans/`, `/progress/`, `/coach/`, `/profile/` | VERIFIED (Chromium headless shell) |
| Temas y contraste del catálogo | matriz 390/768/1440 × claro/oscuro: 0 hallazgos de contraste, objetivos y foco; 60 paradas de teclado por combinación | VERIFIED (screening DOM, no WCAG) |
| Teclado, diálogo (apertura, trap, Escape, retorno de foco) | cotton_acceptance.py | VERIFIED |
| Diálogo: Alpine no sobrescribe `role="dialog"` ni `aria-label="Cerrar"` | comprobación nueva abierto y tras Escape | VERIFIED (menor a) |
| Swaps HTMX/Alpine, CSRF real (403, 403, 200) y guardia de origen | cotton_acceptance.py | VERIFIED |
| Service worker y caché pública PWA, API/navegación privada sin caché | cotton_acceptance.py | VERIFIED |

**El CI de GitHub NO ejecuta `cotton_acceptance`.** El workflow `checks.yml` (jobs `postgres` y `operations`) no tiene job de Chromium: un CI verde no cubre esta aceptación de navegador. Se ejecuta a mano con:
`python -B -m scripts.cotton_acceptance --output <directorio-nuevo> --browser-executable <chrome-headless-shell>`.
Solo se probó en Chromium headless shell; otros navegadores: DESCONOCIDO. No se añade job Chromium por ahora.

**revision independiente: BT2 — PENDIENTE**. Revisor externo NOT RUN por instrucción BT0; no se solicitan ni usan claves. Aprobación humana PENDING; lector de pantalla, dispositivos físicos y servicios LIVE NOT RUN. El draft no autoriza integración ni cierre. No hay cambios de dominio, modelos, migraciones o versiones de dependencias. El checker de arquitectura permanece protegido e intacto.
