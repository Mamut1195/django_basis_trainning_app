# MAM-816: preflight local de sandbox

## Resultado

**BLOCKED_EXTERNAL_CONFIGURATION / NO PROVEEDOR EJECUTADO.** El usuario confirmó continuar lo local y preparar el sandbox después. No se solicitó ni recibió ningún secreto en el chat, no se crearon endpoints ni objetos Polar y no se contactó a sus APIs.

La inspección del proceso de ejecución comprobó únicamente pertenencia de nombres a `os.environ`, sin leer o imprimir valores: `POLAR_ACCESS_TOKEN`, `POLAR_WEBHOOK_SECRET`, `POLAR_SANDBOX` y `PUBLIC_URL` están ausentes. Esto describe este proceso; no inspecciona archivos privados ni otros servicios. El catálogo de herramientas actual no mostró un conector Polar invocable.

## Contrato comprobado por lectura

`config/settings.py` recibe la configuración por entorno. Sin override, usa sandbox y URL pública loopback. `billing/adapters/polar.py` rechaza una petición sin token o producto antes de HTTP. `compose.yaml` conserva variables privadas fuera del código. Los pasos anteriores de sandbox se encuentran en `docs/POLAR_SANDBOX_VERIFICATION.md`; no se reinterpretan como ejecución actual.

## Para reanudar

Preparar privadamente `POLAR_SANDBOX=1`, `POLAR_ACCESS_TOKEN`, `POLAR_PRODUCT_ID`, `POLAR_ORGANIZATION_ID`, `POLAR_WEBHOOK_SECRET` y `PUBLIC_URL` HTTPS autorizado. No pegarlos en tickets, recibos o chat. Verificar en el proceso que ejecutará la aplicación que la configuración esté disponible, sin revelar valores.

Después: checkout por el adaptador real de la app, tarjeta y suscripción de prueba, portal, webhook firmado real, repetición/orden de entrega, conciliación y escenarios de cancelación/impago/reembolso conforme al alcance. No activar producción ni confundir un checkout-link previamente creado con ese recorrido.

**VERIFIED:** ausencia de cuatro nombres de entorno en este proceso; lectura de configuración y transporte; decisión expresa de posponer sandbox. **NOT RUN:** checkout/API/webhook/conciliación reales, pagos de prueba, estado actual de objetos remotos y cualquier operación de producción. No se cambió el estado de MAM-816.
