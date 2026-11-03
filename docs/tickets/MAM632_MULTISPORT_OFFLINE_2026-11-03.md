# MAM-632 — recuperación multisport offline, 2026-11-03

## Alcance y resultado

Implementación de prueba `903b2b0` sobre `a8657241e7a55940fc5c55f3f29466d01ae5360e`; no se modificó producción. **VERIFIED acotado:** una sesión sintética completada con seis bloques, descargada por su propietaria, editada sin red, recargada y reabierta offline, sincronizada y reabierta offline con controles bloqueados. La prueba compara el documento completo de sesión en los stores `sessions`/`outbox` con el POST real y la proyección del servicio/ORM, con equivalencia numérica decimal y revisión incrementada exactamente una vez. Valida cuenta en ambos stores, recibo del dueño, replay del mismo `mutation_id` (HTTP 200 y un recibo), y 404 al abrir la sesión desde otra cuenta. No sustituye aceptación integral ni cierra MAM-632.

| Deporte / estructura | Datos editados y comprobados |
| --- | --- |
| Fuerza | Dos series con objetivos 10 × 20 conservados; reps reales 8/7, kg reales 0/22.5, RIR real 0 en primera y ausencia en segunda. El wire completo conserva también los demás valores existentes. Adaptaciones opcionales y demás valores de serie no fueron editados en este ensayo. |
| Cardio | Todos los campos de bloque declarados por el esquema y sus campos numéricos de intervalo; RPE y descanso real de intervalo 0. |
| Running | Todos los campos de bloque del esquema, incluida cadencia; campos numéricos de intervalo. |
| Ciclismo | Todos los campos de bloque del esquema, potencia 0 y entorno indoor; campos numéricos de intervalo. |
| Natación | Todos los campos de bloque del esquema, brazadas 0; campos numéricos de intervalo. |
| Hiking / etapa trekking | Todos los campos de bloque del esquema, altitudes y desniveles coherentes, mochila 6.25, texto y dificultad; campos numéricos de intervalo. La etapa autorizada conserva su vínculo y nota de recuperación; su editor propio no es campo del wire offline y no se editó offline. |
| Sesión y prescripción | Duración 1800 y RPE 0, estado completado; se comparan todas las claves, bloques, series, intervalos y objetivos del payload con la proyección persistida. Los valores vacíos y cero se distinguen. |

Los intervalos offline no exponen campos de texto o selección; no se afirma su edición. La fixture usa un intervalo por bloque no fuerza, y dos series en un bloque de fuerza. El test no acredita todas las combinaciones de adaptación ni múltiples sesiones independientes por deporte. No se observó defecto de producción en los campos ejecutados.

## Entorno y ejecución

Windows, Python 3.13.7, Django 5.2.18, Playwright 1.64.0, Chromium headless 153.0.8010.12, viewport 390 × 844; PostgreSQL 18.4 en 127.0.0.1:55482. Se creó exclusivamente `basis_wave4_632_payload`; `test_basis_wave4_632_payload` no existía antes de la ejecución final, Django la creó y destruyó. El runner final rechaza explícitamente una base de pruebas preexistente. Utiliza `config.test_settings`, secreto sintético, IA desactivada, HTTPX real denegado, sockets solo loopback, guard de bases y Chromium con proxy cerrado y resolución restringida. Son controles de prueba, no auditoría de red.

```powershell
$py = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
& $py -u .cache/mam632-payload/run.py test tests.regression.test_mam632_multisport_browser --noinput -v 2
& $py -m mypy --config-file mypy-django.ini --follow-imports=silent tests/regression/test_mam632_multisport_browser.py
& $py -m ruff check tests/regression/test_mam632_multisport_browser.py
& $py -m ruff format --check tests/regression/test_mam632_multisport_browser.py
git diff --check
```

Focal final: **1 OK, cero omisiones, 10.631 s**; tipos focales, Ruff, formato y diff check **VERIFIED**. El 404 pertenece a la segunda cuenta y se observó un `Broken pipe` en la ejecución exitosa. No se ejecutaron suite global, tipos globales, djLint ni build: cambios exclusivamente de pruebas/documentación.

Primera ejecución: fallo de comparación textual `0`/`0.0` en reapertura sincronizada; se conservó la verificación y se compararon valores numéricos como `Decimal`. Un segundo intento arrancó antes de que terminase la destrucción de la base de pruebas anterior y falló por colisión durante creación/destrucción; no se atribuye como PASS. Se esperó el fin de ambos procesos, se comprobó ausencia y se repitió; después se añadió el guard preventivo de base existente. MyPy detectó un acceso sobre `object`, corregido con anotación `cast` sin cambiar la ejecución. No hubo correcciones de producción.

## Evidencia local

Archivos ignorados por Git en `.cache/mam632-payload/`, conservar junto al worktree; contienen únicamente fixtures sintéticas. `multisport-wire.json` incluye descarga, cola, POST, persistencia y replay. La captura muestra la reapertura Chromium y no representa dispositivo físico.

