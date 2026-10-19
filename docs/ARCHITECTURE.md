# Arquitectura y límites de operación

## ADR-001 — Arquitectura hexagonal y tipado estricto (2026-10-19)

**Decisión aceptada, migración en curso.** Épica BASIS-ARCH/MAM-821. Arquitectura antes de retomar aceptación funcional. ARCH-01/MAM-822 establece contratos y controles; los flujos existentes siguen en el legado hasta ARCH-02. Los directorios vacíos son límites reservados, no funcionalidades migradas. No se ha cambiado el esquema ni el registro de modelos Django.

`basis/modules/<área>/{domain,application,adapters}` agrupa cada responsabilidad. `public.py` es la única entrada entre módulos y declara `__all__`; inicialmente no exporta operaciones. `basis/shared` contiene identificadores distintos y los protocolos Clock/UnitOfWork. `basis/bootstrap` conectará implementaciones por inyección explícita. Las capas dependen hacia dentro: adaptadores → aplicación → dominio; dominio no importa aplicación. Shared no importa módulos de negocio. Los contratos públicos solo exportan dominio/aplicación y nunca adaptadores.

| Módulo | Responsabilidad y fuente actual | Etapa principal |
| --- | --- | --- |
| accounts | Identidad/verificación/recuperación en training/views y daily_trainning_app | ARCH-03 |
| athletes | Perfil/preferencias/mediciones/bienestar y RM/historial heredado | ARCH-03, ARCH-05 |
| catalog | Ejercicios y variantes en daily_trainning_app | ARCH-03 |
| training | Ejecución, planificación/versiones, métricas y multideporte en training/models, services, domain, forms y views | ARCH-02, ARCH-04, ARCH-05 |
| billing | Acceso comercial/Polar en training/access y billing | ARCH-06 |
| coach | Contexto/propuestas/trabajos/presupuesto en training/ai y proposals | ARCH-07 |
| sync | Revisiones/recibos/conflictos en training/services y vistas API | ARCH-08 |

### Contratos de implementación

Comandos y resultados serán dataclasses; puertos Protocol específicos del caso de uso. Sin repositorio CRUD genérico ni bus obligatorio. Identificadores de cuenta, atleta (PK del perfil), sesión UUID, sesión programada, plan y revisión son NewType diferentes. Los identificadores públicos externos conservarán su representación actual mediante adaptadores. Cargas y dinero usan Decimal; fechas explícitas; None conserva ausencia frente a cero. El núcleo no recibe ORM, QuerySet, HTTP, Any ni JSON libre. Los adaptadores validan y convierten entradas externas y traducen errores propios a los errores HTTP/DRF/formularios existentes.

La UoW Django confirmará explícitamente éxito y revertirá ante error o salida sin commit, también dentro de transacciones anidadas. Sesión y recibo se guardarán juntos. Conservar el orden de bloqueo y la política de reservas/resultados ambiguos del legado. ARCH-02 debe probar estos contratos sobre el adaptador real antes de cerrar.

### Planes y extensión futura

ARCH-04 introducirá una definición tipada independiente de procedencia, con validación/creación privada comunes a manual e IA. Un futuro adaptador de programas podrá resolver ejercicios y fechas por ese contrato. Cada instancia conserva versión, prescripciones y resultados propios; editar una fuente no cambia historia. Esta migración no implementa catálogo, publicación ni interfaz de programas.

### Controles de frontera y tipado

`python scripts/architecture_check.py` analiza incluso importaciones relativas y TYPE_CHECKING: núcleo independiente, capas, acceso entre módulos por public, ausencia de Any explícito y rutas declaradas. Rechaza infraestructura HTTP/configuración/persistencia en el núcleo y ejecución/importación dinámica directa. Import Linter verifica ocho contratos del grafo, incluidos caminos indirectos. Son controles estáticos; no pretenden probar ejecución arbitraria ni reemplazar la revisión de interfaces. Las pruebas importan todo el núcleo usando Python -I -S, sin site-packages, ajustes ni Django.

`mypy-core.ini`: estricto, sin plugin ni inicializar Django; `mypy-django.ini`: estricto con django-stubs/test_settings para basis, incluidos adaptadores y bootstrap. No hay ignore_missing_imports ni exclusiones globales. Ambas configuraciones prohíben Any explícito y procedente de imports sin tipos. Las áreas migradas deben agregarse al alcance estricto desde su primer commit, y salir del inventario pendiente; las excepciones locales de terceros se documentarán individualmente (ninguna en ARCH-01).

