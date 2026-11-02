# BASIS — auditoría y todos los tickets pendientes

Fecha: **2026-11-02**. Proyecto: **P-MAM-12**. Código auditado: `69eeb04c624b87c4cc4c425042d04f3cea68da20` (`main` y `origin/main`, comprobados tras fetch).

## 1. Alcance y fiabilidad del inventario

Este archivo es la lista local única de trabajo: reúne el análisis, los pendientes conocidos, las ampliaciones de tickets existentes y los tickets locales nuevos. Las prioridades de esta auditoría no sustituyen las prioridades originales de Linear.

- **Readback vigente documentado:** [Linear 2026-11-02](LINEAR_READBACK_2026-11-02.json): 51 IDs únicos, 37 Done y 14 abiertos (12 In Progress, 1 Todo, 1 Backlog). Se leyeron las relaciones de los 14 abiertos; no todos los comentarios ni adjuntos. No se realizó una nueva consulta en esta conciliación.
- MAM-624, MAM-625, MAM-819, MAM-1009 y MAM-1010 constan Done en ese readback. Sus notas inferiores conservan el historial y tareas locales de preservación, sin reabrirlos. MAM-1012 sigue In Progress.
- Los tres identificadores `LOCAL-*` son propuestas locales sin ID remoto, adicionales al conteo de Linear. Los checklists no sustituyen los criterios originales ni crean tickets.
- **Corte histórico:** la auditoría anterior usó 51 IDs, 32 Done y 19 no Done; sus recibos y mediciones se mantienen fechados. GitHub Issues devolvió cero abiertos en aquella consulta.
- Dependencias y relaciones vigentes del readback están en el snapshot y el [plan](PLAN_PARALELIZACION_2026-11-02.md); las listas anteriores de este documento pueden reflejar el corte histórico.

**Leyenda:** P1 alta (corregir antes de habilitar el flujo afectado), P2 media (escalabilidad/mantenibilidad). «Reproducido» significa prueba local ejecutada; «estático» significa código inspeccionado; «pendiente de medir» no equivale a incidente observado.

## 2. Dictamen técnico

La estructura modular es una buena base para cambios: dominio puro, casos de uso, adaptadores y composición explícita. El checker arquitectónico falló inicialmente el 2026-11-02 por el probe fuera de su inventario. La [tanda 0](WAVE0_VERIFICATION_2026-11-02.md) incorpora la ruta al alcance estricto y registra la reparación local: checker, mypy y 229 pruebas de arquitectura pasan; integración y CI remoto siguen pendientes. Las prioridades son cerrar la contabilidad/robustez de IA, optimizar rutas concretas de lectura y completar la aceptación comercial/operativa.

No se constató un cobro duplicado real ni una pérdida monetaria en producción. Sí hay defectos reproducibles que afectan a reservas, trazabilidad del costo y continuidad del worker. Las pruebas existentes conservan explícitamente algunos comportamientos defectuosos por compatibilidad: una suite verde no significa que estén resueltos.

### Hallazgos financieros y de continuidad

| ID | Prioridad / evidencia | Hallazgo, efecto y ubicación | Ticket |
| --- | --- | --- | --- |
| F01 | P1, reproducido por prueba existente | `decode_reply` lanza `AttributeError` para JSON no objeto y no vacío. No lo capturan `Provider.call` ni `Jobs.process_one`; el comando termina y deja el job running hasta cuarentena, con reserva retenida. `coach/adapters/provider.py:53-59,99-115`, `coach/application/jobs.py:289-305`, comando `process_ai_jobs.py:14-21`. | MAM-635 |
| F02 | P1, reproducido con ORM SQLite | Una respuesta con `content=null` llega a `job.answer=None`; la columna `AIJob.answer` no admite NULL. `settle` intenta persistirla, lanza `IntegrityError` y revierte gasto/liberación, dejando running y reserva. `coach/application/jobs.py:229-253`, `coach/adapters/models.py:51`, `coach/adapters/jobs.py:136-148`. | MAM-635 + MAM-818 |
| F03 | P1, reproducido con repositorio falso | `pricing_version` es un literal en el modelo, pero no viaja en `Job` ni se usa al liquidar. `usage_cost` usa constantes actuales. Mismo uso y job encolado: costo pasa de **0.00036120 a 0.00060120 USD** al simular cambio de tarifa de entrada antes del procesamiento. No acredita sobrecargo real; acredita falta de una política versionada efectiva. `coach/adapters/models.py:47`, `coach/domain/jobs.py:80-107,126-141`, `coach/adapters/jobs.py:22-45,121-134`. | MAM-818 |
| F04 | P1, reproducido con repositorio falso | Se solicitó `deepseek-v4-flash`, se reportó `reported`, y el job terminó succeeded/costo 0.00036120 sin activar bloqueo. El nombre reportado se guarda, pero no se comprueba contra la tarifa/modelo admitido. Un cambio de modelo podría invalidar el presupuesto. `coach/application/jobs.py:218-241`. | MAM-818 |
| F05 | P1, estático y contrato existente | Los jobs uncertain conservan reservas; `settle` solo acepta running, y no se encontró caso de uso/comando de conciliación IA. La protección contra reintento ambiguo es correcta, pero falta la vía controlada para resolver costo/reserva y desbloquear servicio. `coach/application/jobs.py:203-214,232-241`, `tests_architecture/test_coach_jobs.py:234-242`. | MAM-818 |
| F06 | P1, aceptación pendiente | Polar tiene validación de producto/precio/moneda/impuestos, firmas, intentos persistentes y conciliación. Sigue pendiente acreditar el circuito real de la app en sandbox, incluido intento ambiguo, trial, revocación y reembolso. No confundir estos pendientes con un defecto confirmado de cobro. | MAM-816 |

