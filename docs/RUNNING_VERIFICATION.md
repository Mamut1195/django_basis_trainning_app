# MAM-812 — verificación de running manual

Fecha: 2026-10-23. Ejecución: `MAM812-20261023-running-v1`.
Snapshot congelado v4: `b31e697ee2c363c25c0d8ee9c4cac05d1343a1fa82992fe926de1fd795cf2fd7`.
Base: `de24ce7ef686c0b990342537d7a47a6fec5274a6`; rama: `ticket/MAM-812-running`.

## Alcance auditado y reutilización

Se conserva el trabajo existente de MAM-811: diccionario deportivo, formularios
`MetricsForm`, validación tipada, codec/sync, exportación privada, copia de
prescripciones y referencias históricas de umbral. Es evidencia heredada de diseño,
no un PASS nuevo por herencia. La batería endurance se vuelve a ejecutar localmente;
solo cambia su conteo exacto de variables de 55 a 56.

El cambio de producto añade `pause_seconds` a running reutilizando la misma
especificación `OUTDOOR` y la validación cruzada existente. Presenta métricas legibles
y ritmo derivado transcurrido, con unidades y encabezados separados de objetivo /
prescripción y resultado real / registro manual, para bloques e intervalos. No hay
fallback del objetivo al resultado ni presentación de intervalos como JSON crudo.
Se conservan duración, distancia, superficie, tipo, ascenso/descenso y FC/cadencia
medidas opcionales. Una ausencia es desconocida; un cero observado sigue siendo cero.
No se añaden entidades de catálogo, registros de métodos duplicados ni migraciones.

La continuación previa completó pruebas, comprobaciones LF y documentación:
- Sync ajeno exige exactamente 400 y detalle de sesión no disponible; una cuenta de
  cola distinta exige 403. Se comparan todas las filas de sesiones, bloques,
  intervalos y recibos antes/después, además de excluir recibos de cada mutación
  rechazada. Lecturas/escrituras web ajenas devuelven 404 y export no filtra datos.
- Paridad dominio / `pace_seconds_legacy` / filas de bloque e intervalo, contra
  literales analíticos independientes, no solo comparación entre producción.
- `Session.objects.prefetch_related('blocks__intervals')` permite evaluar métricas
  y renderizar tres intervalos sin consultas adicionales; no hace falta modificar
  vistas ni añadir `select_related`.
- Prueba de bytes LF y salto final para las nueve superficies de texto autorizadas.

Esta continuación mecánica v4 solo conserva el UUID rechazado en la variable local
`rejected_mutation`, de tipo inferido `str`, y la reutiliza en el cuerpo y la consulta
de recibos. No cambia aserciones, semántica ni conteos de pruebas. No toca producto
ni el commit del coordinador `8a9c55d` (diccionario y conteo endurance).

## Fuente, hipótesis y evidencia matemática propia

Autoridad: contrato local congelado `docs/TRAINING_VARIABLES.md`, cláusula
«Métricas», edición de la base indicada arriba; no se atribuye autoridad normativa
externa a una herramienta computacional. Propietario del método y registro:
`training/domain/sports.py`, `pace_seconds` y `VARIABLES` existentes (REUSE).
Aplicación: entradas manuales finitas no negativas admitidas por el diccionario;
distancia positiva en metros y duración transcurrida conocida en segundos.

`ritmo [s/km] = duración [s] / distancia [m] × 1000 [m/km]`.
Se mantiene el método de producción y su redondeo a 0,01 s/km. Ejemplos independientes:

| Duración s | Distancia m | Ritmo esperado s/km |
| --- | --- | --- |
| 1500 | 5000 | 300,00 |
| 1800 | 5000 | 360,00 |
| 60 | 400 | 150,00 |
| 1 | 3 | 333,33 |
| 0 | 5000 | 0,00 |

Las pausas de 120 s no alteran 1800 s / 5000 m = 360,00 s/km: se registran, no se
restan. Pausas mayores que la duración conocida se rechazan. Duración desconocida,
distancia ausente o cero: sin ritmo, nunca división por cero. Un `null` o cadena
vacía heredados no se convierten en cero. FC, cadencia y desnivel ausentes siguen
siendo desconocidos; cero registrado se conserva.

