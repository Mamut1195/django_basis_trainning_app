# MAM-816 — Auditoría de cobertura Polar, 2026-10-23

## Objetivo

Auditar la integración ya incorporada por PR #11 y completar únicamente evidencia
local faltante. **Esta entrega añade pruebas y documentación; no modifica runtime,
UI, contratos públicos, configuración, migraciones ni dependencias.** No certifica
operación de Polar ni cierra MAM-816.

## Contexto

- Base: `de24ce7ef686c0b990342537d7a47a6fec5274a6`.
- Commit de pruebas comprobado: `ca7baa9670f7e17626db8cbbd258b58d7e503099`.
- Rama: `ticket/MAM-816-polar`, dentro del worktree exclusivo MAM-816.
- Contrato conservado: [POLAR_VERIFICATION.md](POLAR_VERIFICATION.md), API 2026-10.
  No se ha seleccionado el esquema MCP 2027-01 ni cambiado la política de reembolsos.
- Se leyeron COMMON.md, MAM-816.md y AUTH-LOTE1.md; no existía
  `basis-runs/REVIEW-MAM-816.md` al continuar. AUTH-LOTE1 autoriza ejecución directa,
  sin delegación; BT2 hará la revisión independiente sobre el PR draft.
- Clasificación LEVEL 2 por billing; MATH_VERIFY OFF, METHOD_REGISTRY NONE.
  No hay cambio de método numérico, precio ni aritmética.

## Restricciones

Sin claves reales, transacciones, organizaciones, túneles, despliegue, fusión,
force-push, edición de Linear/Notion ni acceso a D:. Los datos de las pruebas y
bases PostgreSQL locales son ficticios. Los dobles **no prueban** tarjeta, impuestos,
prueba nativa, conversión a pago o entrega de eventos reales.

El lanzador Systems delegado es incompatible con la prohibición explícita de
AUTH-LOTE1. Se mantuvo la ruta directa autorizada; no se ejecutó init/launch/collect
ni se atribuye sello del runner a los logs. Ownership se registró en el Git común;
control y evidencia se guardan exclusivamente bajo
`basis-runs/MAM-816-20261023-724354b4/`. Revisión BT2: **NOT RUN**.

## Áreas afectadas y auditoría

La implementación existente ya valida producto mensual con único precio activo de
500 centavos USD, impuestos exclusive y trial day/7; el navegador no selecciona
precio, propietario, producto ni URLs. Checkout y portal usan la identidad del
servidor. La creación mantiene intención durable, caducidad y tratamiento de POST
ambiguo. Firmas Standard Webhooks se verifican sobre bytes originales; recibos
únicos y trabajo diferido disparan Customer State GET autoritativo. La conciliación
se serializa con las escrituras de la cuenta y conserva el aislamiento.

No se encontró un hueco de runtime que justificara reimplementar estas partes.
La evidencia anterior agrupaba varias transiciones bajo nombres genéricos. Se
agregaron ocho pruebas para eventos concretos de renovación/cancelación/impago,
entregas invertidas y fronteras HTTP/configuración.

La pantalla oculta checkout sin configuración completa. Para una cuenta con
customer binding anterior, portal/refresh siguen visibles: al enviarlos se muestra
el error de configuración, sin abrir transporte. No se afirma que todos los botones
se oculten. Este comportamiento existente queda probado, no rediseñado.

## Pasos ejecutados

1. Auditoría de billing, config, documentación y pruebas existentes; snapshot v1.
2. Ocho pruebas nuevas y commit pequeño tras pasar su ejecución enfocada.
3. Baterías PostgreSQL, puras, tipado y linters; corrección explícita de entorno
   mediante revisión v2, sin cambiar el candidato de pruebas.
4. Navegador Edge real contra servidor local deshabilitado y backup/restore de una
   base ficticia. Documentación y publicación en PR draft; no integración ni cierre.

## Habilidades empleadas

Planificación, Git seguro, depuración sistemática y verificación antes de completar.
Sin delegación, habilidades de cálculo ni herramientas Polar.

## Validación — matriz criterio → prueba → estado

Alias de archivos:

- **N**: `tests/regression/test_billing_polar_acceptance.py`, clase `PolarAuditAcceptanceTests`.
- **E**: `tests/regression/test_billing_polar.py`, pruebas existentes reejecutadas.
- **W**: `basis/modules/billing/adapters/test_polar.py`, contratos existentes reejecutados.