Se fijan Python 3.13, Django 5.2.18, mypy 1.19.1 y django-stubs/django-stubs-ext 5.2.9, compatibles según la [matriz del proyecto django-stubs](https://github.com/typeddjango/django-stubs#version-compatibility). Import Linter 2.11. El inventario `docs/architecture/legacy-baseline.json` congela los archivos de 08dcd02; `legacy-pending.json` solo puede reducirse. El control compara HEAD y HEAD^ donde existen; CI obtiene dos commits. El legado no está certificado como estrictamente tipado por estas configuraciones. Las migraciones históricas y wrappers Django se conservarán según necesidad, y se registrarán sus límites de aceptación.

### Ejecución y evidencia

ARCH-01 → ARCH-02 → ARCH-03 → ARCH-04 → ARCH-05 → ARCH-06 → ARCH-07 → ARCH-08 → ARCH-09 → ARCH-10; una rama/commit por entrega e integración verificada antes de la siguiente. Reversión por commits inversos, conservando esquema y contratos. No corregir funcionalidad silenciosamente. [Plan de ejecución](ARCHITECTURE_EXECUTION.md), [evidencia](architecture/ARCH-01-VERIFICATION.md) y [readback Linear](architecture/linear-readback.json). Los 35 tickets funcionales conservan identidad/historial: cuatro Done y 31 abiertos bloqueados por la épica. Código integrado no implica aceptación funcional completa.

## Implementación existente y límites que deben conservarse


Monolito modular Django con plantillas en servidor y API de sesión/CSRF. `daily_trainning_app` conserva los perfiles, catálogo, RM y registros anteriores. `training` contiene planificación, ejecución, bienestar, trekking, sincronización y los límites de proveedores. Los servicios transaccionales se comparten entre vistas web, sincronización y aceptación de propuestas.

La cuenta `auth.User` se vincula explícitamente a un perfil privado mediante OneToOne. Todas las consultas privadas se filtran por la cuenta autenticada; un identificador enviado por el navegador nunca elige el dueño de un registro. El catálogo común se administra mediante permisos de personal. Los ejercicios referenciados se protegen frente al borrado en cascada.

Una prescripción contiene bloques y series/intervalos objetivo; una ejecución recibe una copia y registra resultados por separado. Las ejecuciones completadas son inmutables por los flujos de aplicación. Revisar un plan crea una versión y copia únicamente sesiones futuras sin ejecución. Las relaciones históricas permanecen en la versión original. No existe una inferencia retroactiva de resultados ausentes.

## Interfaz y PWA

Los estilos se modifican desde `assets/css/tokens.css`: paleta primitiva, superficies, texto, acento, foco, espaciado, tipografía, radios, sombra y movimiento. Las variables semánticas se mapean al tema Cotton UI; el modo oscuro usa el mismo contrato. Las composiciones Cotton están en `templates/cotton/`. HTMX actualiza el estado de trabajos IA; los formularios ordinarios también funcionan con navegación normal.

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

`/health/` comprueba una consulta de base de datos. CI propone migraciones, lint, tests PostgreSQL y estáticos. Los scripts respaldan formato custom y restauran exclusivamente en una base nueva de pruebas. SMTP, respaldos externos, alertas, despliegue TLS y capacidad de 1.000 usuarios activos requieren verificación operativa adicional. No se ha activado infraestructura de producción.

## Fuentes de contratos

- [Django 5.2](https://docs.djangoproject.com/en/5.2/), [Cotton UI](https://django-cotton.com/ui/installation), [temas Cotton UI](https://django-cotton.com/ui/theming), [HTMX](https://htmx.org/docs/).
- [Polar Customer State](https://polar.sh/docs/integrate/customer-state), [checkout](https://polar.sh/docs/api-reference/2026-10/checkouts/create-checkout-session), [webhooks](https://polar.sh/docs/integrate/webhooks/delivery), [pruebas](https://polar.sh/docs/features/subscriptions/trials).
- [DeepSeek: modelos y precios](https://api-docs.deepseek.com/quick_start/pricing/), [modo de pensamiento](https://api-docs.deepseek.com/guides/thinking_mode).
