# Entradas y casos de uso

Estado: candidato de remediación de ARCH-09, pendiente de aceptación PostgreSQL e integración en main. Esta tabla documenta cadenas revisadas en fuente; los controles de imports o el número de pruebas por sí solos no prueban estas responsabilidades.

| Entrada | Aplicación responsable | Límite preservado |
| --- | --- | --- |
| Registro, verificación, reenvío, recuperación | accounts: Identity y Recovery | Tokens/correo/session son adaptadores Django; inscripción coordinada en una UoW |
| Perfil, preferencias, medición, deporte y bienestar | athletes: Athletes | Propietario desde cuenta autenticada; valores tipados y validación pura |
| RM e historial por formulario o DRF | athletes: RecordRM y RecordWorkout | Referencia medida y congelada; cálculo antes de escribir incluso con repositorio falso permisivo |
| Admin de perfiles, RM e historial, incluidos inline y borrado múltiple | athletes: AthleteAdministration | Permisos staff/modelo nativos; rollback completo ante borrado protegido |
| Catálogo DRF/admin | catalog: Catalog y CatalogAdministration | Autorización y límites del ejercicio en aplicación/dominio; lectura de nombres por contrato público |
| Objetivos, ciclos, calendario, planes y versiones | training: Planning | Contextos tipados, propiedad/autorización, validación previa, versiones e historia |
| Sesión manual, bloque, métricas, serie e intervalo | training: ManualTraining | Comandos concretos, revisión/inmutabilidad puras y UoW explícita |
| Inicio de sesión programada | training: preflight manual y Training.start | Prescripción válida, copia privada y transacción de ejecución |
| Resultados y finalización, incluida metadata sincronizada | sync: Synchronization.apply y training: Training.record | Sesión y recibo atómicos; revisión/propiedad y snapshots históricos de replay |
| Progreso, senderismo y etapas de trekking | training: Progress | Cálculos puros, unidades y ausencia frente a cero |
| Suscripción, checkout, portal, conciliación | billing: Billing | Política comercial separada de Polar; aprovisionamiento de lectura sin guardia de escritura |
| Webhook Polar | billing: Webhooks | Firma en adaptador; idempotencia y fases duraderas en aplicación |
| Trabajos IA y propuesta/aceptación | coach: Jobs y Proposals; training: Planning | Reserva/liquidación/ambigüedad; mismo PlanDefinition que planificación manual |
| POST offline | sync: Synchronization.apply | Contenido canónico, replay antes de validación tardía, errores y cola existentes |
| Comandos process_ai_jobs, link_legacy_profile y reconcile_billing | Casos coach, accounts y billing | Selección operativa de candidatos como lectura propia; mark_pending entra por UoW |
| Exportación, CSRF, manifest, service worker y health | Adaptadores de presentación/framework | Sin una vía alternativa de escritura de negocio |

Bootstrap inyecta repositorios, autorizadores, reloj, unidad de trabajo, proveedores y proyecciones entre módulos. Los formularios de entrenamiento obtienen RM elegibles mediante RMChoices; el admin de atletas obtiene datos del ejercicio mediante ExerciseNames. No importan modelos o adaptadores de otro módulo.

La coordinación de métricas del historial vive en athletes.application.workouts y consume training.public. Sus valores WorkoutMetrics/WorkoutContext son locales al dominio de atletas: esto evita una dependencia indirecta de dominio a aplicación que Import Linter detectó y que no se silenció.

Django conserva autenticación, contraseñas, sesiones, permisos, widgets y operaciones de esquema. Los fixtures de desarrollo y aceptación son excepciones explícitas de bootstrap, restringidas a entornos de desarrollo o bases temporales; no son entradas normales del producto. No hay catálogo de programas predefinidos: PlanDefinition solo prepara una futura fuente sin compartir resultados o versiones del atleta.

Pruebas pertinentes: contratos falsos/Django de planificación y ejecución; test_manual_training, test_athlete_records, test_athlete_administration, test_catalog_policies y los tests bootstrap de administración/lecturas. La suite de regresión conserva los 111 escenarios originales; la evidencia de paridad compara nombres y cantidades de assertions por archivo. Las carreras y bloqueos requieren el recibo PostgreSQL nuevo. Los recorridos de navegador incluyen escritura offline real, replay, 409, CSRF, separación de cuentas y cierre de sesión confirmado por el servidor.
