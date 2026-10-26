# BASIS · Guía breve del prototipo portable

MAM-626 · Artefacto de diseño complementario, no sustituto de la aplicación Django ni de [UX_CONTRACT](../UX_CONTRACT.md). Datos ficticios, sin cuenta, proveedor, servidor ni conexión. Abrir [prototipo/index.html](prototipo/index.html) directamente con `file://`; CSS, JavaScript clásico y SVG son locales. No hace falta instalar nada para recorrerlo.

## Fuente y jerarquía de tokens

La autoridad del producto sigue siendo `basis/adapters/web/static/basis/css/tokens.css`, `brand/identity.json`, [BRAND](../BRAND.md) y [COMPONENTS](../COMPONENTS.md). `prototipo/styles.css` es una proyección explícita para un documento sin Django; no se incorpora al runtime ni constituye una nueva biblioteca.

| Nivel | Tokens del boceto | Uso / decisión revisable |
| --- | --- | --- |
| Primitivos | `--primitive-blue-600: #0400ff`, `--primitive-blue-800: #0300cc`, blanco, tinta, pizarra, lavanda; `--primitive-slate-500: #64748b`, `--primitive-slate-400: #94a3b8` | Identidad azul oficial, nunca la paleta verde antigua. Colores oscuros adaptados, no atribuidos a un manual original de marca. |
| Tipografía | `--font-body`, `--font-xs/sm/md/lg/xl` | ui-sans-serif/system-ui local; sin descarga de fuentes. Texto base de 16 px, jerarquía y unidades visibles. |
| Espaciado | `--space-1/2/3/4/5/6/8/12` | Escala de 4 px; densidad moderada para registrar por serie en móvil. |
| Forma y elevación | `--radius-sm/md/lg`, `--shadow-soft` | Superficies discretas; sombra no comunica estado. |
| Semánticos | `--app-bg`, `--surface`, `--text`, `--muted`, `--border`, `--control-border`, `--accent`, `--accent-strong`, `--accent-soft`, `--on-accent`, `--warning`, `--danger` | Intención en vez de color en cada componente. `--border` conserva separadores decorativos; `--control-border` usa slate500 claro / slate400 oscuro solo en bordes de controles interactivos. Advertencias y errores tienen texto, no solo color. |
| Foco / movimiento | `--focus`, `--focus-width: 3px`, `--focus-gap: 3px`, `--hero-focus`, `--motion-fast` | Outline sólido; excepción semántica de foco blanco dentro del hero azul. `input[type="date"]:focus-within` comparte la regla y tokens de `:focus-visible` para cubrir también el botón nativo del calendario. No hay animación necesaria; movimiento reducido lleva la duración a cero. |
| Componente/layout | `--control-height: 2.8rem`, `--nav-width`, `--content-width`, `--radius-button`, `--radius-box`, `--color-box-border` | Controles de al menos 44 px en ambos ejes. Alias preparados para el mapeo Cotton; no se carga Cotton dentro del HTML portable. |
| Hero / marca | `--hero-background/foreground`, `--brand-background` | Hero azul oscuro y logo claro sobre azul en ambos temas. El SVG local conserva el vector oficial; no se redibuja ni se reconstruye la palabra BASIS. |

El tema cambia únicamente `data-theme` y un bloque de variables en `:root[data-theme="dark"]`, más `color-scheme` para controles nativos. No hay reglas oscuras por componente ni estilos inyectados desde JavaScript. Los breakpoints cambian layout, no la paleta. Diferencias locales declaradas: papel `#f8fafc`, separador decorativo claro `#cbd5e1`, bordes de control `#64748b` / `#94a3b8`, advertencia oscura `#8a3b12`, título más grande y foco neutro; se pueden revertir sin cambiar markup ni lógica.

## Inventario y reutilización

El prototipo imita la semántica de las composiciones existentes; no puede instanciar etiquetas Django/Cotton en `file://`.

| Boceto HTML | Correspondencia existente | Alcance |
| --- | --- | --- |
| Marca local y navegación estable | `c-basis.brand`, `shared/base.html` | Logo canónico de `basis/adapters/web/static/basis/brand/logo.svg`, copia en `prototipo/assets/logo.svg`. Hoy / Plan / Progreso / Entrenador en ese orden; lateral escritorio, inferior móvil. |
| Encabezado de página | `c-basis.page-heading` | Eyebrow, título único y descripción. |
| Tarjeta y botones/enlaces | `c-basis.card` → `c-ui.box`; `c-ui.button` | Primitivas visuales y controles nativos, sin importar ni duplicar el paquete Cotton. |
| Vacío / avisos | `c-basis.empty`, `c-basis.notice` | Contexto, siguiente acción y estado explícito. |
| Formularios y anuncios | `c-basis.form-frame`, `c-basis.submit-status` | Labels nativos, validación HTML y región `role=status`, `aria-live=polite`. |
| Error | `c-basis.error-summary` | Aquí solo un error ilustrativo global con recuperación; no se afirma paridad con los errores Django de servidor. |

