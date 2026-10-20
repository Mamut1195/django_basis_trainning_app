# Componentes generales BASIS

Los componentes propios se resuelven en `basis/adapters/web/templates/cotton/basis/` y se usan con el prefijo `c-basis`. Los componentes `c-ui` pertenecen a django-cotton-ui; sus fuentes no se modifican. Las utilidades pequeñas de espaciado, tipografía y color siguen siendo clases CSS.

| Componente | Parámetros y contenido | Estados | Ejemplo |
| --- | --- | --- | --- |
| `brand` | `href` por defecto `/`, `product` opcional, `class`; marca original con texto alternativo BASIS | Escritorio y móvil | `<c-basis.brand href="/" product="Training" />` |
| `page-heading` | `title`, `subtitle`, `eyebrow`; título de página | Texto largo, sin subtítulo | `<c-basis.page-heading title="Tu sesión" eyebrow="Hoy" />` |
| `card` | `title` opcional, slot; contenedor visual sobre `c-ui.box` | Con/sin encabezado | `<c-basis.card title="Duración">45 min</c-basis.card>` |
| `empty` | `title`, slot explicativo | Lista vacía, primera acción | `<c-basis.empty title="Aún no hay sesiones">Crea tu primera sesión.</c-basis.empty>` |
| `notice` | `tone` por defecto `info`, slot, atributos HTML | `info`/`success`/`warning`: status; `error`: alert | `<c-basis.notice tone="error">Revisa los datos.</c-basis.notice>` |
| `form-frame` | `:form`, `submit` por defecto Guardar, `:revision` opcional; slot para campos adicionales | Sin enviar, errores, ocupado, navegación de vuelta | `<c-basis.form-frame :form="form" submit="Crear cuenta" />` |
| `error-summary` | `:form`; errores globales y enlaces a los IDs reales de cada campo | Oculto sin errores; alert y foco programático con errores | `<c-basis.error-summary :form="form" />` |
| `submit-status` | Slot inicial opcional y atributos HTML | Vacío, Guardando, esperando conexión; aria-live polite | `<c-basis.submit-status />` |

Los formularios nativos siguen funcionando sin JavaScript. `forms.js` marca `aria-busy`, anuncia el envío y bloquea envíos repetidos después de serializar el nombre/valor del botón pulsado. Restaura el estado al volver desde el historial o terminar una petición HTMX. El foco llega al resumen de errores y sus enlaces llevan a campos con etiquetas y errores de Django. Los formularios especializados conservan su contenido y decisiones en cada módulo.

Los parciales privados de ejecución son `_metrics`, `_strength`, `_intervals`, `_timer` y `_blocks` en training; `_result` en coach es la respuesta HTMX; `_conflict` pertenece a sync. No son componentes generales. `app.js` coordina estado de red/tema/HTMX; `timer.js` conserva el temporizador; `updates.js` maneja la activación del service worker; `offline.js` conserva el flujo cohesivo de almacenamiento, edición, replay y conflictos por cuenta.

Revisar cambios con temas claro/oscuro, teclado y móvil. El foco visible, el resumen de errores, los botones deshabilitados y el estado de envío se verifican con el recorrido real de navegador. Las reglas nuevas se añaden al final de la cascada; no se reordenan reglas existentes.

## Relación con los recorridos UX

[UX_CONTRACT.md](UX_CONTRACT.md) vincula estos componentes con las tareas y estados de BASIS-012. El layout propietario es `basis/adapters/web/templates/shared/base.html`; tokens y comportamiento compartido viven en `basis/adapters/web/static/basis/{css,js}`. Las ocho composiciones BASIS anteriores reutilizan primitivas del kit: este inventario no declara cerrado el catálogo completo de variantes, licencias y swaps HTMX/Alpine exigido por BASIS-013.
