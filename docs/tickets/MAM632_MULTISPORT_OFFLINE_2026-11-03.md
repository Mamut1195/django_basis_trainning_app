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