| Criterio | Prueba / archivo | Estado local |
| --- | --- | --- |
| Firma inválida rechazada, bytes/tiempo/rotación | E: `test_raw_signature_full_headers_timestamp_rotation_and_secret_modes` | VERIFIED |
| Replay del mismo evento idempotente | N: `test_inverted_event_snapshots_and_replay_cannot_restore_revoked_access`; E: `test_past_due_replay_order_recovery_and_generic_retry_metrics` | VERIFIED |
| Eventos invertidos no reemplazan estado actual | N: `test_inverted_event_snapshots_and_replay_cannot_restore_revoked_access` | VERIFIED |
| Renovación cambia período solo mediante Customer State | N: `test_renewal_notification_replaces_expired_period_from_customer_state_only` | VERIFIED |
| Cancelación programada conserva acceso; revocación efectiva lo retira | N: `test_scheduled_cancellation_keeps_current_access_then_revocation_removes_it` | VERIFIED |
| Impago past_due/unpaid no concede acceso por importe o snapshot | N: `test_nonpayment_notifications_cannot_grant_from_invoice_or_event_status` | VERIFIED |
| Reembolso parcial/total sigue estado autoritativo, no inventa revocación | E: `test_refund_customer_id_only_uses_bound_identity_and_current_state` | VERIFIED |
| Retorno del checkout no concede acceso ni muta cuentas | N: `test_checkout_web_ignores_client_purchase_fields_and_return_cannot_grant` | VERIFIED |
| Aislamiento entre cuentas y cliente/organización/external ID | N: renovación y checkout; E: `test_wrong_org_customer_and_external_id_never_grant` | VERIFIED |
| Producto/precio/retorno/trial seleccionados en servidor | N: `test_checkout_web_ignores_client_purchase_fields_and_return_cannot_grant`; W: `test_checkout_payload_is_server_owned_and_uses_provider_expiry` | VERIFIED |
| Rechazo de moneda, importe, tax, recurrencia o trial no aprobados | N: `test_checkout_rejects_wrong_currency_tax_price_and_trial_before_purchase`; E: política nativa | VERIFIED |
| Checkout/portal/refresh exigen login, POST y CSRF | N: `test_checkout_portal_and_refresh_require_login_post_and_csrf`; E: portal verificado | VERIFIED |
| Configuración incompleta no abre transporte, checkout oculto | N: `test_incomplete_configuration_disables_checkout_and_provider_network` | VERIFIED |
| Carreras reales de checkout y revocación/escritura | E: tres pruebas `PolarSerializationTests`, PostgreSQL sin omitir | VERIFIED |
| Upgrade conserva identidad, períodos, trial y recibos | E: `PolarUpgradeTests.test_billing_upgrade_preserves_identity_period_history_and_receipts` | VERIFIED |
| Tarjeta, impuestos, trial/conversión y eventos Polar reales | Sandbox/LIVE requiere autorización y configuración | NOT RUN |

### Comandos y resultados reales

Python 3.13.7, PostgreSQL/pg_dump 18.4, HTTPX 0.28.1, StandardWebhooks 1.1.0,
Playwright 1.64.0, Edge instalado 155.0.4283.62. Venv Windows propio, creado con
`uv --cache-dir .cache/uv venv .venv-win --python 3.13` e instalado mediante
`uv --cache-dir .cache/uv pip install --python .venv-win/Scripts/python.exe -r requirements-dev.txt`.
Se usó PostgreSQL descartable propio en loopback:5816; no bases del usuario.

Prefijo **PY** = `.venv-win/Scripts/python.exe`. Entorno de la batería final:
`DJANGO_SETTINGS_MODULE=config.test_settings`,
`DATABASE_URL=postgresql://mam816_local@127.0.0.1:5816/basis_mam816`,
`PUBLIC_URL=http://127.0.0.1:8000`, IA/acceso de desarrollo deshabilitados y
variables privadas de Polar/DeepSeek vacías en el proceso padre de las pruebas.
Los dobles usan valores explícitamente sintéticos.

