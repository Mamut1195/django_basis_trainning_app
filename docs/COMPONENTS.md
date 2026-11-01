# Componentes generales BASIS y catálogo Cotton

## Propiedad, versiones y licencia

Las composiciones propias viven en `basis/adapters/web/templates/cotton/basis/`
y usan `c-basis`. Las primitivas `c-ui` pertenecen a **django-cotton-ui 0.3.4**;
no se copian ni se modifican sus plantillas. Entorno instalado: django-cotton
**2.8.0**, Django **5.2.18**. METADATA de Cotton UI requiere Django >=4.2,<7.0 y
django-cotton >=2.5.0; estas versiones satisfacen esos rangos, no acreditan toda
combinación posible. El kit requiere su CSS/JS y Alpine; `shared/base.html`
carga el kit antes de Alpine, con los plugins collapse/focus locales. No se
instala otro runtime ni se inicializa Alpine manualmente tras swaps.

Licencia MIT, Copyright (c) 2024 Will Abbott. Texto instalado conservado en
`basis/adapters/web/static/vendor/LICENSE-cotton-ui.txt`. Procedencia: dist-info
`METADATA`, `RECORD`, `licenses/LICENSE` y referencia congelada de PyPI 0.3.4
verificada el 23-10-2026. No hay cambio de dependencias. La primitiva instalada
es **`c-ui.card`**, no `c-ui.box`; algunos nombres de variables del kit conservan
`box` como alias histórico, no como componente disponible.

## Inventario completo instalado: 41 familias raíz

Fuente del inventario: `django_cotton_ui-0.3.4.dist-info/RECORD`, rutas
`django_cotton_ui/templates/cotton/ui/`. Una familia agrupa sus subcomponentes;
`impl` es implementación interna, no una primitiva adicional. **Integrada**
significa utilizada por BASIS o por el catálogo de desarrollo, no que todos sus
parámetros hayan sido probados. **Diferida** significa instalada pero no adoptada
como contrato BASIS; no se declara una variante ni soporte funcional no comprobado.

| # | Familia `c-ui` | Estado y uso / motivo de diferir |
| --- | --- | --- |
| 1 | accordion (item) | Diferida; no sustituye parciales deportivos privados. |
| 2 | alert | Integrada en catálogo: cuatro tonos por tres apariencias. |
| 3 | avatar (group) | Diferida; sin necesidad de identidad visual adicional. |
| 4 | badge | Diferida; el estado BASIS existente usa texto/pill. |
| 5 | breadcrumbs (item) | Diferida; navegación principal existente conservada. |
| 6 | button | Integrada en pantallas y catálogo; matriz descrita abajo. |
| 7 | calendar | Diferida; no cambia fechas ni registro deportivo. |
| 8 | card | Integrada mediante `c-basis.card` y directamente en catálogo. |
| 9 | checkbox (group) | Diferida; formularios Django/nativos conservados. |
| 10 | collapse | Integrada en fragmento HTMX, apertura/cierre Alpine. |
| 11 | combobox | Diferida; no se migra selección de dominio. |
| 12 | composer | Diferida; no se reemplaza el formulario del entrenador. |
| 13 | datepicker | Diferida; controles nativos de fecha conservados. |
| 14 | description | Diferida; ayuda Django existente conservada. |
| 15 | dialog (title, description) | Integrada en catálogo, teclado/Escape/retorno de foco. |
| 16 | drawer | Diferida; no sustituye navegación móvil. |
| 17 | dropdown (group, item, separator) | Diferida; sin menú nuevo. |
| 18 | error | Diferida; errores Django y resumen BASIS conservados. |
| 19 | field | Diferida; no se migran todos los formularios. |
| 20 | input | Integrada en catálogo; normal, disabled y error ilustrativo. |
| 21 | label | Diferida; etiquetas HTML/Django conservadas. |
| 22 | menu (content, group, item, search, trigger) | Diferida; sin nueva navegación. |
| 23 | mode_toggle (head) | Diferida; tema BASIS ya tiene propietario. |
| 24 | nav (item) | Integrada en catálogo; enlaces a secciones. |
| 25 | navbar (item) | Diferida; layout BASIS existente conservado. |
| 26 | navlist (group, item) | Diferida; no duplica destinos principales. |
| 27 | pagination (ellipsis, item, next, prev) | Diferida; sin listado paginado nuevo. |
| 28 | popover | Diferida; sin interacción nueva de dominio. |
| 29 | progress | Diferida; no cambia métricas deportivas. |
| 30 | radio (group) | Diferida; controles nativos conservados. |
| 31 | range | Diferida; sin magnitudes nuevas. |
| 32 | scrollspy | Diferida; enlaces de catálogo sin seguimiento automático. |
| 33 | select (native, option, listbox y subcomponentes) | Diferida; selección nativa existente conservada. |
| 34 | spinner | Diferida; carga explícita con botón disabled y texto. |
| 35 | switch | Diferida; no duplica toggle de tema. |
| 36 | table | Integrada en catálogo; cabeceras, caption y datos ficticios. |
| 37 | tabs (tab) | Diferida; no cambia navegación/estado de pantallas. |
| 38 | textarea | Diferida; widgets Django existentes conservados. |
| 39 | theme_builder_widget | Diferida; herramienta del kit, no editor BASIS. |
| 40 | toast (container) | Diferida; regiones status/notice existentes conservadas. |
| 41 | tooltip | Diferida; no es requisito para comprender controles. |