Composiciones deportivas que **no** se declaran nuevos componentes generales terminados: editor por serie (prescrito/realizado), comparativa estimado/medido, resumen de observaciones ausentes/cero, comparación de versiones y conflicto, revisión de propuesta IA. El runtime ya tiene parciales privados `_strength`, `_metrics`, `_intervals`, `_blocks`, `_conflict` y revisión de propuestas. Extraer un componente deportivo reutilizable con todos sus estados sigue siendo una decisión futura; este boceto no completa el catálogo MAM-627.

## Semántica e interacción

- Prescripción A congelada por serie: 8 rep, 40 kg, RPE 7, RIR 3. Los campos reales empiezan vacíos; RPE y RIR son independientes, sin conversiones. Cardio estimado separado de duración/distancia medidas.
- «Sin datos» significa ausencia; `0` conserva una observación ficticia de cero. No hay cálculos de e1RM, adherencia, carga interna, GPS ni sensores. El historial fijo se identifica como ilustrativo y se separa del registro de la pestaña.
- El registro de la sesión A es una copia de ejemplo: aceptar el futuro plan B no transforma esa prescripción ni sus observaciones. El usuario ve esa separación; consultar no equivale a aceptar.
- Formularios y aceptación solo cambian memoria. Aviso persistente de pérdida al recargar/cerrar. No fetch, IndexedDB, localStorage, cookies, service worker, cola ni éxito remoto simulado.
- El selector muestra estados deliberados, no detecta conectividad. Vacío/carga ocultan resultados; error/conflicto bloquean acciones de escritura. Offline/pendiente permiten ensayar memoria, sin prometer durabilidad ni sincronización.
- Hashes locales y foco al contenido tras navegación. Enlaces de navegación siguen disponibles durante los estados. Sin modales ni trampas de teclado intencionadas.

## Verificación reproducible · NOT RUN en esta entrega de fuentes

No se ejecutaron gates ni se generaron capturas por el implementador. El coordinador debe revisar primero `verify_prototype.py`, aplicar el Prettier fijado y ejecutar el auditor sobre las fuentes definitivas. Ejemplo desde la raíz, usando exclusivamente el entorno y Chromium ya instalados:

