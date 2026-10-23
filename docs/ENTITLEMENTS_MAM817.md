# MAM-817 — permisos, fechas y conservación offline

## Alcance y plan breve

Continuación de `implementation_round=1`, no otra ronda de implementación o revisión.
Contrato comercial congelado: acceso únicamente `active`/`trialing` dentro de
`[period_start, period_end)`, con fechas conscientes de zona horaria y sin reconciliación
pendiente. No se cambian reglas de cobro, importes, cuotas, backend, esquema, API, auth
ni JavaScript offline.

1. Conservar el único delta de producto: mostrar «Inicio del período» en español para
   `active`/`trialing` cuando exista `period_start`. Sin fallback; fecha final y portal
   permanecen iguales.
2. Complementar la cobertura existente con tabla temporal independiente, presentación,
   conservación del historial y rechazo de escrituras/cuota sin llamadas a proveedores.
   El template y los dos archivos de tests ya comprometidos no se modifican aquí.
3. Corregir únicamente la observación HTTP y cleanup del harness; registrar literalmente
   `scripts/mam817_browser.py` en `files` de `mypy-django.ini`, sin exclusiones legacy
   ni relajación de strict. Entregar para ejecución por el coordinador. No ejecutar gates
   en esta continuación ni heredar resultados de otro candidato.

## Identificación y estado de evidencia

- Ejecución: `MAM817-20261023-BT1`; rama: `ticket/MAM-817-entitlements`.
- Base congelada: `de24ce7ef686c0b990342537d7a47a6fec5274a6`.
- Snapshot de la continuación anterior, solo procedencia histórica, **no activo**:
  `8e881e692ec054a70d4fefe3cd444fb24d6ef55da4adf2f440a76f5deefd9d45`.
- El script registra `initial_source_snapshot_hash` como procedencia inicial, **no**
  como snapshot activo. El launcher sella externamente candidato y snapshot actuales.
  `source-before.json` y `source-after.json` incluyen los hashes de las seis rutas del
  delta, incluidos el script, esta documentación y `mypy-django.ini`; no se intenta
  incrustar el hash del candidato en sus propios archivos.
- Intento anterior de navegador: **FAILED / timeout de 300000 ms**, no VERIFIED.
  Alcanzó edición/reload offline y `db-expired.json`; `server.log` mostró `/api/sync/`
  con 403 real, pero faltaron `result.json`, `db-after-403.json` y `real-403.json`.
  El bloqueo al leer el body de ServiceWorker es una hipótesis, no causa demostrada.
  El coordinador confirmó y terminó solo wrapper/child propios del runserver anterior.
  Architecture anterior falló por el script fuera de strict scope; la adición literal
  a `files` corrige el registro, sin alterar el checker.
- **Todo resultado del candidato final queda NOT RUN** hasta validación del coordinador.
  Los errores reproducidos sobre el candidato anterior no son una ejecución ni una
  certificación del candidato entregado aquí. Tampoco se heredan resultados de MAM-816.

## Matriz de auditoría y pruebas complementarias

Los nombres siguientes son selectores exactos de los tests añadidos. `P` corresponde a
`tests_architecture.test_entitlements.EntitlementInvariantTests`; `V` a
`tests.regression.test_billing_entitlements.EntitlementPresentationTests`; `C` a
`tests.regression.test_billing_entitlements.ExpiredConservationTests`.

| Criterio | Test exacto / comprobación | Oráculo o invariante | Estado final |
| --- | --- | --- | --- |
| Inicio inclusivo, fin exclusivo; estados permitidos y equivalencia de zonas | `P.test_full_status_and_boundary_truth_table_including_timezone_equivalence` | Tabla literal `False, True, True, True, False, False` en seis instantes, ±1 microsegundo, zonas −5/0/+9; solo active/trialing | NOT RUN |
| Fechas ausentes/naive, pendiente e intervalos no positivos deniegan | `P.test_missing_naive_pending_and_nonpositive_intervals_fail_closed` | Expectativa literal de rechazo, sin derivarla de la implementación | NOT RUN |
| Cancelar al final no acorta ni extiende el corte autoritativo | `P.test_cancellation_flag_never_extends_or_shortens_the_authoritative_cutoff` | `ends_at` prevalece; permite antes y deniega en/después del límite, con ambas banderas | NOT RUN |
| Memoria de prueba única conservada | `P.test_trial_memory_is_monotonic_across_empty_unpaid_and_pending_state` | `trial_used` nunca vuelve a falso al reconciliar estados vacíos/no pagados/pendientes | NOT RUN |
| Inicio visible solo con estado/fecha aplicables; fin y portal intactos | `V.test_initial_date_is_conditional_without_fallback_and_keeps_end_and_portal` | Fecha sintética fija, formato localizado esperado y matriz de estados/ausencia | NOT RUN |
| Cancelación y fechas ausentes no inventan fechas | `V.test_cancellation_label_and_absent_end_do_not_invent_dates` | Etiqueta de acceso hasta; sin inicio/fin cuando faltan; portal conservado | NOT RUN |
| Caducidad conserva lectura/export propio y deniega escritura; aislamiento | `C.test_expiry_rejects_the_same_new_operation_without_receipt_or_server_changes` | Dos 403 con CSRF real y mismo UUID/payload; snapshot intacto, cero recibos, historial propio exportable, ajeno 404/403 y sin datos filtrados | NOT RUN |
| Sin sobrecobro por cuota rechazada; precio fijo sin cambios | `C.test_repeated_quota_rejection_has_no_jobs_usage_changes_or_provider_calls` | Tres rechazos, mismo uso y un único job previo; gasto cero, doubles Polar/IA sin llamadas; página conserva $5 y mensaje sin cargos automáticos | NOT RUN |