Este inventario no es un segundo registro de componentes ni un conjunto de
wrappers vacíos. No promete demostraciones de las 33 familias diferidas.

## Parámetros y estados verificados de las familias integradas

Las enumeraciones siguientes proceden de las plantillas instaladas. No se
extrapolan nombres de variantes desde otros kits ni desde versiones posteriores.

- `button`: `variant=default|primary|subtle|danger|ghost|text` (default: `default`),
  `size=xs|sm|md|lg|xl|2xl` (default: `md`), `outlined` booleano (default falso),
  `href` opcional convierte el control en enlace, `class`, atributos y slot.
  El catálogo muestra 36 combinaciones variante/tamaño, un outlined y un disabled
  por variante, más carga con `aria-busy`. `disabled` es atributo de botón nativo,
  no inhabilita automáticamente un enlace con `href`. Los controles mantienen
  el mínimo BASIS de tamaño aunque el kit ofrezca `xs`.
- `card`: `variant=raised|outline` (default `raised`),
  `padding=none|xs|sm|md|lg|xl|2xl` (default `md`), `title`, `subheading`, slot
  `header`, cuerpo y `class`. Catálogo: raised con encabezado y outline con
  padding sm; no se afirma haber recorrido cada padding.
- `alert`: `variant=info|success|warning|error`,
  `appearance=soft|solid|outline`, `title`, `icon` (default verdadero),
  `dismissible` (default falso), slot y atributos. Catálogo: las doce combinaciones
  con icono desactivado y sin dismissal; dismissal no se declara probado.
- `input`: el catálogo usa `id`, `name`, `value`, `disabled` y atributos ARIA,
  con etiquetas nativas. Error ilustrativo `aria-invalid`/`aria-describedby`;
  no es un componente Django ni un contrato de variantes inventado.
- `nav`/`nav.item`: enlaces `href` a secciones y nombre accesible de navegación.
- `table`: slot de tabla HTML con caption, thead/tbody y scope de cabeceras.
- `dialog`: trigger, header, `dialog.title`, `dialog.description` y cuerpo;
  el cierre del kit se localiza a «Cerrar» sin copiar la primitiva.
- `collapse`: slot trigger y cuerpo, estado Alpine del propio kit; se vuelve a
  probar después de sustituciones reales del fragmento.

## Composiciones BASIS existentes

