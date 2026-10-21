# MAM-622 / BASIS-008 — planificación versionada

## Contrato de la entrega

Objetivo propio → plan → macro/meso/micro → prescripción, con fechas contenidas y sin duración universal. La edición incremental permite borradores; iniciar una sesión requiere bloques. El contrato deportivo de variables no cambia.

Mover, cancelar, omitir y sustituir una sesión crean **otra versión del plan**. La fila y los bloques anteriores se conservan. Cada cambio nuevo exige motivo explícito (1–1000 caracteres), registra propietario autor, `created_at`, fecha efectiva local y tipo de cambio. La sustitución copia prescripción sin resultados; el catálogo/editor existente sigue disponible en la nueva versión. La aceptación explícita de una propuesta conserva ese acto como motivo de versión; no se fabrican motivos deportivos para datos legados.

Una restauración produce vN+1, con `previous=vN` y `restored_from` apuntando a la versión elegida. Restaura **intención futura sin ejecución**, no rebobina resultados. Las ejecuciones iniciadas/completadas mantienen su prescripción original. Una sesión de hoy sin resultados no se etiqueta omitida automáticamente.

El editor incremental permite construir bloques/filas y rellenar por primera vez métricas desconocidas. Cambiar una fila prescrita existente o métricas objetivo ya presentes en la prescripción raíz exige crear antes una versión con motivo; así la ruta de edición no elude la conservación del original. La copia nueva se puede editar mientras siga vigente y sin ejecución.

## Contrato canónico para 623

- Identidad de intención: `PlannedSession.origin_id or PlannedSession.pk`. `origin` apunta siempre a la primera prescripción conocida; `supersedes` apunta a la copia utilizada para crear la versión (en restore, a la versión seleccionada). Ambos son FK `PROTECT`. Una versión no puede contener dos copias del mismo origen conocido.
- `revision` es la revisión optimista de la fila; al copiar aumenta. No es `TrainingPlan.version` ni `Session.revision`.
- Estado de planificación persistido: `scheduled`, `skipped`, `cancelled`. Estado de ejecución sigue siendo `in_progress` o `completed`. Las lecturas muestran Programada, En curso, Completada, Omitida, Cancelada o Pendiente pasada; no crean ejecuciones cero.
- Inicio de una prescripción sustituida/cancelada/omitida o de una intención completada es rechazado. Reintentar el inicio vigente devuelve su ejecución en curso. Una ejecución ya iniciada puede seguir editándose desde su propio identificador aun si el plan cambió.
- Orden común de bloqueos: **cuenta real (`AUTH_USER_MODEL.pk`) → ancla de linaje → prescripción → ejecución**, en el mismo alias de la operación. La cuenta no es `Athlete.pk`, un actor recibido ni la columna pública de la cola. `basis.adapters.django.account_locks.lock_account` es el helper compartido con `DjangoAccountLocks` de sync/coordinar presupuestos y con los escritores de training. La cuenta debe mantenerse hasta el COMMIT exterior: las FK de propietario/autor pueden comprobarse diferidamente en ese punto. Ancla = primera versión persistida del linaje; no cambia al publicar un sucesor.
- `lock_plan`, `lock_scheduled`, `lock_execution` incluyen la cuenta antes de bajar al agregado; inicio y bulk también usan ese helper de cuenta. Las lecturas de escritura se limitan al propietario antes de tomar locks de filas identificadas por el cliente, para no esperar por una cuenta ajena. Los locks/replay de receipts siguen en su UoW exterior; no se liberan en el savepoint interior de registro. Los locks de presupuesto ya existentes conservan su orden (fondo de pruebas, cuenta, billing/uso); training no adquiere fondo ni billing después del linaje. No esperar a otra transacción desde una barrera mientras se retienen bloqueos mutuamente necesarios.
- Los endpoints soportados usan `default`. Helpers y `DjangoUnitOfWork(using=...)` propagan el mismo alias también a atomic/rollback; se comprueban con un alias no predeterminado y procesos distintos. No se añade una API multi-base de datos. SQLite abre primero la conexión perezosa (su inicialización configura `transaction_mode`) y luego reserva el escritor con `BEGIN IMMEDIATE` en el UoW superior; sync utiliza el mismo UoW para que su transacción exterior no sea diferida. Los UoW anidados conservan la transacción del llamador.
- 623 debe preservar el vínculo de prescripción de una ejecución; record/sync no permiten reasignar una ejecución ya vinculada a otra intención. No modificar estos archivos en paralelo sin coordinar el contrato.

## Calendario, historia y zona horaria

`effective_sessions` es la proyección común de calendario, Hoy y adherencia. Selecciona la copia más reciente por origen conocido, conserva prescripciones pasadas y las que tienen ejecución, y excluye intención futura sustituida. Canceladas se muestran pero no cuentan como programadas en adherencia; omitidas cuentan como no completadas. Las versiones originales siguen consultables y exportables.

Las filas anteriores a la migración no reciben vínculos inferidos por título, fecha o deporte. Sin origen probado se mantiene el corte histórico por fecha de creación del sucesor, convertido a la zona del propietario; las versiones nuevas tienen `effective_on` explícito. No es posible reconstruir traslados que ya sobrescribieron su fecha antes de esta entrega.

