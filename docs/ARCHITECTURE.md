# Arquitectura y límites de operación

Estado actual al readback de Luna del 2026-10-21: ARCH-01..10 y la épica BASIS-ARCH/MAM-821 están Done. La remediación y presentación se integraron en `main/24484b7c8c5a4c0beb89ee1dc854c91581d7293a`; el [recibo de aceptación](architecture/ARCHITECTURE-ACCEPTANCE-2026-10-20.json) conserva CI PostgreSQL 246/0 omisiones y la aceptación arquitectónica. MAM-617 permanece Done; MAM-621 y MAM-637 también están Done, tras PR #3 y PR #4 integrados en `158235c035dc442e008fe4e423442c8c955aba9b` y `5edf6bd515ed56289b76da3339c9acaa4a7d4680`. Luna verificó sus criterios y conservó estados ya existentes, sin cambiarlos. Quedan **28 funcionales abiertos**, sin bloqueo de arquitectura; MAM-626/MAM-627 siguen In Progress, lector de pantalla NOT RUN y aceptación humana PENDING. El [readback del lote](DEVELOPMENT_2026-10-20.md#cierre-del-lote-mam-621-y-mam-637-2026-10-21) separa estado actual de pruebas históricas. La reapertura de ARCH-09 tras `337f12d` y sus límites originales se conservan en [el registro histórico de ejecución](ARCHITECTURE_EXECUTION.md) y [la remediación](architecture/ARCH-09-REMEDIATION-VERIFICATION.md).

## Estructura actual y contratos

```text
config/                         # settings, URLs, ASGI y WSGI de Django
basis/
  shared/                       # identificadores distintos, valores y protocolos comunes
  bootstrap/                    # composición explícita y servicios de infraestructura
  modules/
    accounts/                   # identidad, verificación y recuperación
    athletes/                   # perfil, preferencias, mediciones, RM e historial
    catalog/                    # ejercicios y clasificaciones
    training/                   # planificación, ejecución, métricas y trekking
    billing/                    # acceso comercial, checkout, portal y conciliación
    coach/                      # contexto, propuestas, trabajos y presupuestos
    sync/                       # operaciones, revisiones, recibos y conflictos
tests/regression/               # los 111 escenarios originales, ahora tipados
tests_architecture/             # dominio, aplicación y contratos sin Django
```

Cada módulo contiene `domain/`, `application/`, `adapters/` y `public.py`. Domain define valores y reglas puras; application ejecuta comandos tipados usando puertos específicos; adapters implementa HTTP, ORM y proveedores. Los modelos y migraciones iniciales están en `adapters/models.py` y `adapters/migrations/` de las siete aplicaciones `basis_<area>`. La composición vive en bootstrap; config contiene configuración del framework. Ningún paquete de configuración anterior se conserva como puente.

Las colaboraciones entre módulos pasan por contratos públicos, también cuando solo se importan tipos. Los adaptadores de lectura pueden consultar su propio ORM y convertir proyecciones; los de escritura llaman casos de uso. Las vistas manuales ya no abren transacciones ni guardan sesiones, bloques, series o intervalos directamente. Los casos de administración conservan los permisos nativos sin convertirse en una vía alternativa de reglas comerciales. Los hooks de modelos validan defensivamente con las mismas políticas puras.

[Mapa verificable de entradas y casos de uso](architecture/ENTRYPOINTS.md). [Auditoría y resoluciones](architecture/ARCH-10-AUDIT.md). La ausencia física de `basis_trainning_app/` y `daily_trainning_app/` fue comprobada después de la limpieza del usuario; los controles también rechazan sus imports y fuentes activos. El namespace fuente anterior `training/` se retiró al trasladar las pruebas.

`mypy-core.ini` comprueba núcleo y contratos sin plugin Django. `mypy-django.ini` añade todo basis, config, manage.py, las pruebas de regresión y las herramientas migradas, con plugins Django/DRF y sin exclusiones globales de errores. El inventario pendiente actual solo contiene el `seed.py` protegido del usuario; `scripts/backup_db.py` y los verificadores operativos están bajo strict desde PR #4. No quedan fronteras silenciosas en el runtime. La compatibilidad parcial de las versiones de stubs se documenta en [ARCH-09-TYPING.md](architecture/ARCH-09-TYPING.md).