| Comando | Resultado |
| --- | --- |
| `PY manage.py test tests.regression.test_billing_polar_acceptance --noinput -v 1` | VERIFIED: 8/8 |
| `PY manage.py test tests.regression.test_billing_polar tests.regression.test_billing_polar_acceptance basis.modules.billing.adapters.test_polar basis.modules.billing.adapters.test_persistence --noinput -v 2` | VERIFIED: 41/41, cero omisiones |
| `PY manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput` | VERIFIED final: 467/467, cero omisiones |
| `PY -m unittest discover -s tests_architecture` | VERIFIED: 191/191 |
| `PY -m ruff check .` | VERIFIED |
| `PY -m ruff format --check basis config tests tests_architecture scripts/architecture_check.py scripts/browser_smoke.py scripts/acceptance_browser.py scripts/ux_acceptance.py scripts/verify_environment.py scripts/backup_db.py scripts/healthcheck.py scripts/verify_operations.py scripts/verify_gunicorn_logging.py deploy/gunicorn_config.py` | VERIFIED |
| `PY manage.py check` | VERIFIED, cero problemas |
| `PY manage.py makemigrations --check --dry-run` | VERIFIED, sin cambios |
| `PY -m mypy --config-file mypy-core.ini` | VERIFIED: 119 archivos |
| `PY -m mypy --config-file mypy-django.ini` | VERIFIED: 367 archivos |
| `PY scripts/architecture_check.py` y `.venv-win/Scripts/lint-imports.exe` | VERIFIED; 8 contratos conservados |
| `PY -m djlint basis --check` | VERIFIED |
| `npm ci --ignore-scripts` | VERIFIED, instalación fijada por lockfile |
| `npm run format:check` | FAILED en este checkout Windows: 9 estáticos CRLF; configuración exige LF |
| `node node_modules/prettier/bin/prettier.cjs --check "assets/css/**/*.css" "assets/js/**/*.js" "basis/**/static/basis/**/*.css" "basis/**/static/basis/**/*.js" --no-error-on-unmatched-pattern --end-of-line crlf` | VERIFIED diagnóstico: solo diferencia EOL; no reemplaza el gate LF |
| `PY manage.py migrate --noinput` y `PY manage.py collectstatic --noinput` | VERIFIED sobre base local nueva |
| `PY .cache/mam816_browser.py` | VERIFIED final: 8 checks, desktop 1280×900/mobile 390×844; fotos locales |
| `PY scripts/backup_db.py backup .cache/mam816.dump` | VERIFIED |
| `PY scripts/backup_db.py restore-test .cache/mam816.dump --database basis_restore_mam816` | VERIFIED; comparación adicional de todas las filas/tablas y secuencias idéntica |
| `pytest` | NOT RUN: no es dependencia ni runner de este repo; se usa el runner Django/unittest canónico |
| Docker/build de producción local | NOT RUN; comprobación remota pertenece a CI |
| CI remoto del commit publicado | Pendiente de observar en el PR; no se reutiliza CI histórico |

### Fallos intermedios y límites de evidencia

- La primera versión de las pruebas nuevas falló por expectativas CSRF y por no
  restaurar períodos de la fixture entre subcasos; se corrigieron las pruebas,
  no las defensas de producción.
- Un parche inicial del test de producto apuntó a la acción web en vez del requester
  de bootstrap. Eso dejó pasar intentos de transporte GET con un token **sintético**
  que devolvieron errores controlados; no hubo POST ni credenciales reales. No se
  afirma ausencia absoluta de intentos de red en toda la sesión. La versión final
  inyecta `billing(provider)` y bloquea `httpx.Client` por defecto en cada test nuevo:
  una omisión de mock falla antes de abrir transporte. Los resultados finales son
  de esta versión corregida y no prueban operación real.
- La primera batería de 467 terminó FAILED, un fallo: `test_signup_requires_verification_then_login`
  esperaba la URL 8000 y el arnés había fijado 8816. Revisión v2 registró el cambio de
  entorno; repetición completa con 8000: 467/467. Se conserva el log fallido.
- Prettier LF sigue FAILED localmente: no se editaron los nueve estáticos ajenos
  al ticket ni Git config (`core.autocrlf=true`). Diagnóstico CRLF pasa; CI Linux
  deberá comprobar la política canónica.
- Primer smoke de navegador falló al consultar ORM dentro del contexto async de
  Playwright. Se movió la consulta fuera del contexto, sin deshabilitar la defensa
  de Django. Otro intento detectó un host inyectado por el antivirus; la corrida
  final aborta toda petición no local y registra `me.kis.v2.scr.kaspersky-labs.com`.
  No se observó petición del navegador a Polar.

Los logs y hashes son evidencia directa de procesos, **no revisión independiente ni
recibos sellados Systems**. `candidate.json` contiene HEAD limpio y hashes de todos
los archivos; `toolchain.json` identifica bytes de venv (sin pyc generados), y
`results.json`/`directed-results.json` guardan comandos, exits y SHA-256 de logs.
La documentación posterior no cambia los bytes de código/pruebas de `ca7baa9`.

Anclas de evidencia:

- `candidate.json`: SHA-256 `2f3e2ecd7874e85f8b1e648ff17f7a074d881a5a217e9fa10a37d39ad114aad1`.
- `focused-polar.log`: `7e569042949c877fbc4f6739081accf89a49a1850c7214a6692db054a90437c2`.
- `full-postgres-default-origin.log`: `d6b5758a4739f50c94774c379c7d23b9ea4a46d1bdda032a7cbfc9ba8f50e778`.
- `pure.log`: `1605245894aa927034f28181c9ecd4b90980d370923c0a371de188876267ef4a`.
- `browser.json` y `backup-restore.json` conservan versiones y hashes de artefactos.

## Riesgos y pendientes

- BT2 debe revisar independientemente el PR draft; no se declara aprobación local.
- Sandbox/LIVE, tarjeta, impuestos, conversión trial, impago/cancelación/reembolsos
  reales: **NOT RUN**, reservados a autorización explícita de Jonathan.
- CI remoto y la política LF deben comprobarse en el SHA final publicado.
- No integración en main, fusión, transición Done ni sincronización de tracker.
- Se conserva el worktree, las ramas anteriores y las evidencias; no se limpia
  trabajo privado/ignorado ni toolchains compartidos.