| Archivo | SHA-256 |
| --- | --- |
| `run.py` | `1a4b1d92ce775022253cf938daf376a465ffbe6f41d78497766332e258326bdb` |
| `owner-final.log` | `dee32e2198b954d550e9bffc246bfe2a44099f5556fb7d15dbb9db9fc5a93b39` |
| `pwa/multisport-wire.json` | `1bee60a0ee052ec97bd76b21b4bd42a8411f0a96e27d3733091911afb1d8d14d` |
| `pwa/multisport-completed.png` | `fc66a28e99366f3a911143d0153aae2e734063b2518bfa4106f47eab9a27310f` |

Registros `first.log`, `second.log`, `third.log`, `fourth.log`, `final.log` y `guarded-final.log` preservados. `run.py` se copió y adaptó de la referencia de coordinación, sin ejecutar su base. **NOT RUN:** instalación real, teléfono, lector de pantalla, cuota/evicción, otros navegadores, CI/Actions, integración en main, publicación y producción. No se hizo push, PR ni mutación de Linear. La candidata congelada 633/634 no se tocó.

## Revisión e integración de coordinación

Se revisaron los tres commits propios `a128319`, `903b2b0` y `372a162`; se incorporaron en orden como `c77555a`, `cc4b159` y `b1d17d8`. Solo pruebas y documentación. Coordinación comprobó los hashes del runner, log final y JSON del ejecutor; coinciden con la tabla anterior.

Primera repetición en coordinación, todavía sin ampliación propia: **VERIFIED**, una prueba, cero omisiones, 6.512 s, salida0. Ruff/formato y mypy Django focal sin silenciamiento de imports satisfactorios. Fuente funcional `b1d17d8`; no se repitió la suite global por cambios exclusivamente de pruebas.

### Complemento ejecutado: todos los campos editables de serie

Coordinación amplió la misma prueba a los 14 campos reales de la primera serie: reps, kg, RPE, RIR, descanso, isometría; ejercicio realizado, tipo de carga, tipo de serie, lado, tempo, rango, grupo y motivo de adaptación. Se abre el panel opcional mediante su control UI antes de rellenarlo. La segunda serie mantiene ausencia de RIR para distinguirla de cero. El caso compara el payload completo y verifica adicionalmente que objetivos y campos de prescripción de todos los bloques/series permanezcan iguales, aunque cambie el ejercicio realizado.

**VERIFIED:** una prueba Chromium/PostgreSQL, cero omisiones, 15.035 s, salida0; Ruff check/format y mypy Django focal satisfactorios. Este resultado amplía la fila de fuerza anterior, que solo describía la entrega original. Sigue siendo una sesión sintética de seis deportes y una configuración por campo, no todas las combinaciones posibles ni un dispositivo físico. El editor propio de etapas trekking sigue fuera del wire offline y no se presenta como editado aquí. No se modificó producción.

**FAILED de fixture, corregido:** el primer intento ampliado trató de enumerar paneles antes de terminar la apertura asíncrona del editor; el campo opcional permaneció oculto y Playwright agotó su espera. Se añadió una espera explícita a la primera cabecera de adaptación y luego se abrieron los paneles por UI. Mypy detectó además reutilización de un nombre `str` como `object` en la comparación de prescripción; se renombró la variable. Ambas correcciones son exclusivas de pruebas; se conservan los logs previos.

Comando desde coordinación: `.venv-win/Scripts/python.exe -u .cache/wave4-632-payload-integration/run.py test tests.regression.test_mam632_multisport_browser --noinput -v 2`. Runner adaptado exclusivamente a `basis_wave3_integration`/`test_basis_wave3_integration`; guard de base temporal preexistente, HTTPX externo denegado y loopback local permitido. Ninguna conexión a la base del ejecutor ni parada de PostgreSQL. Django destruyó la base temporal en cada ejecución terminada.

| Artefacto local de coordinación | SHA256 |
| --- | --- |
| `run.py` | `E383C1C9997E7BDB409CD597FB6CA1D9DFEB37F192C85FE9AF6883D4FCDB6A32` |
| `verified.log` (repetición inicial) | `69389C248DA4899F01563C4352B053975CCFF8FB7F684EB448AA2B61E816E7D7` |
| `strength-complete.log` (fallido) | `4B90FAE0A1DF39848350FD04D1D1342BBDB93196F2A7F288313917D328D3E4CB` |
| `strength-verified.log` (final) | `0EBC8AFD2C27E3E1089421BA7BDE42439C8CD229A4FA174656882CC3C47ABD5A` |
| `strength-final/multisport-wire.json` | `DCF6F7EFB0B456531C3C38D86B12A4A09B9C7884287511B9C707819B2DFB537C` |
| `strength-final/multisport-completed.png` | `9A13400E6C6D65DF2CE5348A9BFD35CC5A17E5B3B4F050BDF529CB2EFFE99E10` |

Todos están bajo `.cache/wave4-632-payload-integration/`, ignorados por Git. El test reutilizó inicialmente su directorio `pwa/`, por lo que su JSON/captura corresponden al intento ampliado más reciente; se copiaron a `strength-final/` para conservarlos. Los logs de ambas variantes permanecen separados y los artefactos originales del ejecutor siguen intactos en su worktree. No se afirma conservar un JSON independiente de la primera repetición de coordinación.

MAM-632 sigue abierto por las aceptaciones externas indicadas; main, CI remoto y la rama congelada633/634 no cambian. La mayor cobertura automatizada no equivale a instalación real ni aceptación humana.