Las medidas `5500.5` m y `7.25` kg del navegador son datos sintéticos de persistencia,
no nuevos algoritmos numéricos. Se exige igualdad exacta del JSON/UUID/payload y de
los snapshots; no se añade tolerancia que pueda ocultar pérdida de datos. La única
resolución temporal usada en la tabla es un microsegundo de `datetime`.

## Cobertura existente reutilizada, sin duplicar backend

La auditoría congelada del coordinador ya identificó la cobertura existente de Polar,
persistencia y estado comercial. Esta continuación no repite esa auditoría ni modifica
esos tests. Se reutilizan mediante los selectores de suite incluidos en `django-suite`;
los nombres individuales/resultados de esa cobertura se deben conservar en el registro
de ejecución y la PR, no inventarse a partir de esta matriz.

| Contrato existente reutilizado | Suite/selector de ejecución | Complemento de este delta | Estado final |
| --- | --- | --- | --- |
| Refund no inventa revocación: consultar estado autoritativo con doubles locales | `tests.regression` (cobertura existente billing/Polar), `basis.modules.billing.adapters.test_polar` | No nuevo handler ni revocación; se conserva el contrato auditado | NOT RUN |
| Impago/past_due deniega | `tests.regression`, `basis.modules.billing.adapters.test_polar` | Tabla completa de estados en `P.test_full_status_and_boundary_truth_table_including_timezone_equivalence` | NOT RUN |
| Customer único, sin rebind ni cruce de cuentas | `tests.regression`, `basis.modules.billing.adapters.test_persistence`, `basis.modules.billing.adapters.test_polar` | Aislamiento DB/web en `C.test_expiry_rejects_the_same_new_operation_without_receipt_or_server_changes` y navegador con otra cuenta | NOT RUN |
| Trial único por cuenta/cliente; checkout sin segunda prueba | `tests.regression`, `basis.modules.billing.adapters.test_polar` | Monotonía de `trial_used` en `P.test_trial_memory_is_monotonic_across_empty_unpaid_and_pending_state` | NOT RUN |
| Precio fijo y límites existentes; sin cambios de importe ni algoritmo | `tests.regression` | `C.test_repeated_quota_rejection_has_no_jobs_usage_changes_or_provider_calls` verifica rechazo sin proveedor, sin incremento de uso y presentación de $5 | NOT RUN |

## Navegador real y artefactos previstos

Entrada: `scripts/mam817_browser.py`, gate congelado `browser`. Edge se verifica por
SHA-256 antes del lanzamiento y nuevamente después de preparar la DB. Usa una DB SQLite
y perfil únicos propios bajo `.cache/mam817-browser-*`, entorno de subprocess limpio,
proveedores/SMTP deshabilitados y origen loopback. No usa Polar real ni credenciales reales.
La DB exacta se comprueba antes de cada observación/mutación ORM. No se mockea ni se
sustituye la respuesta de `/api/sync/`.

Se conserva `expect_response` de la UI: status 403 real, wire idéntico a la operación
pendiente y mensaje visible de acceso denegado. No se llama a `json()`/`finished()`
del BrowserResponse de ServiceWorker. Se obtiene CSRF fresco por `page.request.get`
y se hace **un POST HTTP real adicional**, con el mismo wire, por `page.request.post`;
ambas peticiones tienen timeout de 15000 ms. Este segundo 403 debe incluir el detalle
explícito de suscripción activa, no un rechazo CSRF. Los dos rechazos se registran por
separado antes de las comprobaciones conservadas de cola/servidor/export/otra cuenta.