```powershell
.venv-win/Scripts/python.exe -B docs/design/verify_prototype.py --output docs/design/capturas --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

`--output` debe ser nuevo: no sobrescribe evidencia. Para repetir, usar otro directorio. No instala navegador, no usa pytest, no arranca servidor. Emite `report.json` (también ante errores de ejecución), cuatro PNG `hoy-{390,1440}-{light,dark}.png` si el recorrido alcanza esos estados y un código distinto de cero ante fallo o pintura no soportada. No interpretar PNG ausentes, dependencias ausentes ni un informe parcial como PASS.

El informe liga hashes antes/después de fuentes, logo canónico y auditor; registra versiones Python/Playwright/Chromium. Ejecuta regresiones negativas del propio medidor, cinco recorridos, selección de siete estados y una matriz de **140 auditorías DOM** (5 vistas × 7 estados × 2 temas × 2 anchos). Registra texto real, controles, nombres, tamaños, overflow y recorrido Tab/Shift+Tab con foco. Calcula contraste sRGB sobre colores sólidos compuestos: umbral de texto 4.5:1 o 3:1 para texto grande; foco 3:1 sin redondear. En cada input/select visible y habilitado registra los cuatro bordes sólidos y sus ratios frente al fondo del control y al padre adyacente, ambos con mínimo 3:1; incluye una regresión negativa de borde tenue. Cada parada Tab conserva `focusVisible` y `focusWithin`: solo una fecha nativa puede usar `focusWithin` como elegibilidad alternativa, sin omitir ninguna parada ni eximir outline opaco sólido de 3 px, separación de 3 px o contraste. Se conservan el límite finito de paradas nativas y las regresiones de foco invisible, trampa de fecha y repetición no consecutiva. Pinta no soportada bloquea un resultado limpio. El informe distingue auditoría DOM de captura: solo hay cuatro PNG de Hoy, no 140 capturas ni una revisión visual exhaustiva.

### Límites y aceptación pendiente

| Validación | Estado de esta entrega |
| --- | --- |
| Auditor portable / regresiones / contraste / teclado automatizados | NOT RUN; instrucciones anteriores, resultados futuros en `report.json` |
| Formato fijado y gates de proyecto | NOT RUN por el implementador; coordinador |
| Revisión semántica/visual independiente de candidato exacto | PENDING |
| Aprobación del propietario sobre tareas, marca y decisiones | PENDING |
| Lector de pantalla real y dispositivo físico | NOT RUN |
| Persistencia, sincronización, backend, calidad deportiva IA | Fuera de alcance del boceto; no acreditados |

Screening no equivale a certificación WCAG: no mide píxeles de SVG, pseudo-elementos, placeholder, todos los estados hover/disabled, área completa o recorte del foco, oclusión por barra móvil ni tecnología asistiva. Revisar capturas y probar físicamente tamaño de texto, zoom, navegación, comprensión de RPE/RIR, estados y contraste efectivo. Las decisiones de orden de destinos, barra inferior, densidad de series, tamaño del hero y separación de plan/registro son reversibles en este artefacto. Nada de esto autoriza cerrar MAM-626.

## Resultado coordinado posterior · 23 de octubre de 2026

La sección NOT RUN anterior registra la entrega inicial de fuentes, no el estado posterior. La preparación automatizada del coordinador ya está **VERIFIED**: 140 combinaciones DOM/teclado, cinco recorridos, cuatro PNG y regresiones negativas; resultados, hashes y límites en [VERIFICATION.md](VERIFICATION.md). `capturas/` ya existe: para repetir use un directorio nuevo como `.cache/mam626-ux-nuevo`, sin sobrescribir ni borrar evidencia. La aceptación del propietario sigue **PENDING** y lector de pantalla/dispositivo físico **NOT RUN**. El PR registra separadamente los gates finales y la revisión independiente; no se cierra MAM-626.

## R2 · Sesión primero y registro rápido · NOT RUN

Esta revisión sustituye las decisiones de hero/densidad y los objetivos de verificación anteriores; el resultado de 140 auditorías pertenece a R1, **no acredita R2**. Se mantiene la identidad y el tema por tokens: escala 4/8 px, `--font-xs/sm: 0.875rem` (labels >=14 px), `--control-height: 3rem`, `--mobile-nav-height: 5rem`. Texto >=4.5:1 incluso grande; foco opaco 3 px + 3 px de separación y controles >=44 px, checks por serie >=48 px. Un borde izquierdo decorativo por superficie, no cajas anidadas; los bordes funcionales siguen sujetos a contraste.

- **Hoy:** resumen de sesión como primer contenido y único Comenzar dominante de ancho completo; sesión y CTA deben caber sobre la navegación fija a 390×844 sin scroll. Resumen semanal compacto; herramientas/selector demo en disclosure cerrado, avisos de estado fuera. Cuatro destinos con icono + texto; margen de scroll y 6 px libres para foco, sin controles enfocados cubiertos por la barra.
- **Registro rápido:** tabla semántica kg/reps/RPE; anterior ficticio separado de entradas reales vacías. Prescripción y RIR opcional por disclosure nativo. Pendiente/Realizada y `aria-pressed`; marcar exige datos válidos, bloquea edición hasta desmarcar e inicia descanso ilustrativo de 90 s, uno solo, retenido al navegar y omitible. Nunca marca otra serie ni envía al terminar. No recomendación deportiva.
- **Plan y onboarding:** franja de siete días; fecha oculta hasta Reprogramar, cancelar descarta y aplicar actualiza el futuro plan. Bienvenida/registro navegables; labels y validación cliente obligatoria, datos inventados, contraseña ficticia >=8 y mayoría de edad. Resultado exclusivamente en memoria: NO cuenta, NO correo, NO servidor; contraseña borrada, no mostrada, persistida ni incluida en evidencia.
- **Objetivo del auditor R2 (NOT RUN):** 196 combinaciones base (7 rutas × 7 estados × 2 temas × 2 anchos) + 28 disclosures expandidos = **224 auditorías mínimo**, conservando regresiones negativas/fecha nativa y añadiendo geometría de foco y reloj Playwright (sin espera de 90 s). Diez PNG obligatorios en raíz de salida nueva: `hoy-{390,1440}-{light,dark}.png`, `plan-390-{light,dark}.png`, `onboarding-390-{light,dark}.png` (bienvenida), `registro-390-{light,dark}.png`, con herramientas cerradas y sin contraseñas. No son aprobación visual humana.

Gates, formato, capturas e informe R2: **NOT RUN por este implementador**, pendientes del coordinador sobre candidato exacto. BT2 independiente **PENDING**; validación externa/humana, lector de pantalla y dispositivo físico **NOT RUN** para R2. Un fallo de exposición o geometría requiere corrección de UI por el coordinador, nunca rebajar el auditor. Estas composiciones siguen siendo privadas del boceto, sin nuevos componentes Cotton/runtime ni cierre de ticket.

### Readback R2 del coordinador

La asignación de fuentes anterior no ejecutó pruebas, pero el coordinador ya obtuvo preparación **VERIFIED**: 224 auditorías, diez capturas, onboarding y descanso automático comprobados con reloj virtual. Véase [VERIFICATION.md](VERIFICATION.md), sección R2, para resultados, hashes y límites. Los enlaces de texto también tienen target de 48 px y el scroll-margin se aplica en escritorio además del móvil para dejar libre el outline; se preservan todos los umbrales. El PR registra la batería final y CI del nuevo SHA, no el verde de R1. **revision independiente: BT2 PENDIENTE; revisor externo/aprobación humana/lector de pantalla/dispositivo NOT RUN.**