Las secciones ARCH-03..08 y el registro de presentación al final describen entregas históricas y sus límites en aquel momento; sus rutas, estados y cantidades no describen el candidato actual. Los recibos de cada etapa conservan su evidencia original. La remediación y su aceptación tienen recibos propios; no se atribuyen sus pruebas a candidatos posteriores.

## ADR-001 — Arquitectura hexagonal y tipado estricto (2026-10-19)

**Decisión aceptada e implementación arquitectónica aceptada.** Épica BASIS-ARCH/MAM-821, ARCH-09/MAM-830 y ARCH-10/MAM-831 Done, con evidencia enlazada arriba. La aceptación funcional continúa con sus dependencias propias. ADR-002 reemplaza la conservación inicial de tablas, etiquetas y migraciones: los modelos pertenecen a los adaptadores finales y el esquema se verifica desde cero en bases temporales.

`basis/modules/<área>/{domain,application,adapters}` agrupa cada responsabilidad. `public.py` es la única entrada entre módulos y declara `__all__`; declara los contratos migrados. `basis/shared` contiene identificadores distintos y los protocolos Clock/UnitOfWork. `basis/bootstrap` conecta implementaciones por inyección explícita. Las capas dependen hacia dentro: adaptadores → aplicación → dominio; dominio no importa aplicación. Shared no importa módulos de negocio. Los contratos públicos solo exportan dominio/aplicación y nunca adaptadores.

| Módulo | Responsabilidad y fuente actual | Etapa principal |
| --- | --- | --- |
| accounts | Identity, verification and recovery; own typed domain/application/adapters | ARCH-03, ARCH-09 |
| athletes | Profile, preferences, measurements, wellness, RM and historical workouts | ARCH-03, ARCH-05, ARCH-09 |
| catalog | Exercise/classification catalog and staff API/admin | ARCH-03, ARCH-09 |
| training | Execution, planning/versioning, metrics and multisport | ARCH-02, ARCH-04, ARCH-05, ARCH-09 |
| billing | Commercial policy, Polar, reconciliation and webhook adapters | ARCH-06, ARCH-09 |
| coach | Authorized context, proposals, jobs and budget accounting | ARCH-07, ARCH-09 |
| sync | Revision, receipt, replay and offline-conflict coordination | ARCH-08, ARCH-09 |

### Contratos de implementación

Comandos y resultados serán dataclasses; puertos Protocol específicos del caso de uso. Sin repositorio CRUD genérico ni bus obligatorio. Identificadores de cuenta, atleta (PK del perfil), sesión UUID, sesión programada, plan y revisión son NewType diferentes. Los identificadores públicos externos conservarán su representación actual mediante adaptadores. Cargas y dinero usan Decimal; fechas explícitas; None conserva ausencia frente a cero. El núcleo no recibe ORM, QuerySet, HTTP, Any ni JSON libre. Los adaptadores validan y convierten entradas externas y traducen errores propios a los errores HTTP/DRF/formularios existentes.

La UoW Django confirmará explícitamente éxito y revertirá ante error o salida sin commit, también dentro de transacciones anidadas. Sesión y recibo se guardarán juntos. Conservar el orden de bloqueo y la política de reservas/resultados ambiguos del legado. ARCH-02 verificó estos contratos sobre el adaptador real y PostgreSQL antes de cerrar.

### Planes y extensión futura

PlanDefinition es una definición tipada independiente de procedencia, con validación y creación privada comunes a manual e IA. Un futuro adaptador de programas podrá resolver ejercicios y fechas por ese contrato. Cada instancia conserva versión, prescripciones y resultados propios; editar una fuente no cambia historia. Esta migración no implementa catálogo, publicación ni interfaz de programas.

### Controles de frontera y tipado

`python scripts/architecture_check.py` analiza incluso importaciones relativas y TYPE_CHECKING: núcleo independiente, capas, acceso entre módulos por public, ausencia de Any explícito y rutas declaradas. Rechaza infraestructura HTTP/configuración/persistencia en el núcleo y ejecución/importación dinámica directa. Import Linter verifica ocho contratos del grafo, incluidos caminos indirectos. Son controles estáticos; no pretenden probar ejecución arbitraria ni reemplazar la revisión de interfaces. Las pruebas importan todo el núcleo usando Python -I -S, sin site-packages, ajustes ni Django.

