# Goal

Avanzar BASIS-012/MAM-626 con un contrato UX verificable sobre la aplicación real y recorridos reproducibles. Conservar el estado abierto hasta resolver la revisión visual del propietario y la validación con lector de pantalla.

# Context

Partida: main `24484b7`, presentación modular con Cotton, tokens locales y aceptación de navegador histórica. El 20 de octubre de 2026 Linear mantiene BASIS-012 y BASIS-013 In Progress; la aceptación de arquitectura se reconcilia por separado.

# Constraints

Reutilizar la identidad BASIS y componentes existentes. Sin rediseño, rutas de producto nuevas, TypeScript, proveedor IA, pagos, SMTP ni base original. Datos de navegador ficticios en SQLite temporal bajo `.cache`; no presentar fixtures o resultados automatizados como aceptación humana.

# Affected areas

`docs/UX_CONTRACT.md`, documentación de marca/componentes y sección UI de arquitectura; corrección del separador literal de progreso; herramienta UX independiente usando la infraestructura de aceptación aislada. Coordinar el inventario estricto con el orquestador.

# Implementation steps

1. Registrar navegación, tareas, estados, semántica y tokens contra los criterios actuales de MAM-626.
2. Actualizar las referencias físicas obsoletas de la documentación y corregir el separador visible de progreso.
3. Ejercitar vistas reales a 390, 768 y 1440 px en ambos temas con teclado, desbordamiento, controles y contraste; guardar evidencia de tareas y capturas.
4. Registrar las brechas demostradas y la revisión pendiente; entregar evidencia al orquestador sin cerrar criterios no ejecutados.

# Required skills

`task-planning`, `safe-git-workflow`, `verify-before-complete`; `systematic-debugging` para el fallo reproducido al arrancar Edge.

# Validation

Base aislada con proveedores deshabilitados; proceso de servidor/navegador detenido; binding de fuentes antes/después; comprobaciones de formato/tipado pertinentes y render de la plantilla modificada. Revisión manual de capturas complementa el recorrido automatizado. Lector de pantalla y aprobación del propietario requieren evidencia específica.

# Risks

Edge se cierra antes de iniciar una página en el entorno actual. Chromium headless shell instalado sí supera el caso mínimo de lanzamiento; su recorrido completo se valida por separado. La matriz automatizada puede revelar brechas de contraste/tamaño que deberán documentarse o corregirse de forma acotada, sin relajar comprobaciones para obtener un resultado verde.

# Complemento portable · 23 de octubre de 2026

Boceto estático adicional: [HTML local](design/prototipo/index.html), [guía de tokens y verificación](design/STYLE_GUIDE.md) y [cinco flujos y estados](design/FLOWS.md). Se abre con `file://`, sin servidor; datos ficticios y cambios solo en memoria que se pierden al recargar/cerrar. No reemplaza la aplicación ni la evidencia histórica anterior. Fuentes entregadas con gates/capturas NOT RUN por el implementador; el coordinador ejecuta la CLI documentada tras revisar/formatear el candidato. Revisión humana PENDING y lector de pantalla NOT RUN.