La fecha de Hoy, inicio, revisión/restauración y corte del informe se obtiene de la zona IANA del atleta mediante `AthletePresentation.timezone`, contrato público de solo lectura. No consulta datos privados de athletes desde training ni crea preferencias al leer. Zona ausente utiliza la configuración del producto. No se convierte una disponibilidad parcial o ausente en una prohibición global ni se interpretan limitaciones libres como diagnóstico. Cambios entre microciclos deben escoger un destino del mismo plan y pasar contención temporal.

## Correcciones de revisión R1/R2/R3 (registro histórico)

La revisión independiente del candidato authored `836380…` fue **BLOCK**: el contrato de lock anterior omitía la cuenta y las FK al COMMIT, y las ocho carreras iniciales no cubrían ese cruce. Sus reportes/logs se conservan como historia, no como aceptación del candidato corregido.

El editor usa la lectura anterior al lock solo para localizar el padre. Revisión, elegibilidad, disciplina y objetivos se leen/validan bajo el bloqueo común; un número de revisión anticipado no autoriza usar un target vacío antiguo. Dos POST concurrentes con revisiones1/2 deben conservar la primera carga1800, rechazar la segunda999 sin versión/motivo y no avanzar a revisión3.

El cambio web usa `action` como discriminador. `cancelled`/`skipped` con `replacement`, y `replace` sin referencia, son formularios400 sin nueva versión; no se reinterpretan como otra acción. El puerto también rechaza sustitución combinada con estado de cancelación/omisión. Motivo y metadatos del servidor conservan su autoridad.

El contrato de ejecución pendiente623 (congelación de la copia por sync, IDs de hijos, adaptaciones y semántica parcial) no se amplía en esta corrección. El nuevo gate/report de revisión debe acreditar los cruces de cuenta/sync, ambas direcciones, dos procesos y conexiones reales, replay y lectura fresca; no basta con capturar `OperationalError` y devolver409.

## Privacidad, acceso y persistencia

Las operaciones conservan las guardas comerciales de Goal/Plan/RM/Training/IA. El perfil personal gratuito no concede escritura de planificación. Historial y exportación propios siguen legibles al expirar acceso. Formularios de origen/versiones y sustitución solo aceptan registros propios; CSRF sigue habilitado.

Migración aditiva `basis_training.0002_planning_version_history`: añade metadatos, FK protegidas y unicidad plan/origen; no borra datos ni reasigna resultados, y deja motivos/autor/fecha efectiva/origen legados desconocidos. El exportador existente usa los campos reales de modelos y conserva automáticamente estos metadatos dentro de sus secciones, sin cambiar `basis-export-v1`.

## Verificación y evidencia

La fuente de resultados de esta corrección es `.cache/MAM622_REVISION_REPORT.md` y el nuevo `.cache/MAM622_CANDIDATE.json`, con sus JSON/logs enlazados. El reporte de implementación previo y el manifiesto `pre-review-836380` se conservan como historia del candidato bloqueado. Cada ejecución nueva registra el binding SHA256 de fuentes runtime y su conservación antes/después. No reutilizar cifras históricas de620 ni del candidato bloqueado como pruebas de la corrección.

Cobertura requerida: dominio puro; creación y consulta completa; motivos y snapshots; estados; restauración con resultados/partial; privacidad/pago/CSRF; upgrade real desde las 28 migraciones anteriores; carreras PostgreSQL con conexiones distintas y espera real de bloqueo; fallback SQLite; Chromium a 390/1440; backup/restore con filas que usan las nuevas relaciones. Proveedores externos, dispositivos físicos y SMTP LIVE no forman parte de esta ejecución local.

En esa captura, esta documentación no marcaba622 Done ni acreditaba integración; requería revisión, release/CI y readback autorizado, incluida la dependencia620. Se conservan ese contexto y los fallos anteriores.

## Readback de integracion y cierre 2026-10-21

**MAM-622 Done**, `completedAt=2026-10-21T15:27:40.765Z`, ya existente y conservado por Luna; dependencias620/618/621 Done. [PR #8](https://github.com/Mamut1195/django_basis_trainning_app/pull/8), merge `cccc448c4aeaffef8d7a9e60bbab0b174e24ce42`; [CI postmerge 39624647162](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39624647162) SUCCESS:390PG/179puras, mypy115/350 y ocho contratos. Esta es evidencia de código integrado en ese SHA, no una repetición local ni evidencia reasignada a un commit documental posterior.

El contrato canónico anterior sigue vigente: IDs/origin/supersedes/source protegidos, intención y resultados separados, None distinto de0 y locks hasta COMMIT exterior.623 lo preservó al integrarse después en PR #9 y también está Done. Los pendientes623 mencionados en el registro de revisión eran futuros en esa captura, no el estado actual. [Cierre de cadena y límites](DEVELOPMENT_2026-10-21.md#cierre-de-la-cadena-mam-810--620--622--623); no se amplía el alcance a UX humana, dispositivos o LIVE.