Todas las rutas de la tabla anteriores son relativas a `basis/modules/`, salvo las rutas que comienzan por `tests_architecture/`.

**Economía unitaria:** a las constantes actuales, reserva máxima por consulta = `4000 × 0.30/10^6 + 1500 × 1.20/10^6 = USD 0.003`; por plan = `USD 0.006`. Los máximos nominales pagados, 200 consultas y ocho planes, reservan **USD 0.648** por período; prueba, cinco consultas y un plan, **USD 0.021** vitalicios. Están bajo los topes de USD 1 / USD 0.03. Son límites técnicos con esas tarifas, no una factura ni margen neto. USD 5 de ingreso base menos USD 0.648 deja USD 4.352 **antes** de comisiones, infraestructura, correo, soporte, reembolsos y otros costos. Falta calcular el margen neto con contratos y consumos reales (MAM-818/MAM-638); no hay evidencia para afirmar rentabilidad o déficit.

### Rendimiento y optimización

| ID | Prioridad / evidencia | Hallazgo | Ticket |
| --- | --- | --- | --- |
| P01 | P1, reproducido | El detalle de una versión histórica usa `list(plan.sessions.all())`, sin anotaciones; `calendar_status` ejecuta hasta dos `exists()` por fila. Selección + estados: **21 consultas con 10 sesiones, 201 con 100**, sin contar otras consultas de la vista. `training/adapters/web/planning.py:105-138`, `training/adapters/calendar.py:59-77`. | LOCAL-PERF-01 |
| P02 | P2, estático | `effective_sessions` trae todas las prescripciones/versiones del dueño y las ordena en Python. Hoy filtra después; progreso también y vuelve a calcular agenda dentro de `progress_report`. Paginación de la lista no acota la selección inicial. `calendar.py:16-56`, `web/planning.py:66-69`, `web/progress.py:124-149`, `application/progress.py:85-88`. | LOCAL-PERF-01 |
| P03 | P1, estático; contención por medir en PostgreSQL | **Todo enqueue**, incluso pagado, bloquea el mismo `TrialFund` mensual antes de saber si es trial. Mantiene ese bloqueo mientras construye contexto y prepara petición. Serializa cuentas independientes. `coach/application/jobs.py:124-159`, `coach/adapters/jobs.py:78-80`. | MAM-818 |
| P04 | P2, estático; pico de memoria por medir | Exportación materializa ORM → JSON completo → objetos Python → tuplas/listas → JSON final, para todas las secciones. Coste proporcional al historial y múltiples representaciones simultáneas. `basis/adapters/django/export.py:12-16`, `basis/adapters/web/platform_views.py:20-28`. | LOCAL-PERF-02 |
| P05 | P2, estático | `DjangoProgressRepository.sessions` precarga `blocks__intervals`, pero `progress_session` solo lee bloques y series; añade una consulta y carga intervalos que no se utilizan. `training/adapters/progress.py:17-48`. | LOCAL-PERF-02 |
| P06 | P1, capacidad de recuperación por medir | Conciliador atiende 25 cuentas por vuelta y duerme 60 s **después** del trabajo; un ciclo de 1.000 cuentas requiere al menos unas 40 vueltas/minutos, más HTTP y eventos. El filtro de cinco minutos no garantiza una frescura de cinco minutos. HTTP Polar ocurre bajo lock de cuenta en checkout/portal/reconcile. `billing/adapters/management/commands/reconcile_billing.py:28-73`, `billing/application/service.py:94-215`. Riesgo de demora de revocación por eventos perdidos y espera en operaciones de la misma cuenta. | MAM-816 + MAM-638 |

Rutas abreviadas P01–P03/P05/P06: relativas a `basis/modules/`; `calendar.py` y `web/*` pertenecen a `training/adapters/`.

**Corrección ya comprobada:** la ruta efectiva actual no presenta el N+1 que describía la revisión temprana del 1 de noviembre. Benchmark ejecutado nuevamente:

| Sesiones sintéticas de una cuenta | Selección efectiva | Estados extra | Agenda/adherencia | Hoy completo |
| --- | --- | --- | --- | --- |
| 10 | 2 | 0 | 2 | 11 |
| 100 | 2 | 0 | 2 | 11 |
| 1.000 | 2 | 0 | 2 | 11 |