`mypy-core.ini`: estricto, sin plugin ni inicializar Django; `mypy-django.ini`: estricto con django-stubs/test_settings para basis, incluidos adaptadores y bootstrap. No hay ignore_missing_imports ni exclusiones globales. Ambas configuraciones prohíben Any explícito y procedente de imports sin tipos. Las áreas migradas deben agregarse al alcance estricto desde su primer commit, y salir del inventario pendiente; las excepciones locales de terceros se documentarán individualmente (ninguna en ARCH-01).

Se fijan Python 3.13, Django 5.2.18, mypy 1.19.1, django-stubs/django-stubs-ext 6.1.2 y djangorestframework-stubs 3.18.1. La matriz oficial declara compatibilidad parcial con Django 5.2: el alcance comprobado se documenta en [ARCH-09-TYPING.md](architecture/ARCH-09-TYPING.md). Import Linter 2.11. El inventario `docs/architecture/legacy-baseline.json` congela los archivos de 08dcd02; `legacy-pending.json` solo puede reducirse. El control compara HEAD y HEAD^ donde existen; CI obtiene dos commits. El legado no está certificado como estrictamente tipado por estas configuraciones. ADR-002 retires the old runtime packages and migrations; the final seven module applications have typed initial migrations. The regression suite is strictly typed. Only protected seed.py remains in the current pending inventory; scripts/backup_db.py was promoted to strict typing in PR #4.

### Ejecución y evidencia

ARCH-01 → ARCH-02 → ARCH-03 → ARCH-04 → ARCH-05 → ARCH-06 → ARCH-07 → ARCH-08 → ARCH-09 → ARCH-10; etapas integradas y aceptadas. Reversión por commits inversos, conservando esquema y contratos. No corregir funcionalidad silenciosamente. [Plan y registros históricos](ARCHITECTURE_EXECUTION.md), [aceptación](architecture/ARCHITECTURE-ACCEPTANCE-2026-10-20.json) y [snapshot histórico de arquitectura anterior al cierre de MAM-617](architecture/linear-readback.json). Estado actual: **35 funcionales = siete Done y 28 abiertos (27 In Progress y uno Backlog)**; con los 11 de arquitectura Done, **46 tickets = 18 Done, 27 In Progress y uno Backlog**. [ROADMAP.json](ROADMAP.json), campo `current_readback`, concilia MAM-621/MAM-637 Done y la fuente de Luna sin reescribir los snapshots anteriores. El cierre no elimina otras dependencias: MAM-622 espera MAM-620, que espera MAM-810; MAM-623 espera MAM-622. MAM-638 conserva once bloqueantes pendientes, incluido MAM-636 Backlog. La cadena High MAM-810 → MAM-620 → MAM-622 → MAM-623 no se inicia en este lote.