| Componente | Parámetros y contenido | Estados |
| --- | --- | --- |
| `brand` | `href` (default `/`), `product` opcional, `class`; logo canónico con alternativa BASIS | Escritorio/móvil |
| `page-heading` | `title`, `subtitle`, `eyebrow` | Texto largo, sin subtítulo |
| `card` | `title` opcional y slot; composición sobre **`c-ui.card`** | Con/sin encabezado |
| `empty` | `title` y explicación en slot | Lista vacía, primera acción |
| `notice` | `tone` (default `info`), slot, atributos | info/success/warning: status; error: alert |
| `form-frame` | `:form`, `submit` (default Guardar), `:revision` opcional, slot | Inicial, errores, ocupado, volver |
| `error-summary` | `:form`, errores globales y enlaces a IDs reales | Oculto sin errores; alert/foco con errores |
| `submit-status` | Slot inicial opcional y atributos | Vacío, Guardando, espera de conexión; aria-live polite |

Ejemplos: `<c-basis.card title="Duración">45 min</c-basis.card>` y
`<c-basis.form-frame :form="form" submit="Validar ejemplo" />`.
Los formularios siguen funcionando sin JavaScript. `forms.js` anuncia el envío,
marca `aria-busy`, impide duplicados después de serializar el botón pulsado y
restaura estado tras historial/HTMX. El foco va al resumen y sus enlaces al campo.
No se han migrado formularios de dominio a nuevos widgets.

## Catálogo de desarrollo y propiedad del estado

`/ui/components/` permite GET y POST sintéticos, sin persistencia ni proveedores.
`/ui/components/fragment/` solo GET. Ambas rutas devuelven 404 con DEBUG falso y
no-store. El POST usa middleware CSRF real, formulario Django y resumen de errores;
no hay `csrf_exempt`. `app.js` solo añade CSRF a HTMX same-origin y cancela
solicitudes externas. La sesión no se crea para el catálogo anónimo.

El padre `#interactions` conserva su contador; cada `outerHTML` reemplaza solo
`#component-fragment`, cuyo `x-data` propio debe reiniciar el hijo a cero.
Alpine observa el DOM y posee la inicialización; no hay `Alpine.initTree` manual.
El botón hijo hereda el estado y no necesita poseer `_x_dataStack` propio. La
prueba espera el root inicializado y luego demuestra clicks unitarios y collapse
operativo tras tres swaps HTTP reales; no basta comparar markup.

Los parciales `_metrics`, `_strength`, `_intervals`, `_timer`, `_blocks`,
`_result` y `_conflict` siguen siendo privados del módulo, no familias generales.
`timer.js`, `updates.js` y `offline.js` conservan sus responsabilidades actuales.

## Tokens, temas y verificación

Autoridad: `tokens.css` y marca canónica, no un tema paralelo. La cascada sigue
kit CSS → tokens BASIS → app CSS. Alias públicos Cotton/Tailwind conectan
`--font-sans`, `--text-*`, `--spacing`, radios button/control/box, superficies,
accent y focus con `--font-*`, `--space-*`, `--radius-*` y roles BASIS. Las reglas
propias de app usan esos tokens sin reordenar la cascada. `:root.dark` cambia
roles semánticos, no plantillas. Separadores decorativos y bordes de control
permanecen distintos; el foco usa 3 px y separación 3 px.

El gate `browser` ejecuta `scripts/cotton_acceptance.py`: matriz 390/768/1440 en
claro/oscuro, teclado real, screening DOM de contraste/foco, mutación/restauración
de tokens en catálogo y cinco pantallas principales, CSRF HTTP, HTMX/Alpine,
diálogo y caché pública del service worker sin conexión. No se cachea HTML privado
ni API. El reporte liga fuentes y PNG por SHA-256. Alcance, estado honesto de gates
y límites en [COTTON-VERIFICATION.md](COTTON-VERIFICATION.md). Screening automatizado
no equivale a certificación WCAG, revisión visual independiente ni aceptación.

[UX_CONTRACT.md](UX_CONTRACT.md) sigue gobernando tareas y estados. El contrato
MAM-626 se usa como referencia, no se reabre ni se modifica su prototipo.