Eso mide consultas, no capacidad para 1.000 usuarios, latencia p95 ni memoria. P01 pertenece a otra rama de ejecución: versión histórica sin anotar.

### Arquitectura y SOLID

| Principio | Evidencia actual | Mejora necesaria |
| --- | --- | --- |
| **S — Responsabilidad única** | Los módulos separan identidad, atletas, catálogo, entrenamiento, pagos, IA y sync. | `Jobs` reúne disponibilidad, enqueue, reservas, liquidación, procesamiento y cuarentena; `Progress` combina métricas y escrituras de trekking. Separar por caso de uso al intervenir esas áreas. |
| **O — Abierto/cerrado** | Puertos `Provider`, `Gateway`, reloj y UoW permiten cambiar infraestructura por composición. | Tarifas, límites y allowlist de modelos están incrustados en funciones. Introducir política de costo inmutable/versionada, sin ramificaciones por proveedor en todos los casos de uso. |
| **L — Sustitución de Liskov** | Hay contratos compartidos para repositorios falsos/Django y UoW. | El fake tolera answer=None mientras Django falla por NOT NULL; contrato de resultados/errores y liquidación debe ser igual para ambos, incluidos malformed y concurrencia. |
| **I — Segregación de interfaces** | `BillingProfiles`, `Clock` y puertos públicos tipados acotan muchas dependencias. | `JobsRepository` agrupa 17 operaciones de fondos, cuotas, colas y servicio; `ProgressRepository` mezcla lectura y escritura. Dividir por consumidor, manteniendo transacción/orden de locks. |
| **D — Inversión de dependencias** | Núcleo independiente de Django; bootstrap inyecta ORM/proveedores, interacciones entre módulos por `public.py`. | Mantener ese límite al optimizar: proyecciones de lectura explícitas y reglas puras; evitar llevar QuerySets o clientes HTTP al núcleo. |

