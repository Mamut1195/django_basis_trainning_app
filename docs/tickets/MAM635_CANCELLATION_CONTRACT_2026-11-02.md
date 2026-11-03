# Cancelación de consultas IA pendientes: contrato de implementación

Estado: **PLAN / NOT RUN**. Este documento no acredita código, pruebas o aceptación de MAM-635. Depende de integrar y revisar la corrección de intentos tardíos818. La candidata633/634 permanece congelada por separado en f42b861.

## 1. Goal

Permitir que la cuenta propietaria cancele una consulta pendiente antes de que un worker la reclame. Recuperar su reserva y su acción de cuota no utilizada exactamente una vez. El mismo job y su request_key se conservan como historial durable.

Una consulta que ya comenzó a procesarse no se puede cancelar desde esta operación. La interfaz debe indicarlo y conservar su estado y reserva; el timeout y la conciliación se rigen por818. No se promete detener una solicitud HTTP enviada.

## 2. Required skills

task-planning, safe-git-workflow, verify-before-complete; systematic-debugging para cualquier fallo inesperado. Leer arquitectura y contratos818 integrados antes de editar.

## 3. Likely affected areas

- basis/modules/coach/application/jobs.py: operación tipada cancel(owner, job_id), con el mismo orden de locks que settlement y reconciliación.
- basis/modules/coach/adapters/actions.py: fachada Django que traduce identificadores y errores.
- basis/modules/coach/adapters/web/views.py y urls.py: POST autenticado, CSRF y propiedad comprobada.
- basis/modules/coach/adapters/templates/coach/jobs/_result.html: acción solo para pending, estado cancelado legible y sin polling.
- Pruebas propias nuevas de cancelación puras/PostgreSQL/HTTP y recibo MAM635. Integración de templates serializada después del commit UI635.

El estado cancelled cabe en el campo status existente; no crear una tabla o un campo solo para representarlo. Si la corrección818 introduce un estado del intento, consultarlo también para probar que no hubo despacho.

## 4. Constraints

La operación no requiere una nueva llamada al proveedor ni acceso comercial activo: permite retirar trabajo propio no enviado aun después de vencer la suscripción. Mantener autenticación y aislamiento por cuenta. No usar la autorización de escritura deportiva como requisito comercial de esta operación.

Orden transaccional: fondo original cuando existe → cuenta propietaria → job → período original. Comprobar propietario antes de alterar datos; una cuenta ajena recibe404, sin revelar costo o estado. Releer el estado bajo lock. El claim de un worker y la cancelación deben decidirse atómicamente sobre la misma fila.

Para pending sin evidencia de despacho: validar saldos y contador antes de restar; liberar exactamente la reserva del período y del fondo originales, decrementar solo el contador de su tipo, guardar cost=0, status=cancelled y completed_at. No cambiar spent ni otros contadores. Si los invariantes no permiten la liberación, rechazar sin ajustes parciales ni valores negativos.

Un replay de cancelled devuelve el resultado existente y no vuelve a descontar. Reutilizar request_key conserva el job cancelado mediante la idempotencia existente; iniciar otra consulta requiere una petición nueva. No reenviar automáticamente por cancelación o reconexión.

Para running, uncertain y demás estados terminales: no modificar estado, saldos, contadores, evidencia o propuestas; devolver conflicto controlado. No aceptar una confirmación del navegador como prueba de que un intento HTTP terminó.

## 5. Do not change

No editar contexto/codec/prompts633, fuente/guard/revisión de propuestas634, tarifas o whitelist818, políticas comerciales, entrenamiento manual, programas deportivos, modelos históricos o workflows/lockfiles. No activar IA LIVE, pagos, producción, CI remoto o endpoints públicos. No escribir Linear ni cerrar tickets. Preservar documentos ajenos y commits existentes.

## 6. Implementation steps

1. Incorporar únicamente commits818 revisados y estables; leer su representación durable del intento y su orden de locks.
2. Añadir el caso de uso y regresiones de estado, propiedad, saldos y replay. Reproducir la carrera claim/cancel en ambos órdenes con transacciones y conexiones PostgreSQL distintas.
3. Exponer el POST y el botón pendiente; GET no modifica datos. Mantener CSRF y enlaces de regreso al resultado. Un conflicto por claim concurrente vuelve a mostrar el estado real.
4. Mostrar Cancelada y detener polling. No ofrecer el botón para un trabajo ya enviado; explicar que su resultado sigue pendiente cuando corresponda.
5. Probar web y navegador móvil/escritorio con proveedor simulado, incluyendo regreso y recarga. Registrar SHA, comandos, resultados y límites antes de entregar commit propio.

## 7. Acceptance criteria

- Pending paid/trial: reserva original liberada una vez, acción correspondiente recuperada una vez, fondo trial correcto y costo cero; no HTTP ni propuesta.
- Doble cancelación y POST repetido: mismo resultado, sin segundo ajuste; request_key no crea otro job.
- Cancelación primero: el worker no puede reclamar ni enviar ese job. Claim primero: cancelación devuelve conflicto y no libera nada.
- PostgreSQL: demostrar bloqueo real y terminación sin ciclo en ambos órdenes; verificar saldos y número de llamadas tras commit. Añadir cancelación frente a enqueue concurrente del mismo propietario.
- Otra cuenta, anónimo, GET y CSRF inválido no pueden cancelar; la operación propia no queda bloqueada solo por acceso comercial vencido.
- Running/uncertain/succeeded/failed no se convierten silenciosamente en cancelled. Los fallos de integridad conservan todos los saldos.
- La pantalla reabierta muestra Cancelada sin polling ni nuevo POST. El registro manual y el plan vigente permanecen disponibles.

## 8. Validation

Estos son checks requeridos, todavía **NOT RUN** para este contrato: pruebas nuevas puras y PostgreSQL; jobs/edges/ledger/reconciliación; aceptación635 integrada; mypy core y Django; checker de arquitectura, Import Linter, Ruff check/format, djLint, Django check y makemigrations --check --dry-run. Suite equivalente a checks.yml cuando el conjunto esté estable.

Usar Python root .venv-win, config.test_settings, PostgreSQL18.4 en loopback y una base exclusiva autorizada, AI_ENABLED=0 fuera del fixture y credenciales sintéticas. HTTP real bloqueado; MockTransport para el worker. No atribuir la prueba de cliente Django a navegador, ni una emulación a dispositivo físico. Conservar logs y no parar PostgreSQL compartido.
