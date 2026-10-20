# Contrato UX BASIS Training

BASIS-012 / [MAM-626](https://linear.app/mamutsystems/issue/MAM-626/basis-012-disenar-flujos-ui-ux-y-contrato-visual-basado-en-tokens). Estado: entrega de contrato y prototipo real para revisión; no sustituye la aceptación del propietario ni una prueba con lector de pantalla. Identidad oficial BASIS y aplicación Django existente. Fecha: 20 de octubre de 2026.

## Prototipo portable

El prototipo navegable es la propia aplicación, con recursos locales y datos ficticios en una base descartable. No necesita OpenDesign, cuentas reales ni proveedores. Ejecutar desde la raíz del repositorio:

```powershell
.venv-win/Scripts/python.exe -m scripts.ux_acceptance --browser-executable C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe
```

La herramienta prepara la base SQLite bajo `.cache/ux-acceptance/<id>`, abre un servidor exclusivo en loopback, recorre pantallas con Chromium y conserva un resultado JSON, capturas y logs sin contraseñas. Se detienen navegador y servidor al terminar. La propuesta IA del fixture está identificada como sintética: revisar/aceptar prueba la interfaz y persistencia, nunca la calidad de una generación o una llamada al proveedor. El recorrido offline completo pertenece también a `scripts/acceptance_browser.py`; no se infiere éxito de sincronización a partir de un mensaje local.

## Navegación y tareas

El layout compartido es `basis/adapters/web/templates/shared/base.html`. Hoy, Plan, Progreso y Entrenador se mantienen en el mismo orden. En escritorio aparecen en la barra lateral; en móvil/tablet hasta 850 px, en la barra inferior. Perfil está en la cabecera; Suscripción también se alcanza desde Perfil. La navegación marca la página actual y permite saltar al contenido con teclado.

| Tarea | Recorrido real y decisión | Resultado observable |
| --- | --- | --- |
| Inicio | `/accounts/signup/` → verificación de correo → `/profile/` → editar perfil/disponibilidad → objetivo | No confundir registro, correo verificado y acceso de escritura; los formularios conservan errores y datos válidos. El correo del fixture permanece local. |
| Preparar el día | `/` → agenda programada o registrar entrenamiento | La agenda vacía ofrece una acción y las sesiones recientes muestran estado real. |
| Planificar | `/plans/` → crear plan → ciclos → programar sesión → detalle | Objetivo, fechas y versión visibles; la nueva versión conserva historia. |
| Entrenar | sesión programada → empezar → sesión de ejecución → guardar/completar | Prescripción visible por separado; registrar datos reales no rellena lo ausente con cero. |
| Reprogramar | detalle de programada → Reprogramar → nueva fecha → Guardar | La nueva fecha se persiste y el formulario lleva revisión para detectar cambios concurrentes. |
| Entender progreso | `/progress/` → adherencia, carga por protocolo, deporte, bienestar e historial de fuerza | Unidades, datos faltantes y etiquetas de estimación permanecen visibles. Exportación disponible. |
| Revisar propuesta | `/coach/` → consulta → Revisar propuesta → editar campos → aceptar/rechazar | Resumen y grupos por ciclo/sesión; aceptar crea plan o versión privada y mantiene la prescripción histórica. |
| Continuar offline | sesión → descargar → sin red → guardar → pendientes → reconectar/sincronizar | Sólo la confirmación del servidor elimina un pendiente. Conflictos permiten revisión explícita; una ejecución completada no admite sobrescritura local. |

## Estados y recuperación

| Estado | Presentación y acción | Fuente implementada |
| --- | --- | --- |
| Vacío | Explicar contexto y siguiente acción; no inventar datos, porcentaje o recomendación | `c-basis.empty`, Hoy/Plan/Progreso/Entrenador |
| Cargando | Botón ocupado/deshabilitado y anuncio de envío; un trabajo IA conserva acceso posterior | `forms.js`, `submit-status`, `coach/jobs/_result.html` |
| Error de formulario | Resumen con foco, enlaces a campos y errores junto al control; conservar entradas | `error-summary`, formularios Django |
| Servicio deshabilitado | Explicar que IA/pagos no están habilitados; no mostrar resultado de proveedor ficticio como LIVE | Entrenador y Suscripción |
| Sin red | Estado visible y datos descargados por cuenta; no prometer que todo el sitio está disponible | `offline.js`, `sync/offline/index.html` |
| Pendiente | Identificar operaciones guardadas localmente hasta confirmación; exportación local disponible | IndexedDB por cuenta y cola ordenada |
| Conflicto | Mostrar copia local/remota y elección explícita; respetar sesión completada | `sync/offline/_conflict.html` |
| Sesión cerrada | Resolver/exportar pendientes antes de purgar; invalidar sesión antes del aviso entre pestañas | Perfil y flujo de logout confirmado |

## Semántica deportiva

Prescrito y realizado son columnas o secciones distintas: `target` describe intención y `actual` registra observación. El RPE objetivo no rellena el RPE real ni la estimación. Un RM medido muestra su fecha/referencia; un e1RM se etiqueta como estimado y no modifica retroactivamente el RM de referencia. Un guion o «Sin datos» significa ausencia; cero es una medición válida cuando el contrato de la variable lo admite. Unidades y protocolo acompañan la carga: UA de minutos × RPE real no es predicción de lesiones ni equivalencia entre deportes. Estos límites se apoyan en `TRAINING_CONTRACT.md`, `TRAINING_VARIABLES.md` y `STRENGTH_METRICS.md`.

## Tokens, componentes y decisiones revisables

La fuente canónica es `basis/adapters/web/static/basis/css/tokens.css`; `identity.json` aporta marca a HTML/manifest mediante `brand.py`. `app.css` compone layouts/estados sin copiar primitivas Cotton. El tema se selecciona con `basis-theme` y clase `.dark`; el mismo markup sirve para ambos temas.

| Nivel | Ejemplos actuales | Decisión |
| --- | --- | --- |
| Primitivo | `--primitive-blue-600`, `--primitive-paper`, `--space-1`…`--space-12`, `--font-body`, `--radius-*` | Marca azul original, sistema tipográfico local y escala compartida. |
| Semántico | `--app-bg`, `--surface`, `--text`, `--muted`, `--accent`, `--danger`, `--warning` | Adaptación clara/oscura por intención; el significado no depende sólo del color. |
| Componente/layout | `--color-accent*`, `--color-box-border`, `--radius-button`, `--hero-*`, `--nav-width`, `--control-height` | Mapeo Cotton y excepciones explícitas del hero; cambiar tokens no exige rehacer pantallas. |
| Interacción | `--focus-width`, `--motion-fast`, `prefers-reduced-motion` | Foco visible, movimiento reducido y estados ocupados/deshabilitados. Revisar los valores efectivos en ambos temas. |

El inventario canónico de ocho componentes BASIS y sus estados está en [COMPONENTS.md](COMPONENTS.md). Se reutilizan primitivas `c-ui.button`/`c-ui.box`; las plantillas privadas de entrenamiento, propuestas y conflicto son compuestos de cada módulo. Las tablas de fuerza, métricas de intervalo, temporizador y diálogo de conflicto conservan su semántica y responsabilidad local; no se crea una segunda biblioteca de botones o formularios.

Decisiones para revisar con el propietario: orden estable de cuatro destinos; CTA de registro en Hoy; barra inferior móvil; información de planificación separada del registro real; estados vacíos con una acción; revisión humana de propuestas; conflictos sin sobrescritura automática; ambos temas con identidad BASIS. No se solicita aprobación de infraestructura ni proveedores mediante este prototipo.

## Matriz de aceptación y límites

| Criterio de BASIS-012 | Evidencia ejecutable | Gate restante |
| --- | --- | --- |
| Inicio/entrenamiento/reprogramación/progreso/propuesta navegables | `ux_acceptance.py` contra rutas/POST reales y fixture identificado | Revisión de tareas por el propietario; correo real fuera de este entorno |
| 390/1440 y cobertura tablet | Matriz 390/768/1440 × claro/oscuro; capturas/overflow/teclado/controles/contraste | Revisar hallazgos del resultado; dispositivo físico no ejecutado |
| Tema mediante tokens y componentes reutilizados | Mismo markup/rutas, tokens efectivos y mapeo anterior | Cambio de escala global y catálogo completo de variantes corresponden a BASIS-013 |
| Prescrito/real, estimado/medido, ausente/cero | Plantillas y contratos enlazados; captura de ejecución/progreso | Revisión de comprensión del usuario |
| Offline/pendiente/conflicto sin éxito simulado | Suite `acceptance_browser.py`: offline real, cola/replay/409 y separación de cuentas | No certifica almacenamiento duradero de un dispositivo físico |
| Teclado/lector de pantalla | Teclado automatizado, nombres/roles/foco y anuncios inspeccionables | Lector de pantalla real NOT RUN; no sustituir por auditoría DOM |
| Decisiones visuales revisables | Este contrato + inventario + capturas de la aplicación | Aceptación explícita del propietario pendiente |

No cerrar MAM-626 sólo porque el recorrido automatizado pase. Registrar los resultados actuales en `UX-VERIFICATION.md`; mantener pendientes las comprobaciones humanas y los hallazgos no resueltos. MAM-627 conserva su dependencia y tiene además catálogo completo, licencias/versiones y swaps repetidos HTMX/Alpine como aceptación propia.