La [revisión independiente previa a PR #1](../.cache/independent-review-a5614455b6c040438616780d94269822/result.json) verificó mypy núcleo 113/Django 320, Ruff/djLint/Prettier, arquitectura y ocho contratos, 174 pruebas puras y 21 comprobaciones de navegador sobre runtime `d3ecd68ddced4c3d4bcc3de23c94be869ebdbf1847f7456d93b3fe251dc09533`. Esa evidencia local conserva su candidato. El [cierre operativo de integridad](HISTORY_INTEGRITY.md#cierre-operativo-mam-617-2026-10-20) registra por separado PR #1 y el CI del SHA exacto integrado; los recibos PostgreSQL y fallos anteriores mantienen su atribución histórica.

## Implementación existente y límites que deben conservarse


Django modular monolith with server-rendered templates and session/CSRF API. Runtime code resides under basis/modules and explicit bootstrap composition; retired application/configuration packages have no active source or registration. tests/regression preserves the original baseline scenarios under strict typing. Model classes live in each module's adapters/models.py or explicit adapters/models packages, registered as basis_<area>, with initial migrations under adapters/migrations. All 28 models and config are in strict type scope; no silent model import frontier remains.

La cuenta `auth.User` se vincula explícitamente a un perfil privado mediante OneToOne. Todas las consultas privadas se filtran por la cuenta autenticada; un identificador enviado por el navegador nunca elige el dueño de un registro. El catálogo común se administra mediante permisos de personal. Los ejercicios referenciados se protegen frente al borrado en cascada.

Una prescripción contiene bloques y series/intervalos objetivo; una ejecución recibe una copia y registra resultados por separado. Las ejecuciones completadas son inmutables por los flujos de aplicación. Revisar un plan crea una versión y copia únicamente sesiones futuras sin ejecución. Las relaciones históricas permanecen en la versión original. No existe una inferencia retroactiva de resultados ausentes.

## Interfaz y PWA

Los estilos se modifican desde `basis/adapters/web/static/basis/css/tokens.css`: paleta primitiva, superficies, texto, acento, foco, espaciado, tipografía, radios, sombra y movimiento. Las variables semánticas se mapean al tema Cotton UI; el modo oscuro usa el mismo contrato. Las composiciones compartidas Cotton están en `basis/adapters/web/templates/cotton/basis/`; el contrato de navegación, tareas y estados se documenta en [UX_CONTRACT.md](UX_CONTRACT.md). HTMX actualiza el estado de trabajos IA; los formularios ordinarios también funcionan con navegación normal.

El service worker precarga exclusivamente recursos públicos y una pantalla offline obtenida sin credenciales. Nunca guarda HTML autenticado ni respuestas de API. La versión de caché depende del contenido de los recursos. La primera instalación no recarga formularios; una actualización requiere una acción explícita y evita aplicarse con pendientes.

IndexedDB conserva instantáneas y operaciones por cuenta. Cada operación tiene UUID, hash de contenido y revisión esperada. PostgreSQL serializa la aplicación y los recibos dentro de una transacción. Un conflicto responde 409 y mantiene las copias para revisión. Una respuesta ambigua conserva la misma operación para reintentar; una respuesta del servidor es la única confirmación de sincronización. Cambiar de cuenta no envía su cola bajo otra identidad. Cerrar sesión exporta/solicita resolución de pendientes y limpia la copia de esa cuenta. El almacenamiento del navegador depende del dispositivo; exportar sigue siendo necesario antes de borrar datos o desinstalar.

## Polar

El producto y el importe se seleccionan en servidor y se verifican antes de crear checkout. Una creación se reutiliza mientras su enlace es vigente para evitar dobles solicitudes. El portal permite gestionar o cancelar. Ningún dato de tarjeta entra en BASIS.

Los eventos Standard Webhooks se verifican con firma y tolerancia temporal; cada identificador se registra una sola vez. Los eventos disparan una lectura del estado actual de Polar, serializada por cliente, para resolver entregas fuera de orden. Se filtra el producto configurado. El acceso depende de `active`/`trialing`, período vigente y conciliación completa; impago, cancelación efectiva o revocación dejan lectura/exportación. Un reembolso provoca conciliación: no se inventa un estado distinto del que mantiene Polar.

Debe configurarse una conciliación periódica para eventos perdidos. El flujo LIVE, el producto concreto, su tratamiento fiscal y las transiciones de tarjeta deben certificarse en sandbox antes de producción.

## DeepSeek y costo

Las peticiones usan contexto autorizado congelado, cálculos deterministas y una llamada HTTP sin bucles ilimitados de herramientas. La respuesta de planificación debe superar la misma validación que un plan manual. La persona revisa campos legibles, acepta, edita o rechaza; aceptar no sobrescribe ejecuciones.

Antes de crear un trabajo se reservan tokens y costo máximos. Límites acumulados por acción: consulta 4.000 tokens de entrada/1.500 de salida; plan 8.000/3.000. La entrada se limita conservadoramente por bytes UTF-8 más margen. Se registran modelo solicitado y reportado, uso y tarifa versionada. Las tarifas pico y el redondeo hacia arriba mantienen una estimación conservadora incluso con descuentos horarios del proveedor.

Los bloqueos siguen el orden fondo → cuenta → suscripción → cuota. Una prueba comparte un presupuesto vitalicio de cuenta y un identificador de cliente Polar único. El fondo es mensual. Un cambio de período antes de procesar invalida el trabajo pendiente sin llamar al proveedor. Un timeout conserva su reserva; un worker interrumpido no repite una petición posiblemente facturada. Uso inesperado activa un bloqueo global hasta conciliar. Fallos y reservas no autorizan sobrecargos automáticos.

El acceso IA está deshabilitado inicialmente. Las pruebas contractuales no certifican la calidad deportiva del modelo. El roadmap mantiene abierta la evaluación LIVE de programación, adaptación, datos incompletos, síntomas, instrucciones maliciosas y carga concurrente.

## Infraestructura proporcionada

PostgreSQL, dos procesos web iniciales y un worker de trabajos duraderos. WhiteNoise sirve recursos versionados. HTTPS termina en un proxy controlado. No se requiere Redis, Kubernetes ni microservicios para esta base. Puede aumentar el número de workers web; los presupuestos y la sincronización usan bloqueos PostgreSQL, no memoria de proceso.

`/health/` comprueba una consulta de base de datos. El [CI de código PR #4](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424), ligado al SHA `5edf6bd515ed56289b76da3339c9acaa4a7d4680`, ejecutó migraciones, lint, tests PostgreSQL, estáticos, build/arranque y verificación operativa de backup/restore. Los scripts respaldan formato custom y restauran exclusivamente en una base nueva de pruebas; el [runbook](OPERATIONS_VERIFICATION.md#readback-de-integración-y-cierre-2026-10-21) registra límites y métricas de referencia. SMTP, respaldos externos, alertas, despliegue TLS y capacidad de 1.000 usuarios activos requieren verificación operativa adicional. No se ha activado infraestructura de producción.

## Fuentes de contratos

- [Django 5.2](https://docs.djangoproject.com/en/5.2/), [Cotton UI](https://django-cotton.com/ui/installation), [temas Cotton UI](https://django-cotton.com/ui/theming), [HTMX](https://htmx.org/docs/).
- [Polar Customer State](https://polar.sh/docs/integrate/customer-state), [checkout](https://polar.sh/docs/api-reference/2026-10/checkouts/create-checkout-session), [webhooks](https://polar.sh/docs/integrate/webhooks/delivery), [pruebas](https://polar.sh/docs/features/subscriptions/trials).
- [DeepSeek: modelos y precios](https://api-docs.deepseek.com/quick_start/pricing/), [modo de pensamiento](https://api-docs.deepseek.com/guides/thinking_mode).

## ARCH-03: identity, athletes and catalog

Typed identity registration, email confirmation/resend, rate windows and password recovery live in accounts. Django remains the password/token/site/mail adapter. Registration coordinates athlete/settings and empty billing enrollment through public ports in one explicitly committed transaction; mail failure rolls back all rows. GET confirmation never activates an account. Explicit legacy linking locks account before athlete, never guesses an owner, and does not verify email.

Athlete commands own profile/preferences, sport profiles, wellness, measurements, measured RM and legacy workout writes. Owner IDs come from the authenticated account. Observation absence remains distinct from zero. Existing sport/wellness/RM invariants are shared pure functions called by model validation; historical strength calculations and reference freezing remain in persistence until ARCH-05. Catalog writes enforce staff authorization, preserve archive behavior and Django protected deletion. Existing ModelSerializers/templates/querysets are compatibility read adapters until ARCH-09; schema/URL/JSON/export formats remain stable.

Composition is explicit in basis/bootstrap/{accounts,athletes,catalog,training}. Shared Django UoW/clock adapters now live in bootstrap/transactions; modules do not import each other's adapters. The six exact pending legacy typing frontiers remain unchanged: these mixed files are not certified as fully migrated. Narrow Protocol casts describe existing untyped model save/access signatures without suppressing migrated code or replacing validation.

[ARCH-03 plan](architecture/ARCH-03-PLAN.md), [verification and pending gates](architecture/ARCH-03-VERIFICATION.md). ARCH-04 starts only after the ARCH-03 commit, receipt and main are independently checked.

## ARCH-04: source-independent private planning

PlanDefinition contains typed goals, dates, cycle hierarchy and scheduled prescriptions. It has no program/proposal/provider dependency. Manual forms create a valid empty draft through the same creation/validation path as decoded AI proposals. Proposal shape and366-day/3..100-cycle/1..14-session bounds remain at the wire adapter; they do not restrict manual drafts. No programs feature or schema/provenance column was introduced.

Planning coordinates goal creation, cycles, scheduling, rescheduling with revision/execution guards, rollback-only preview, owner-scoped calendar reads and plan revision. Django adapters keep model/field validation and owner-scoped FK resolution; model clean hooks delegate shared pure goal/date/cycle/schedule rules. Existing proposal acceptance keeps its lock/idempotency/status policy until ARCH-07 and delegates plan creation. Generic template/admin/queryset integration remains for ARCH-09.

Revision locks the original plan, preserves its lineage/version relationship, copies all cycles and only future schedules without executions. Old schedules, prescriptions, measured RM references and results remain intact. Target/actual fields stay distinct, including zero observations. Revisions of an empty scheduled prescription retain the existing validation failure rather than inventing blocks. Typed definitions use immutable tuples and private instance copies, so changing source input cannot alter history.

Shared fake/Django repository tests cover creation, preview rollback and revision/history. Additional real tests cover detailed strength prescriptions and frozen RM, foreign RM rollback, source-input mutation, manual cycle/schedule forms and stale rescheduling. [Plan](architecture/ARCH-04-PLAN.md), [verification](architecture/ARCH-04-VERIFICATION.md). ARCH-05 waits for independent PostgreSQL/commit readback.

## ARCH-05: metrics, progress and multisport

Pure strength/sport policies now define Decimal arithmetic, overflow/rounding/effort eligibility, detailed external-volume/estimate rules, repetition prescriptions and historical RM identity/frozen-context decisions. Sport variables/units/ranges, pace, measured time/load and hiking consistency rules share typed execution Metric/MetricName values. Loose input conversion and Django error translation live in adapters; original strength metric version and reference selection/save behavior remain stable.

Progress/application consumes typed repository snapshots and controlled clock; aggregates authoritative block totals without adding intervals again, keeps sport/protocol ordering and separate units, preserves zero versus unknown and historical adherence across version replacement dates. Trekking adds typed trip/stage writes with explicit UoW, owner/hiking/date-order validation shared with model/form hooks, and typed summary projections. Existing HTTP/report dictionaries are presentation adapters; no public format changed.

Two completed compatibility files (training/domain.py and daily_trainning_app/strength_metrics.py) are strictly checked and removed from pending inventory. Four exact silent legacy frontiers remain; mixed model/view/service files are still infrastructure pending their later retirement. [Plan](architecture/ARCH-05-PLAN.md), [evidence](architecture/ARCH-05-VERIFICATION.md). One combined delivery follows two disjoint executors and independent primary verification; no ARCH-06 before main readback. No programs functionality or schema change.

## ARCH-06: commercial policy and billing adapters

Billing now has typed commercial/access/period policies and transactional checkout, portal, reconciliation and webhook cases, composed with Django repositories, public athlete identity lookup, a bounded Polar gateway and web signature adapter. Core webhook results express business outcomes; HTTP mapping remains in the adapter. Durable webhook phases preserve receipt/pending state before provider reconciliation, including failure/retry. Legacy access/billing/command facades enter strict scope; three exact mixed legacy import frontiers remain. See [verification](architecture/ARCH-06-VERIFICATION.md) and [typing boundary](architecture/ARCH-06-TYPING-EXCEPTIONS.md).

Local checks verify72 pure tests, mypy70/102 files, eight import contracts, AST/Ruff/Django/no migrations/static and180 SQLite tests with three PostgreSQL-only skips. The43-file candidate is not integrated; external PostgreSQL/main gate remains. [Current handoff](HANDOFF_ARCH06_2026-10-19.md). ADR-002 requires daily_trainning_app removal and final model/app/migration reorganization in ARCH-09, with final acceptance in ARCH-10.

## ARCH-07: typed coach context, budgets, jobs and proposals

Coach context reads typed public athlete/catalog/training projections, and job coordination uses public account/billing locking ports. Frozen context and provider response conversion remain in adapters. Typed cases own enqueue/reservation, settlement, claim/quarantine and proposal create/edit/reject/accept using the common ARCH-04 planning contract. Bootstrap composes repositories, clock, UoW, context and injected DeepSeek transport. Legacy training.ai.httpx.Client mocking remains effective; no provider network call is used for verification.

Preserved contracts include lock order, exact quotas/rates, partial token capture, no ambiguous retries, raw selected-plan idempotency and delayed validation, JSON/message byte order, exact original proposal input and historical plan instances. Existing malformed-response defects are recorded in MAM-635/MAM-818 without silent fixes. Three newly certified legacy entry points leave pending inventory; no new typing exception or broad exclusion. Final app/model/migration relocation and remaining generic UI/admin integration stay ARCH-09 under ADR-002.

Local verification:91 pure tests, strict mypy85/129 files, eight import contracts, AST/Ruff/Django/no migrations/static and199 SQLite tests with four PostgreSQL-only skips. Independent40-case differential against integrated baseline shows zero differences. The53-file candidate still requires external PostgreSQL199/no skips and main integration before ARCH-08. See [verification](architecture/ARCH-07-VERIFICATION.md), [parity](architecture/ARCH-07-PARITY.json) and [current handoff](HANDOFF_ARCH07_2026-10-19.md).

## ARCH-08: typed offline synchronization and receipts

Synchronization now coordinates typed operation identity/digest/receipt, deferred boundary source, public account locks/authorization/training execution and a single outer UoW. Identity/canonical hashing remains before receipt lookup; replay precedes authorization and late payload validation. Training owner/revision guards still precede child conversion. Session and receipt commit or roll back together even after an inner execution commit. Original receipt snapshots preserve IDs/order/Decimal scale/missing/zero without reading current rows. Bootstrap injects training snapshot codecs into sync persistence rather than importing foreign adapters from the module.

Canonical JSON, original IndexedDB body including created, owner scope, CSRF and400/403/409 responses remain compatible. Offline assets are unchanged; real browser/device acceptance remains ARCH-10. training/services.py now joins strict scope and leaves pending inventory; two exact silent mixed model frontiers remain until ARCH-09. One local DRF web import boundary is documented in [verification](architecture/ARCH-08-VERIFICATION.md); no broad suppression.

Local candidate:105 pure tests, strict89/140 files, eight import contracts, AST/Ruff/Django/no migrations/static,218 SQLite tests (five PostgreSQL-only skips),23 independent parity cases/zero differences and31-file stable scope. PostgreSQL/main integration remains pending; [current handoff](HANDOFF_ARCH08_2026-10-19.md). Only after readback may ARCH-09 remove daily_trainning_app and reorganize the final persistence/apps/migrations according to ADR-002.


## Registro histórico: presentation ownership and composition completion

The following historical presentation candidate started from main `717cc1b`, before integration in `24484b7` and architecture acceptance. `basis/adapters/web` is a technical Django application without models: shared layouts/forms/notices, `cotton/basis` components and authored `static/basis` resources. Third-party static files retain `static/vendor`. Each business module owns its `adapters/web` routes, views/forms and `adapters/templates/<area>` screens. Training web handlers are split into planning, execution, strength, intervals, progress and trekking; athlete/training model packages export exactly one definition of each registered model.

`bootstrap` constructs and injects services and adapters; it contains no HTTP handlers, ORM selections, JSON conversion or application command dispatch. AST enforcement covers factories, technical adapter core independence and nested web handlers. Export-v1 obtains 19 owner-selected sections through typed area export read ports; foreign ORM schemas do not leave their owning adapters. Historical workout persistence and typed commands reuse one pure reference decision, compatibility policy and metric calculation while retaining defensive validation and `update_fields` semantics.

Password recovery uses explicit `accounts/auth` templates through confirmation and completion, avoiding admin template discovery. The service worker hashes relocated templates/components/static sources, renders a Prettier-formatted plain JavaScript source, and fails explicitly for a missing critical source or resource. The offline shell omits credentials and authenticated documents. Shared form/error/loading components and their parameters/states are documented in [COMPONENTS](COMPONENTS.md).

See [movement map](architecture/PRESENTATION-MOVES.json), [implementation plan](architecture/PRESENTATION-PLAN.md) and [verification](architecture/PRESENTATION-VERIFICATION.md). At that historical capture, Git integration was still pending and ARCH-09/ARCH-10 remained open. Their later integration and acceptance are recorded in the current-state section above; these historical receipts keep their original attribution.