Resultado: base sólida y comprobable, con deuda localizada; los controles estáticos no certifican por sí solos todos los principios. Contrato ampliado en [ARCHITECTURE.md](../ARCHITECTURE.md#solid-y-facilidad-de-cambio--revisión-2026-11-02). Trabajo específico: LOCAL-ARCH-01 y MAM-818.

## 3. Tickets abiertos / pendientes conocidos, actualizados localmente

Cada enlace MAM apunta al ticket existente. Los estados indicados se concilian con el readback del 2026-11-02; las dependencias y checklists conservan el análisis histórico y propuestas locales. Las secciones Done se mantienen para preservar evidencia, no como tickets abiertos.

### MAM-624 — Recuperación, bienestar y respuesta al entrenamiento

[Linear](https://linear.app/mamutsystems/issue/MAM-624) · Done · P2 · dependencias: MAM-620, MAM-618.

Implementación integrada por PR #27 (`5726ad4`); queda un worktree antiguo con 14 archivos modificados y cuatro nuevos.

- [x] Estado Done confirmado en el readback del 2026-11-02; conservar `docs/WELLNESS_VERIFICATION.md` como evidencia histórica.
- [x] Comparar los 18 archivos pendientes con origin/main: 12 blobs idénticos y seis diferentes (`observations.py`, `web/urls.py`, `web/views.py`, `docs/VALIDATION.md`, `test_wellness.py`, plantilla `wellness.html`).
- [ ] Conciliar esas seis diferencias y preservar evidencia antes de retirar el worktree. Se conserva durante esta limpieza.

### MAM-630 — Progreso, recuperación y ajustes del perfil

[Linear](https://linear.app/mamutsystems/issue/MAM-630) · In Progress · P2 · dependencias: MAM-620, MAM-624, MAM-625, MAM-627.

- [ ] Completar aceptación UX/visualizaciones sobre un SHA final, móvil y escritorio; estados vacíos/parciales, períodos, fuentes, navegación y privacidad.
- [ ] Confirmar accesibilidad y comportamiento ante historiales grandes. Coordinar P02 con LOCAL-PERF-01; no dar por cerrado por la integración de MAM-625.

### MAM-632 — Registro offline y sincronización idempotente

[Linear](https://linear.app/mamutsystems/issue/MAM-632) · In Progress · P1 · dependencias: MAM-631, MAM-623, MAM-628, MAM-616.

- [ ] Verificar cortes de red durante guardado, reapertura, respuestas ambiguas, dos dispositivos y conflictos revisables sin duplicación.
- [ ] Verificar logout/cambio de cuenta con cola pendiente, exportación local y actualización del service worker.
- [ ] Adjuntar evidencia de navegadores/dispositivos al candidato final; quitar un worktree vacío no cierra el ticket.

### MAM-633 — Contexto y herramientas de IA sobre servicios deportivos

[Linear](https://linear.app/mamutsystems/issue/MAM-633) · In Progress · P1 · dependencias: MAM-810, MAM-815, MAM-625, MAM-624, MAM-623, MAM-616, MAM-622.

- [ ] Completar matriz de contexto autorizado: propietario, unidades, procedencia, datos faltantes, períodos, límites de bytes/tokens y cambios recientes de bienestar/trekking.
- [ ] Medir consultas y tiempo de congelación del contexto; reducir tiempo bajo locks sin perder consistencia.
- [ ] Acreditar contrato con proveedor y las dependencias funcionales pendientes antes de aceptación.

### MAM-634 — Propuestas de entrenamiento y ciclos con validación/versiones

[Linear](https://linear.app/mamutsystems/issue/MAM-634) · In Progress · P1 · dependencia: MAM-633.

- [ ] Validar generar/revisar/editar/rechazar/aceptar; JSON malformado, preguntas aclaratorias, datos faltantes, plan base sustituido y aceptación repetida.
- [ ] Demostrar que una propuesta no modifica ejecución histórica y que errores no dejan planes parciales; completar evaluación funcional pendiente.

### MAM-635 — Entrenador IA y adaptación con tareas controladas

[Linear](https://linear.app/mamutsystems/issue/MAM-635) · In Progress · **P1** · dependencias: MAM-818, MAM-633, MAM-634, MAM-627.

**Actualización de auditoría: F01 y F02, ya conservados como defectos heredados en pruebas.**

- [ ] Normalizar JSON no objeto y contenido nulo en la frontera del proveedor; devolver error de dominio/controlado sin excepción sin capturar.
- [ ] Mantener reserva y uso parcial cuando no se conoce costo; no repetir solicitudes posiblemente facturadas.
- [ ] Procesar un job válido posterior al inválido sin tumbar el worker; persistir estado terminal/ambiguo coherente.
- [ ] Cambiar las pruebas que hoy esperan `AttributeError`/`IntegrityError` por pruebas del comportamiento corregido, tanto fake como ORM; cubrir rollback y concurrencia PostgreSQL.
- [ ] Completar experiencia visible de estado/error y flujo de adaptación; confirmar alcance original antes de cerrar.

### MAM-636 — Evaluar entrenador antes de habilitar programación/adaptación

[Linear](https://linear.app/mamutsystems/issue/MAM-636) · Backlog · P1 · dependencias: MAM-635, MAM-633, MAM-634.

- [ ] Ejecutar evaluación versionada de programación/adaptación, datos incompletos, síntomas, instrucciones maliciosas y coherencia multideporte.
- [ ] Registrar modelo, prompts, dataset, resultados, límites y decisión explícita de habilitación; pruebas contractuales no acreditan calidad deportiva.

### MAM-638 — Aceptación completa web, móvil, offline e IA

[Linear](https://linear.app/mamutsystems/issue/MAM-638) · In Progress · **P1**.

Dependencias del corte anterior: MAM-818, MAM-815, MAM-816, MAM-820, MAM-817, MAM-637, MAM-632, MAM-625, MAM-629, MAM-630, MAM-628, MAM-636; no todas siguen abiertas.

- [ ] Candidato único integrado, CI PostgreSQL/operations, recorrido completo y decisiones de producto trazables.
- [ ] SMTP/TLS, backup externo/restauración, rollback, alertas, salud de workers y supervisión de conciliación.
- [ ] Medir p50/p95/p99, errores, RSS, filas/consultas, conexiones y espera de locks con usuarios concurrentes e historiales crecientes en PostgreSQL. Acordar SLO antes de aceptar; no extrapolar conteos SQLite.
- [ ] Medir P06: antigüedad máxima de última conciliación, tamaño de cola, timeouts/429 y recuperación de 1.000 cuentas; documentar ventana comercial de riesgo por eventos perdidos.
- [ ] Completar auditoría de dependencias Python, pendiente según handoff, y aceptación física de navegadores/dispositivos.
- [ ] Registrar costos reales de hosting, correo, proveedor y pagos para validar margen neto junto a MAM-818.

### MAM-815 — Carga concurrente y analítica multideporte con procedencia

[Linear](https://linear.app/mamutsystems/issue/MAM-815) · In Progress · P1 · dependencias: MAM-820, MAM-625, MAM-814, MAM-819, MAM-812, MAM-813.

- [ ] Contrastar sesiones consecutivas y recuperación con el alcance original; completar relación con bienestar/trekking.
- [ ] Verificar conservación de unidades/protocolos, cero frente a ausencia, sesiones mixtas y no doble conteo de bloques/intervalos/etapas.
- [ ] Cerrar aceptación propia tras MAM-820; MAM-625 no sustituye este alcance.

### MAM-816 — Polar checkout, portal y webhooks conciliados

[Linear](https://linear.app/mamutsystems/issue/MAM-816) · In Progress · **P1** · dependencia: MAM-810.

- [ ] Completar checkout iniciado desde la app, tarjeta sandbox, webhook y conciliación autoritativa; enlazar evidencia sin secretos (`docs/POLAR_SANDBOX_VERIFICATION.md`).
- [ ] Trial de siete días, USD 5 mensual/exclusive, cancelación al vencimiento, impago, revocación, reembolso y conservación de lectura/exportación.
- [ ] Doble clic, timeout/resultado ambiguo y expiración del intento: probar ausencia de segunda suscripción efectiva mediante evidencia del proveedor, no solo doble HTTP simulado.
- [ ] Incluir P06: medir espera de locks bajo latencia del proveedor y frescura del reconciliador. Si se mueve HTTP fuera de transacción, conservar intento persistente, validación de versión y consistencia de webhook.

### MAM-818 — Cuotas IA y libro de costo con reservas atómicas

[Linear](https://linear.app/mamutsystems/issue/MAM-818) · In Progress · **P1** · dependencias: MAM-633, MAM-817.

**Actualización de auditoría: F02–F05 y P03.**

- [ ] Definir política explícita de precio al encolar/procesar y persistir su versión y tarifas efectivas; que el costo sea reproducible desde el job. Un cambio de tarifa debe conservar la política congelada o invalidar/re-reservar explícitamente antes de llamar al proveedor.
- [ ] Validar modelo reportado contra los alias admitidos para esa versión; desconocido/incompatible conserva evidencia, evita éxito silencioso y activa tratamiento de conciliación.
- [ ] Caso de uso de conciliación de uncertain con referencia/evidencia, idempotencia, actor/motivo, uso/costo y ajuste atómico de cuota/fondo. Conciliar no debe reenviar la petición al proveedor.
- [ ] Probar invariante contable: reservas agregadas = reservas pendientes/ambiguas; gasto = liquidaciones efectivas, sin negativos ni doble liberación. Agregar restricciones DB compatibles con los límites definidos.
- [ ] Eliminar bloqueo global de fondo para cuentas pagadas cuando no lo necesitan; preservar orden de locks y presupuesto trial global. Probar en PostgreSQL que dos cuentas pagadas encolan independientemente y trials concurrentes no superan fondo.
- [ ] Evaluar costos reales, tarifas vigentes documentadas y contingencia de cambio de modelo; mantener aritmética Decimal y redondeo conservador.
- [ ] Coordinar F02 con MAM-635: error de contenido no debe destruir trazabilidad del uso ya recibido.

### MAM-819 — Hiking: tiempos, desnivel, altitud, terreno y mochila

[Linear](https://linear.app/mamutsystems/issue/MAM-819) · Done · P2 · dependencia: MAM-811.

Hay implementación integrada por PR #29 (`3b3350e`). La rama antigua conserva **tres commits no ancestros de main**, pero los cinco archivos que modificaron son **idénticos a origin/main**, comprobado con `git diff` (sin diferencias): `domain/sports.py`, `docs/TRAINING_VARIABLES.md`, `test_hiking.py`, `test_hiking_browser.py` y `test_sport_metrics.py`.

- [x] Estado Done confirmado en el readback del 2026-11-02; conservar `docs/HIKING_VERIFICATION.md` y PR #29 como evidencia histórica.
- [x] Comparar los tres commits antiguos con la integración: equivalencia de los cinco archivos confirmada; conservar la rama mantiene también los SHA originales.
- [x] Retirar la copia de trabajo con archivo verificado de sus 3.433 archivos ignorados (recibo en sección 6); rama conservada.

### MAM-820 — Trekking por etapas, pernoctas y recuperación

[Linear](https://linear.app/mamutsystems/issue/MAM-820) · In Progress · **P1** · dependencias: MAM-819, MAM-624.

Trabajo conservado en `.cache/worktrees/mam820-completion`, base `d0e76d3`, 11 archivos modificados + tres nuevos, sin commit. No incorpora PR #32.

- [ ] Finalizar revisión del candidato existente: validación de fecha/orden/propietario/composición hiking, errores de formulario, etiquetas/unidades y edición de etapas.
- [ ] Revisar capturas móviles finales conservadas y registrar aceptación; no contar inspecciones interrumpidas como realizadas.
- [ ] Crear commit acotado del trabajo existente e incorporar main sin perderlo; verificar el árbol combinado con progreso PR #32.
- [ ] Ejecutar suite y carrera PostgreSQL de dos cambios de fechas incompatibles: un éxito, un rechazo, un recibo, orden válido.
- [ ] Publicar, revisar CI e integrar antes de cerrar; conservar evidencia antes de retirar worktree.

### MAM-1008 — Estabilización del candidato (épica)

[Linear](https://linear.app/mamutsystems/issue/MAM-1008) · In Progress · P1.

- [ ] Confirmar aceptación de MAM-1009/1010 integrados y completar MAM-1011/1012.
- [ ] Incorporar esta auditoría como evidencia y relacionar los tres tickets locales cuando Linear esté disponible.

### MAM-1009 — Aislar regresión Polar y rechazar red en pruebas

[Linear](https://linear.app/mamutsystems/issue/MAM-1009) · Done · P1 · padre: MAM-1008.

- [x] Corrección integrada en PR #26; prueba usa el símbolo inyectado y barrera de transporte. Suite focal de esta auditoría pasa.
- [x] Estado Done confirmado en el readback del 2026-11-02.

### MAM-1010 — Formato web reproducible en Windows

[Linear](https://linear.app/mamutsystems/issue/MAM-1010) · Done · P2 · padre: MAM-1008.

- [x] `.gitattributes` y corrección incluidos en PR #26; CI posterior de main consta success.
- [x] Estado Done confirmado en el readback del 2026-11-02. La auditoría histórica no repitió todo el formato web.

### MAM-1011 — Exigir PR y CI para integrar en main

[Linear](https://linear.app/mamutsystems/issue/MAM-1011) · Todo · **P1** · padre: MAM-1008.

- [x] Política aplicada y leída de nuevo el 2026-11-02: PR, checks `postgres`/`operations` de GitHub Actions, rama actualizada y conversaciones resueltas; cero aprobaciones humanas obligatorias. Administradores incluidos, sin force push ni borrado. [Recibo](MAM1011_VERIFICATION_2026-11-02.md).
- [ ] Verificar que un candidato con check fallido no integre y que uno válido sí pueda hacerlo.
- [x] GET independiente devuelve `protected=true`. El `protected=false` del diagnóstico inicial queda como historia; este cambio no cierra automáticamente MAM-1011 ni modifica su estado remoto.

### MAM-1012 — Conciliar roadmap y retirar worktrees integrados

[Linear](https://linear.app/mamutsystems/issue/MAM-1012) · In Progress · P2 · padre: MAM-1008.

- [x] Reunir los 51 IDs conocidos y los nuevos pendientes en este archivo, sin borrar estados históricos.
- [x] Fetch y comparación main/remoto sobre `69eeb04`; documentación del SHA/CI real.
- [ ] Integrar y verificar la conciliación documental; el readback del 2026-11-02 se utiliza localmente y no implica actualizar ni cerrar Linear.
- [x] Retirar siete worktrees con respaldo verificado; conservar MAM-624/MAM-820 con trabajo pendiente. Auditoría publicada en main/remoto (`0d17abb`); recibo de limpieza detallado en sección 6.

### LOCAL-PERF-01 — Acotar lecturas de calendario y eliminar N+1 histórico

**Nuevo local · Todo · P1 · sin ID remoto**. Relacionados: MAM-629, MAM-630, MAM-625 (cerrado), MAM-638. Evidencia: P01/P02.

- [ ] Anotar en lote ejecuciones/estados en la rama de versiones históricas; mantener semántica de raíz/copia y aislamiento por cuenta.
- [ ] Diseñar una proyección de agenda acotada por fecha/linaje que resuelva versiones **antes** de filtrar/paginar. Un `date__range` ingenuo antes de resolver raíces podría resucitar prescripciones sustituidas.
- [ ] Evitar recalcular la misma agenda dos veces dentro de progreso; reutilizar una proyección/request o contrato de lectura específico, sin caché global obsoleta.
- [ ] Aceptación: selección+estados con 10/100/1.000 filas mantiene un número constante de consultas; probar raíz fuera de rango/copia dentro y viceversa, canceladas, ejecutadas, cortes de versión y otra cuenta.
- [ ] Medir filas materializadas, RSS, tiempo y `EXPLAIN (ANALYZE, BUFFERS)` PostgreSQL con historial/versiones crecientes. Registrar plan/índices antes de añadirlos.

### LOCAL-PERF-02 — Reducir materialización de exportación y progreso

**Nuevo local · Todo · P2 · sin ID remoto**. Relacionados: MAM-638, MAM-630. Evidencia: P04/P05.

- [ ] Retirar prefetch de intervalos no consumidos, verificando paridad de totales y no doble conteo.
- [ ] Medir exportaciones de 1.000/10.000/100.000 registros sintéticos: RSS, tiempo, bytes y consultas.
- [ ] Implementar lectura/serialización por lotes o streaming que mantenga `basis-export-v1`, todos los datos y aislamiento. Definir consistencia del snapshot y comportamiento ante interrupción; exportación no debe truncar silenciosamente el historial.
- [ ] Aceptación: mismo contenido semántico y permisos, menor memoria máxima demostrada en fixture grande, consultas por lote previsibles y ausencia de caché pública de datos privados.

### LOCAL-ARCH-01 — Segregar contratos y casos de uso para facilitar cambios

**Nuevo local · Todo · P2 · sin ID remoto**. Relacionados: MAM-635, MAM-818, MAM-820; precedencia recomendada: estabilizar contabilidad antes de refactorizarla.

- [ ] Separar responsabilidades de enqueue/reserva, liquidación y procesamiento con puertos pequeños; separar lectura de progreso y escritura de trekking.
- [ ] Política de costo/modelo versionada compartida por reserva y liquidación (coordinada con MAM-818), inyectada desde bootstrap.
- [ ] Contratos fake/Django comunes para None/ausencia, errores, transacciones, duplicados y resultados ambiguos; conservar ownership, idempotencia y orden de locks.
- [ ] Aceptación: cambiar proveedor/lector implica nuevo adaptador y composición, sin editar reglas deportivas ni vistas de otros módulos; núcleo se importa sin Django y pasan tipos/contratos/límites.
- [ ] Refactorizaciones pequeñas con paridad; no incorporar repositorio CRUD universal, bus genérico ni infraestructura sin un consumidor concreto.

## 4. Todos los cerrados conocidos y discrepancias resueltas

Los 32 Done del corte histórico del 1 de noviembre se enumeran para comprobar cobertura y evitar recrearlos:

| ID | Trabajo | Estado de fuente |
| --- | --- | --- |
| MAM-615 | Arranque y entorno reproducible | Done |
| MAM-616 | Cuenta/atleta y privacidad | Done |
| MAM-617 | Historial e integridad | Done |
| MAM-618 | Contrato deportivo | Done |
| MAM-619 | Métricas de fuerza/RPE | Done |
| MAM-620 | Perfil y configuración | Done |
| MAM-621 | Catálogo de ejercicios | Done |
| MAM-622 | Objetivos/ciclos/calendario versionado | Done |
| MAM-623 | Prescripción y ejecución por serie | Done |
| MAM-626 | Contrato UI/UX | Done |
| MAM-627 | Cotton/HTMX/tokens | Done |
| MAM-628 | Hoy/reproductor | Done |
| MAM-629 | Calendario/editor | Done |
| MAM-631 | PWA y recursos offline | Done |
| MAM-637 | Despliegue/PostgreSQL/backups/CI | Done |
| MAM-810 | Registro/verificación/recuperación | Done |
| MAM-811 | Resistencia/intervalos/umbrales | Done |
| MAM-812 | Running | Done |
| MAM-813 | Ciclismo | Done |
| MAM-814 | Natación | Done |
| MAM-817 | Prueba/permisos/conservación | Done |
| MAM-821 | Épica arquitectura hexagonal | Done |
| MAM-822 | ARCH-01 contratos/controles | Done |
| MAM-823 | ARCH-02 flujo entrenamiento | Done |
| MAM-824 | ARCH-03 identidad/atleta/catálogo | Done |
| MAM-825 | ARCH-04 planificación/versiones | Done |
| MAM-826 | ARCH-05 métricas/multideporte | Done |
| MAM-827 | ARCH-06 facturación | Done |
| MAM-828 | ARCH-07 entrenador IA | Done |
| MAM-829 | ARCH-08 sincronización | Done |
| MAM-830 | ARCH-09 integración/retiro legado | Done |
| MAM-831 | ARCH-10 aceptación arquitectura | Done |

**MAM-625 — Progreso/adherencia/carga:** In Progress en snapshot, **Done en handoff posterior**. PR #30/#31/#32 integraron períodos, marcas, fuentes y RPE descriptivo. `main=69eeb04`; CI remoto [41359093108](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/41359093108) leído en esta auditoría: completed/success. No se reabre ni se presenta P01/P02 como fallo ya corregido por ese cierre; el trabajo adicional queda explícito en LOCAL-PERF-01.

En ese corte histórico se identificaron 51 IDs: 18 en seguimiento + 32 Done + MAM-625 con cierre posterior. El readback vigente registra 37 Done y 14 abiertos; los tres IDs locales son adicionales.

## 5. Evidencia histórica ejecutada en esta auditoría

El checker principal falló en el diagnóstico posterior del 2026-11-02, como se indica arriba; el resultado de la tabla pertenece al corte auditado anterior.

| Comprobación | Resultado |
| --- | --- |
| `python -m unittest discover -s tests_architecture` | 229 pruebas, OK, 3.800 s |
| `python scripts/architecture_check.py` | VERIFIED: límites de capas/public e inventario legado |
| `lint-imports` | 385 archivos, 1.670 dependencias, ocho contratos conservados |
| Tests coach_jobs, coach_edges, billing_ai, billing_polar y adaptadores billing | 68 pruebas, OK, cuatro omitidas por capacidades PostgreSQL, 2.241 s |
| `benchmark_calendar_queries` con SQLite en memoria | Una prueba OK, 2.210 s; matriz 2/0/2/11 para 10/100/1.000 sesiones |
| Tres probes de auditoría, SQLite/fakes sin proveedor | OK, 0.133 s: N+1 histórico 21/201; tarifa mutable; modelo inesperado aceptado |
| Probes tras moverlos al directorio de evidencia y formatearlos | Tres pruebas OK, 0.151 s, mismos resultados; Ruff check pasa |
| Cobertura del inventario | VERIFIED: 51 IDs fuente; 19 abiertos del corte contabilizados, 18 headings pendientes y tres IDs locales únicos; enlaces locales válidos |
| Diff de documentación | `git diff --check` sin errores; tres documentos ajenos no rastreados conservados |
| GitHub API branch main | SHA 69eeb04, protected=false |
| GitHub CI del SHA auditado | Run 41359093108 completed/success; se consultó estado, no se repitieron sus jobs |

Los tests de F01/F02 existen en `basis/bootstrap/tests/test_coach_edges.py:333-339` y `test_coach_jobs.py:47-75`: esperan las excepciones heredadas; el OK **reproduce** el defecto. Los tres probes se conservan en [evidence/probes_2026_11_02.py](evidence/probes_2026_11_02.py). Son reproducciones del comportamiento auditado, no pruebas de una corrección; dejarán de describirlo al resolver los tickets.

Reproducción de la suite focal (PowerShell, desde la raíz; siempre base desechable):

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:DJANGO_DEBUG = '1'
$env:DJANGO_SECRET_KEY = 'audit-synthetic-only'
$env:AI_ENABLED = '0'
.venv-win/Scripts/python.exe manage.py test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges tests.regression.test_billing_ai tests.regression.test_billing_polar basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar --noinput
$env:PYTHONPATH = 'scripts'
.venv-win/Scripts/python.exe manage.py test benchmark_calendar_queries --noinput
$env:PYTHONPATH = 'docs/tickets/evidence'
.venv-win/Scripts/python.exe manage.py test probes_2026_11_02.AuditProbes --noinput
```

No ejecutados en esta auditoría: PostgreSQL local/concurrencia, carga sostenida, proveedor/pagos reales, dispositivos, despliegue, costo real ni escaneo completo de dependencias. No se modificó lógica productiva para corregir los hallazgos: quedan en los tickets anteriores.

## 6. Git, worktrees y sincronización

El usuario confirmó que «WordPress» significaba **worktrees**, y autorizó retirar los integrados conservando antes los datos locales ignorados.

- Inicial: main y origin/main iguales; tres documentos ajenos no rastreados en `docs/` conservados.
- Retirada **completada**: MAM-629, MAM-631, MAM-632, MAM-816-sandbox, MAM-test-polar-clock y main-postmerge-20261031; todos sin cambios rastreados/no rastreados y HEAD ancestro de origin/main.
- Archivo de preservación: `.cache/worktree-archives-2026-11-02/`, un tar.gz y un manifiesto SHA-256 por worktree; incluye bases, evidencias, entornos y demás archivos ignorados. Se comprueba contenido archivado y original antes de la retirada. Datos privados locales, fuera de Git.
- MAM-819 **retirado** tras comprobar equivalencia exacta de los cinco archivos modificados por sus tres commits; rama conservada, 3.433 archivos ignorados preservados en archivo de 7.074.508 bytes. Recibo: `.cache/worktree-archives-2026-11-02/receipt-MAM-819.json`.
- Conservar MAM-624 (18 archivos pendientes, seis diferentes de main) y MAM-820 (14 archivos pendientes). MAM-820 requirió excepción `safe.directory` **solo por comando**, con ruta exacta del worktree conocido; no se cambió configuración global ni propietario.
- `git worktree list --porcelain` final: únicamente el checkout principal, MAM-624 y MAM-820. No se borraron ramas ni se forzó ninguna retirada.
- Auditoría publicada como `0d17abb09516e0cdae23fc45e5441120cd5bfe97`; HEAD, origin/main y API GitHub coincidieron tras push. Este recibo se incorpora en un commit documental posterior. El CI citado arriba pertenece al código auditado `69eeb04`, no es una ejecución del commit documental final.

**Recibo final de limpieza — VERIFIED:** los siete directorios retirados ya no existen, los manifiestos coinciden con los tamaños/cantidades y todos los objetos de commit originales siguen disponibles. La rutina comprobó SHA-256 de cada archivo original y de su copia en el tar antes de retirar el worktree.

| Worktree retirado | Archivos ignorados preservados | Archivo tar.gz (bytes) |
| --- | --- | --- |
| MAM-629 | 22.998 | 110.635.781 |
| MAM-631 | 23.615 | 115.075.520 |
| MAM-632 | 0 | 92 |
| MAM-816-sandbox | 1 | 296 |
| MAM-test-polar-clock | 3.390 | 7.006.697 |
| main-postmerge-20261031 | 225 | 733.607 |
| MAM-819 | 3.433 | 7.074.508 |
| **Total** | **53.662** | **240.526.501** |

Recibos locales: `.cache/worktree-archives-2026-11-02/receipt.json` y `receipt-MAM-819.json`. Conservar esa carpeta: contiene las bases/evidencias archivadas, no solo caché regenerable. Los respaldos no se publicaron en Git. Los tres documentos previos no rastreados y los cambios de MAM-624/MAM-820 también permanecen locales; sincronizar main no significa haber integrado ese trabajo pendiente.

## 7. Orden recomendado

1. MAM-635 + MAM-818: errores de proveedor, costo versionado, modelo, conciliación y locks; LOCAL-PERF-01 para el N+1 histórico.
2. MAM-816 + MAM-638: aceptación comercial y capacidad/frescura operativa; MAM-1011 y conciliación de estados MAM-1012.
3. Terminar candidato MAM-820 y cerrar aceptaciones MAM-815/MAM-630/MAM-632 con dependencias verificadas.
4. LOCAL-PERF-02 y LOCAL-ARCH-01 en cambios pequeños medidos; completar cadena IA MAM-633/634/635/636 antes de habilitarla.
