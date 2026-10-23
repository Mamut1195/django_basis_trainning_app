# MAM-816 - Verificación Polar Sandbox, 2026-10-23

Alcance autorizado por Jonathan (vía BT0): **solo Polar SANDBOX**, organización
"BASIS Training Sandbox" y su producto mensual existente. Producción (`polar-production`)
desactivada y no usada. No se crearon ni cambiaron objetos en Polar. No se imprimió ningún
secreto. Hora de referencia: America/Guayaquil (UTC-5).

## Resultados

| # | Verificación | Resultado | Evidencia (sin secretos) | Hora (UTC-5) |
|---|---|---|---|---|
| 1 | Default de la app es sandbox; producción exige opt-in explícito | VERIFIED | `config/settings.py`: `POLAR_SANDBOX = os.getenv("POLAR_SANDBOX", "1") == "1"`; `.env.example` y `compose.yaml` fijan `POLAR_SANDBOX=1` por defecto. `polar.py`: base `https://sandbox-api.polar.sh` si sandbox, `https://api.polar.sh` solo con `POLAR_SANDBOX!=1`. | 11:15 |
| 2 | Claves por variables de entorno, sin claves ni secretos en el repo | VERIFIED | Variables: `POLAR_ACCESS_TOKEN`, `POLAR_ORGANIZATION_ID`, `POLAR_PRODUCT_ID`, `POLAR_WEBHOOK_SECRET`, `POLAR_WEBHOOK_SECRET_FORMAT`, `POLAR_WEBHOOK_API_VERSION`, `POLAR_SANDBOX`, `PUBLIC_URL`. Búsqueda de tokens/`whsec_`/`Bearer` literales fuera de `docs/`: 0 coincidencias. Hosts `polar.sh` literales fuera de docs solo en `polar.py` (lista de hosts permitidos y URL base) y en pruebas. | 11:15 |
| 3 | Sin URL/clave LIVE configurada en el entorno de la PC | VERIFIED | Variables de Polar presentes en proceso/usuario/máquina: **NO** (las 8 listadas arriba). No hay `.env` en el worktree (solo `.env.example`). | 11:15 |
| 4 | Pruebas locales del módulo Polar (webhook firmado con secreto sintético, idempotencia, replay, estados, enlaces permitidos) | VERIFIED: 47/47, 0 omisiones | `DJANGO_SETTINGS_MODULE=config.test_settings`, PostgreSQL 18 descartable en loopback:5818 (propio, fuera de D:), variables Polar vacías. Módulos: `tests.regression.test_billing_polar`, `tests.regression.test_billing_polar_acceptance`, `basis.modules.billing.adapters.test_polar`, `basis.modules.billing.adapters.test_persistence`, `basis.bootstrap.tests.test_billing_web`. Todo con `httpx.MockTransport`/dobles: **no toca Polar**. | 11:16 |
| 5 | Lectura sandbox: organización existe | VERIFIED | GET vía MCP `polar-sandbox`: id `ff85b5fb-a8a1-4284-b92c-bea391b2adf4`, nombre "BASIS Training Sandbox", slug `basis-training-sandbox`. | 11:14 |
| 6 | Lectura sandbox: producto mensual coincide con lo que la app espera | VERIFIED | GET: id `8124146d-4811-474d-a971-1467b808ba53`, `organization_id` igual a la org, `is_archived=false`, `is_recurring=true`, `recurring_interval=month`, `recurring_interval_count=1`, `trial_interval=day`, `trial_interval_count=7`. Un precio `c355d38f-45bc-4f3e-aa95-7d8dc2bedfe0`: `recurring`, `fixed`, 500 centavos, `usd`, no archivado, `tax_behavior=exclusive`. Coincide con `POLAR_VERIFICATION.md` (conteo 1, fijo 500c USD, impuesto exclusivo, prueba day/7). | 11:14 |
| 7 | Estado previo de la organización sandbox | VERIFIED (solo lectura) | Checkouts 0, clientes 0, órdenes 0, suscripciones 0. Producto con 0 benefits y 0 meters. | 11:14 |
| 8 | Checkout de prueba por el adaptador de la app | NOT RUN | La app no tiene `POLAR_ACCESS_TOKEN` en el entorno (no se creó ni pidió un token). El MCP `polar-sandbox` **no expone `POST /v1/checkouts/`** (probado: HTTP 404 "not an operation exposed by this server"; ningún objeto creado). | 11:16 |
| 9 | Pago con tarjeta de prueba, orden y suscripción de prueba, cancelación | NOT RUN | Depende de #8. | - |
| 10 | Webhook firmado real desde Polar (firma, idempotencia, orden invertido sobre entregas reales) | NOT RUN | Depende de #8/#9 y exige endpoint webhook remoto y `PUBLIC_URL` HTTPS; crear endpoints no está autorizado. La firma e idempotencia sí están VERIFIED localmente (#4). | - |
| 11 | Conciliación `reconcile_billing` contra Customer State real | NOT RUN | Requiere token sandbox en el entorno. | - |
| 12 | LIVE / producción | NOT RUN | Desactivada por autorización; no usada. | - |
| 13 | Benefits / meters | NOT RUN (no creados) | No autorizados; el producto tiene 0 y la app no los usa (ver abajo). | - |

## Objetos creados en sandbox

Ninguno. Tipo: -, id: -, estado final: -, cancelado: no aplica (no hubo nada que cancelar).
El único intento de escritura fue `POST /v1/checkouts/` vía MCP, rechazado por el servidor
(404, operación no expuesta); no se creó objeto. Las demás operaciones fueron GET.

## Operaciones del MCP `polar-sandbox` (solo lectura de especificación)

Expone `POST /v1/checkout-links/` (otro objeto: enlace de pago reutilizable, no el
`POST /v1/checkouts/` que usa el adaptador), pero **no** `POST /v1/checkouts/`,
`POST /v1/customer-sessions/` ni `POST /v1/subscriptions/`. No se usó `checkout-links`: no
reproduce la ruta de código de la app y no estaba autorizado. Sí expone
`DELETE /v1/subscriptions/{id}` (revocar), útil si se obtiene una suscripción de prueba.

## Para completar #8 a #11 (requiere decisión de Jonathan)

1. Que Jonathan cree en el sandbox un Organization Access Token (scopes `products:read`,
   `customers:read`, `checkouts:write`, `customer_sessions:write`) y lo ponga como variable
   de entorno privada `POLAR_ACCESS_TOKEN` (con `POLAR_ORGANIZATION_ID`, `POLAR_PRODUCT_ID`,
   `POLAR_SANDBOX=1`); o
2. autorizar un checkout-link de sandbox (no equivale a la ruta de la app).

Después, el pago con tarjeta de prueba de Polar requiere navegador; si no se puede
automatizar, queda NOT RUN.

## MAM-817: ¿necesita benefits o meters en Polar?

No, según el código y la documentación del repo. Evidencia: en el worktree de MAM-817 la
búsqueda de las palabras `benefit(s)`, `meter(s)`, `meter_id`, `customer-meters` da 0
coincidencias. El contrato congelado concede acceso únicamente con suscripción
`active`/`trialing` dentro de `[period_start, period_end)` y sin conciliación pendiente
(`docs/ENTITLEMENTS_MAM817.md`), leída del Customer State de Polar; las cuotas y el fondo
mensual de IA se calculan localmente (`docs/ARCHITECTURE.md`). El producto sandbox tiene
0 benefits y 0 meters y es suficiente.