Las pruebas exigen igualdad Decimal exacta contra los literales redondeados y error
analítico sin redondear <= 0,005 s/km; no tolerancia relativa amplia. Se comprueba
invariancia al escalar positivamente duración y distancia por 0,1 / 1 / 7 / 100,
y las relaciones al duplicar solo distancia o duración. Objetivo y resultado usan
únicamente sus propias fuentes. No hay GPS, inferencia de velocidad ni afirmación
fisiológica, sensor, dispositivo o LIVE.

## Ejecución local propia y comandos

Runtime aprobado: Python 3.13.7 Windows, `.venv-win/Scripts/python.exe`, Django /
unittest nativos (el proyecto no usa pytest). SQLite de prueba aislado y desechable,
`DJANGO_SETTINGS_MODULE=config.test_settings`; sin credenciales reales. El driver
congelado `.cache/mam812_gate_driver.py` fija comandos y entorno. Se leen los espejos
completos `.cache/mam812-diagnostics/<gate>.txt`, no se deduce PASS de salidas truncadas.
Cada gate genera su registro firmado para el candidato exacto; guardar esta
bitácora cambia el candidato y exige sellos finales posteriores.

Resultados del coordinador sobre el candidato anterior que ya incluía documentación,
según el encargo congelado v4 (evidencia observada previa, no sellos del candidato final):

| Gate / comando lanzador ejecutado | Estado observado por el coordinador |
| --- | --- |
| `python -B .cache/mam812_gate_driver.py running` | VERIFIED: 20 tests, 0 skips, EXIT 0 |
| `python -B .cache/mam812_gate_driver.py browser {OUTPUT}` | VERIFIED: 1 test Chromium, 0 skips, EXIT 0 |
| `python -B .cache/mam812_gate_driver.py quality` | VERIFIED: PASS |
| `python -B .cache/mam812_gate_driver.py contracts` | FAILED provisional: solo mypy-django por `mutation_id` inferido `object`; 195 pruebas puras, core 120 archivos, arquitectura y 8 contratos de imports PASS |
| `python -B .cache/mam812_gate_driver.py regression` | VERIFIED: 467 tests, OK, skipped 63 |

Comprobación propia tras corregir el tipo: `systems_gate contracts` ejecutó
`python -B .cache/mam812_gate_driver.py contracts`: VERIFIED, todos los comandos EXIT 0.
El diagnóstico completo `.cache/mam812-diagnostics/contracts.txt` registra 195 tests
OK, mypy-core sin incidencias en 120 archivos, mypy-django sin incidencias en 368
archivos, arquitectura VERIFIED y 8 contratos de imports conservados, 0 rotos.
Este resultado corrige el fallo provisional de tipado, sin omitir ni debilitar checks.
Tras guardar esta bitácora se ejecutan de nuevo `contracts` y `quality`; sus estados
finales y el identificador exacto del candidato quedan en los registros firmados y
`systems_result`, sin editar después el candidato para transcribirlos. Los otros
tres gates finales (`running`, `browser`, `regression`) quedan para el coordinador:
NOT RUN sobre estos bytes finales en esta continuación.

Los comandos internos exactos aprobados son:

```text
python -B manage.py test tests.regression.test_running tests.regression.test_endurance --noinput --verbosity 2
python -B manage.py test tests.regression.test_running_browser --noinput --verbosity 2
python -B -m ruff check .
python -B -m ruff format --check basis config tests tests_architecture
python -B -m djlint basis --check
python -B manage.py check
python -B manage.py makemigrations --check --dry-run
git diff --check
python -B -m unittest discover -s tests_architecture
python -B -m mypy --config-file mypy-core.ini --cache-dir .cache/mypy-core
python -B -m mypy --config-file mypy-django.ini --cache-dir .cache/mypy-django
python -B scripts/architecture_check.py
.venv-win/Scripts/lint-imports.exe --no-cache
python -B manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput
```

El gate browser activa `BASIS_RUNNING_BROWSER=1`, establece su directorio de salida
y comprueba el hash del Chromium compartido revision 1243, propiedad del usuario.
El recorrido HTTP usa una cuenta ficticia: login, creación de sesión, edición de
métricas, alta/edición de intervalo, objetivo distinto de real, ausencia de FC,
ceros de cadencia/desnivel/pausas, ritmo sin descontar pausas, y viewport 390/1440 px
sin overflow horizontal. Genera `running-390.png`, `running-1440.png` y
`browser-report.json` fuera del worktree, ligados al registro del gate. Las peticiones
no locales se abortan. Capturas/DOM no equivalen a aceptación de accesibilidad.

