# MAM-635 / BASIS-021 — aceptación local parcial

Fecha del propietario: 2026-11-02. Base `5cb9498294655b769b948a4639909a4b7d843dd0`; ticket vivo leído con relaciones y comentarios: In Progress, bloqueado entre otros por MAM-818. No se modifica Linear ni se propone cerrar el ticket. MAM-818 no está integrado en esta base: los resultados no acreditan tarifas, cuotas finales ni conciliación.

## Plan y alcance

Objetivo: contrastar la interfaz HTTP con composición, persistencia y worker reales mediante un transporte sintético. Arquitectura: monolito Django, módulos hexagonales, templates/Cotton/HTMX; la lógica de propuestas permanece en MAM-634. Restricciones: solo prueba y recibo propios; sin proveedores LIVE, modificación de contabilidad o cambios compartidos. Validación: PostgreSQL exclusivo, mypy y Ruff focales. Riesgos pendientes: cancelación, observabilidad, reconexión y aceptación móvil.

## Matriz de evidencia

| Criterio | Resultado y límites |
| --- | --- |
| Consultar, revisar, aceptar o descartar | **VERIFIED LOCAL_SIMULATED**: dos respuestas de plan sintéticas atraviesan POST, worker, revisión y decisión; aceptar crea un plan y descartar no lo crea. Son planes nuevos; adaptación de un plan existente por esta cadena completa queda **NOT RUN**. Reglas exhaustivas corresponden a MAM-634. |
| Reabrir sin encolar | **VERIFIED LOCAL_SIMULATED**: GET repetidos y parcial HTMX para pending no crean otro job ni llaman al proveedor; después del worker se muestra respuesta y cesa polling. Otra cuenta recibe 404. No es prueba real de reconexión del navegador. |
| Caída y entrenamiento | **VERIFIED LOCAL_SIMULATED**: 500 simulado produce uncertain, retiene reserva y no se reenvía; POST crea una sesión manual y los campos del plan base permanecen iguales. No prueba todas las variantes de caída ni operación offline. |
| Consumo y errores privados | **PARCIAL**: respuesta válida guarda modelo y tokens; detalle muestra error controlado y no muestra el cuerpo privado de 500 ni la credencial sintética. `_result.html` no muestra tokens, costo ni saldo; no se ha auditado el conjunto de logs. Observabilidad de consumo y privacidad global pendientes. |
| Tarea larga | **PARCIAL**: el comando real pone en cuarentena un running de más de diez minutos, conserva reserva y no llama HTTP. No simula un worker realmente bloqueado ni una carrera de cancelación. |
| Límites | **PARCIAL**: contador existente fijado a 200 impide nueva consulta y muestra mensaje; no demuestra concurrencia, todas las cuotas ni precios de MAM-818. |
| Propuesta inválida | **VERIFIED LOCAL_SIMULATED**: respuesta incompleta termina failed sin propuesta ni plan. |
| Cancelación | **GAP**: `coach/adapters/web/urls.py` solo expone consulta, detalle y revisión; `application/jobs.py` no ofrece caso de uso de cancelación de AIJob. Cancelar una sesión deportiva no cancela un job IA. Interfaz mínima a coordinar: comando autenticado y dueño-scoped `cancel(job_id)` con resultado/estado explícito, transición atómica de pending bajo locks y política de reserva; definir por separado running/llamada ya enviada como ambigua y no reenviable, y carreras con claim/settle. Requiere diseño y pruebas del dueño de jobs/ledger antes de ofrecer botón. |
| Reconexión y móvil | **NOT RUN**: sin navegador, viewport, teclado o emulación; GET/HTMX del cliente Django no demuestra comportamiento offline, reconexión visual, accesibilidad ni dispositivo físico. `app.js` escucha online/offline, pero su presencia estática no prueba el recorrido. |

## Ejecución

Intérprete `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe`, `config.test_settings`, secreto sintético, `AI_ENABLED=0` fuera del override exclusivo de la clase, modelo/credencial sintéticos. `httpx.HTTPTransport.handle_request` bloqueado en el runner; el único transporte del proveedor es `httpx.MockTransport`. PostgreSQL `basis_wave3_635` en `127.0.0.1:55482`; Django creó y destruyó `test_basis_wave3_635`. Las fechas del fixture siguen `timezone.localdate()` del mismo reloj usado por la aplicación. No se detuvo la instancia.

**VERIFIED**: 7 pruebas, cero omisiones, 1.747 s; Django system check sin incidencias. Aviso: directorio `staticfiles` ausente; el cliente de pruebas no comprueba activos visuales. Mypy Django focal: un archivo sin errores; Ruff check y format focales pasan. Dos ejecuciones intermedias fallaron por el fixture de tipo corto y por una edición con codificación incorrecta; se corrigieron y la ejecución final pasó.

```powershell
$env:DJANGO_SETTINGS_MODULE='config.test_settings'
$env:DJANGO_SECRET_KEY='synthetic-test-only'
$env:AI_ENABLED='0'
$env:DATABASE_URL='postgresql://basis_wave0@127.0.0.1:55482/basis_wave3_635'
$taskPython='C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
& $taskPython -c "import httpx,runpy,sys; httpx.HTTPTransport.handle_request=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('External HTTP blocked')); sys.argv=['manage.py','test','basis.bootstrap.tests.test_mam635_acceptance','--noinput','-v','1']; runpy.run_path('manage.py',run_name='__main__')"
& $taskPython -m mypy --config-file mypy-django.ini basis/bootstrap/tests/test_mam635_acceptance.py
& $taskPython -m ruff check basis/bootstrap/tests/test_mam635_acceptance.py
& $taskPython -m ruff format --check basis/bootstrap/tests/test_mam635_acceptance.py
```

**NOT RUN**: suite completa, CI, navegador y dispositivos, HTTP o IA LIVE, calidad deportiva, pagos, y validación posterior a la integración de MAM-818. El bloqueo indicado cubre el transporte HTTPX estándar de estas pruebas; no constituye un cortafuegos general del sistema. Sin commit, push ni PR.