| Criterio | Nombres exactos de checks del script | Evidencia prevista | Estado final |
| --- | --- | --- | --- |
| Fixture con acceso real, sin bypass | `owned_fixture_active_without_development_bypass`, `edge_executable_sha256_verified_before_launch` | `db-initial.json`, hash y versión Edge/Python en `result.json` | NOT RUN |
| Fechas inicial/final visibles, sin overflow a 1440 y 390 px | `billing_dates_visible_no_overflow_1440`, `billing_dates_visible_no_overflow_390` | `billing-desktop.png`, `billing-mobile.png`, fecha esperada ORM | NOT RUN |
| Descargar con acceso, editar offline y recargar sin perder datos | `real_offline_edit_reload_preserves_uuid_entire_payload_and_measurements` | `queue-before-reconnect.json`, UUID y payload completo de IndexedDB | NOT RUN |
| UI 403 real con misma operación y estado de denegación; confirmación HTTP independiente | `real_ui_403_same_queued_wire_and_denial_status`, `real_direct_http_entitlement_403_same_queued_wire` | `real-ui-403.json` y `real-direct-403.json`, sin leer body de ServiceWorker | NOT RUN |
| Vencer acceso en DB propia, reconectar y recibir 403 real sin cambio servidor | `real_entitlement_403_same_uuid_payload_local_data_and_server_unchanged` | `real-403.json` (UI y confirmación separadas), `queue-after-403.json`, `db-before-expiry.json`, `db-expired.json`, `db-after-403.json` | NOT RUN |
| Descargar JSON exacto de pendientes caducados y offline sin borrarlos | `exact_local_json_download_after_expiry_and_offline_without_data_loss` | `pending-expired.json`, `pending-offline.json`, `expired-pending.png`; igualdad exacta por cuenta | NOT RUN |
| Historial propio legible/exportable tras caducidad | `expired_owner_history_readable_and_exportable` | Respuestas HTTP reales y snapshots de servidor | NOT RUN |
| Otra cuenta no ve/exporta/envía cola ni historial ajenos, aun con filas presentes en el mismo perfil | `same_profile_other_account_cannot_view_export_or_submit_foreign_queue_or_history` | `other-account.json`, `other-account-offline.json`, `db-final.json`; export local vacío, historial 404, envío 403 | NOT RUN |
| Sin entrega HTTP fuera del origen local | `outside_origin_requests_aborted_no_external_responses` | Lista de bloqueos/respuestas externas y errores JavaScript en `result.json` | NOT RUN |

El script conserva DB/perfil propios para inspección, registra cleanup y hashes y
redacta secretos sintéticos en logs/JSON. En Windows termina exclusivamente el subárbol
del PID de su propio `Popen` mediante `SystemRoot/System32/taskkill.exe /PID <pid> /T /F`,
timeout de 15 s, salida capturada y espera de hasta 10 s; no basta que salga el wrapper.
En otros sistemas conserva terminate/wait y kill acotados. No hay kill global ni borrado
de archivos, caches o toolchains compartidos.

Las llamadas de Playwright permanecen en un único thread propietario. Como close no
expone timeout síncrono, el thread principal espera como máximo 20 s por teardown de
context/browser/driver tras finalizar el flujo. Si no termina, el resultado es FAILED y
`browser_stopped` es falso (no se presume cierre ni se mata un proceso ajeno). Los errores
de cleanup/finalización no impiden intentar escribir `result.json`; un subárbol no
confirmado o fuente alterada también impide VERIFIED. Las capturas/JSON solo constituyen
evidencia del candidato exacto cuando el launcher los selle y el coordinador valide.

## Gates y límites pendientes

Todos **NOT RUN** para el candidato final: `django-suite`, `pure-tests`, `check`,
`migration-drift`, `ruff`, `ruff-format`, `djlint`, `mypy-core`, `mypy-django`,
`mypy-browser`, `architecture`, `imports`, `browser`. Se usan únicamente los comandos,
entornos, timeouts y ejecutables del snapshot congelado. La inspección del script y la
validación del coordinador preceden a su ejecución; se requiere revisión strong del
candidato exacto y revisión UI. Esta entrega no implica aceptación, integración,
publicación ni cierre.

SQLite y navegador local no certifican carreras PostgreSQL, dispositivos físicos,
Polar LIVE/sandbox ni CI remoto. Los skips SQLite no cuentan como prueba de concurrencia.
Las referencias/cobertura previa no sustituyen resultados propios por SHA. La PR debe
registrar por separado VERIFIED/FAILED/NOT RUN con sus registros sellados y los límites
restantes; no se cambia esta documentación para fingir una ejecución que no ocurrió.