## Fallos provisionales y límites

La continuación conserva el selector estable `details > summary` que corrigió la
renumeración dinámica de locators en un intento anterior. Conserva también la
corrección del conteo de ausencia en la página (solo queda desconocido el objetivo
no prescrito del bloque). La expectativa provisional 403/404 para sync ajeno era
incorrecta: el adaptador convierte `Unavailable` a ValidationError HTTP 400;
se prueba ese contrato exacto y separadamente el 403 por cuenta de cola incorrecta,
sin modificar producto ni debilitar aislamiento. Los dos ajustes locales de formato
solicitados por Ruff quedaron corregidos: el coordinador observó quality PASS.
El único fallo posterior fue mypy-django en la consulta de recibos (antes línea 325):
`body["mutation_id"]` se infería `object`. La variable local `str` elimina ese error;
la comprobación propia posterior de contracts descrita arriba pasó íntegramente.

`makemigrations --check --dry-run` observó «No changes detected». Django advierte que
no existe el directorio de salida `staticfiles/`; no impide el live server de prueba.
Git advierte de posible conversión futura LF -> CRLF por configuración heredada;
no se cambia configuración ni `.gitattributes`. La prueba binaria verifica los
bytes reales del candidato, no una suposición basada en esa advertencia.

- PostgreSQL local y su comportamiento concurrente específico: NOT RUN; la regresión
  SQLite del coordinador registró 63 skips, sin atribuirles cobertura PostgreSQL.
- Dispositivos físicos, sensores, GPS, wearables, LIVE: NOT RUN / fuera de alcance.
- Screenreader y aceptación integral de accesibilidad: NOT RUN.
- Browser offline/service worker: NOT RUN; el contexto bloquea service workers.
- Revisión fuerte independiente semántica/matemática/UI: pendiente.
- Sellos finales de running, browser y regression: pendientes del coordinador.
- Commits pequeños restantes, push, DRAFT PR y CI remota: pendientes, solo coordinador.

No se afirma aceptación, integración, publicación, cierre ni ticket Done.

## Readback del coordinador — candidato local preparado para revisión

Después de la corrección mecánica de tipado se verificaron los cinco gates sobre
los mismos bytes de implementación: `quality` EXIT 0; `contracts` EXIT 0 (195 pruebas
puras, mypy 120/368 archivos, arquitectura y ocho contratos); `running` EXIT 0
(20 pruebas, cero omisiones); `regression` EXIT 0 (467 pruebas, 63 omisiones);
`browser` EXIT 0 (una prueba real Chromium a 390/1440 px, cero omisiones).
Los 63 skips incluyen los casos exclusivos de PostgreSQL y el navegador opt-in,
que sí se ejecutó separadamente en su gate. No equivalen a 467 casos aprobados sin
omisiones ni a evidencia local PostgreSQL.

Este readback es posterior a las notas de continuación anteriores. Se conservan los
fallos provisionales como historia, no como fallos pendientes del producto. Tras
esta adición documental se vuelven a sellar los cinco gates para el árbol final;
el resultado autoritativo es `collect` del run externo y se comunica en el PR.
No se reutiliza una aprobación sobre un cambio semántico.

BT2: la paridad de ritmo usa literales independientes y compara dominio, adaptador
y presentación; tres intervalos prefetched se presentan sin consultas adicionales.
La comprobación binaria de finales LF pasó en las nueve superficies cambiadas.
El coordinador observó las capturas: objetivo/real, unidades y ausencia/cero se
mantienen legibles en ambos anchos. El aviso offline es esperado por el bloqueo de
service workers del contexto de prueba; no demuestra aceptación offline. El texto
heredado «Pausas excluidas» no cambia la fórmula: la pantalla explicita que no se
restan del ritmo transcurrido.

Se conserva el commit de dominio `8a9c55d` y el de presentación/pruebas `7308c8e`.
La revisión fuerte y la publicación DRAFT se registran separadamente en el PR con
su estado real; esta bitácora no declara integración, merge ni ticket Done.
