# MAM-814 — Natación manual y ritmo transcurrido por 100 m

## Alcance y plan congelado

Base `00fc7185355b05f34874c4cefb4a4c8c16b05793`, rama
`ticket/MAM-814-swimming`, ejecución `MAM814-20261026-v1`, snapshot
`5009067c331655f59b5782a67f2235a4dc455c936cc820c66f50ee7359cc85fc`.
Solo presentación de ritmo en `metric_rows` y explicación española compartida
por bloques e intervalos; las validaciones, formularios, privacidad, persistencia
y agregados deportivos existentes se reutilizan, sin migraciones, sensores,
proveedores, importaciones ni registro paralelo de métodos.

Plan: (1) leer contratos y dependencias; (2) extender presentación sin cambiar
running; (3) probar con literales analíticos, límites, formularios HTTP, copia de
intención, sincronización/exportación y totales; (4) recorrido Chromium local
390/1440; (5) gates acotados y revisión independiente pendiente; evidencia ordinaria, no firmada.

## Fuente, aplicabilidad, unidades y método

Autoridad: edición local de `docs/TRAINING_VARIABLES.md` en la base `00fc718`,
cláusulas **Métricas / Ritmo** y **Los totales del bloque son autoritativos**;
`docs/TRAINING_CONTRACT.md` versión `basis-005-v1`, secciones **Variables, unidades
y procedencia**, fila swimming, y **Evaluación reproducible y límites de los
estimadores**, párrafo `pace_seconds`. No se atribuye autoridad normativa a
Wolfram, navegador ni comparación entre adaptadores.

Propietario del registro reutilizado: training, `domain/sports.py::VARIABLES` y
`pace_seconds`. Fórmula: `t[s] / d[m] × 100[m]` produce segundos por cada 100 m;
entradas manuales finitas no negativas ya validadas, distancia estrictamente
positiva, duración conocida (incluido cero). Se usa duración **transcurrida** de
la misma fuente `target` o `actual`, nunca mezcla o fallback; no se descuentan
descansos ni se multiplica el ritmo por repeticiones. Se mantiene running en
s/km con factor 1000. Redondeo Decimal a 0,01, half-even; no es min:seg.

Oráculos analíticos independientes (no generados por producción):

| t (s) | d (m) | s/100 m esperado |
|---:|---:|---:|
| 1200 | 800 | 150.00 |
| 100 | 50 | 200.00 |
| 120 | 50 | 240.00 |
| 1 | 3 | 33.33 |
| 1 | 32 | 3.12 (exacto 3.125, empate half-even) |
| 0 | 800 | 0.00 |

Ausencia/null/vacío o distancia cero: desconocido (`—`), no cero inferido.
Tolerancia: igualdad exacta con los literales cuantizados y error absoluto frente
a la razón no redondeada ≤ 0,005 s/100 m. Invariantes: escalar ambas entradas no
cambia ritmo; doble distancia divide ritmo por dos; doble tiempo lo duplica.
La paridad dominio/adaptador/presentación es adicional, no el oráculo primario.
Los valores inválidos se rechazan por dominio y fronteras existentes antes del
cálculo; `pace_seconds` no es por sí sola una API de validación de valores crudos.

Distancia del bloque autoritativa: 700 m registrados con 32 largos × 25 m siguen
siendo 700 m. No se suman además intervalos/repeticiones, aunque estén parcialmente
registrados. Solo largos/piscina y distancias de intervalos dejan el total de
bloque desconocido. Completar no obliga a rellenar todos los intervalos; una
sesión en curso no entra en totales completados. No se afirma que el subtotal
conocido certifique cobertura de todas las mediciones.

## Pruebas y evidencia

- `tests_architecture/test_swimming.py`: analítica independiente, redondeo,
  tolerancia, escala, límites de cada variable numérica, largos/brazadas enteros,
  estilo/técnica de texto libre, FC opcional/coherencia, descansos/repeticiones,
  agregado puro y ausencia de inferencia desde largos.
- `tests/regression/test_swimming.py`: paridad con constantes, null/vacío/cero,
  español y escape HTML, formulario/unidades, crear/editar HTTP, intervalo con
  descansos objetivo/real, copia prescrita e intención protegida, inmutabilidad
  completada, prefetch sin consultas adicionales, sincronización idempotente y
  atómica, rechazo ajeno sin cambios de filas/recibos, exportación privada y
  totales completados con intervalos parciales sin doble conteo.
- `tests/regression/test_swimming_browser.py`: opt-in
  `BASIS_SWIMMING_BROWSER=1`; usa `BROWSER_EXECUTABLE` y directorio de
  `BASIS_SWIMMING_OUTPUT` proporcionado/expandido por el runner (sin ruta fija).
  Login real con cuenta ficticia de factory, creación de sesión/bloque, edición
  de métricas e intervalo, reapertura persistida, FC vacía, cero explícito,
  ritmos separados 150/200/240 y descanso no descontado. Bloquea solicitudes
  fuera del origen local y service workers. Produce `swimming-390.png`,
  `swimming-1440.png`, `browser-report.json`. El informe DOM no sustituye la
  revisión visual independiente ni lector de pantalla.

### Resultados reales de continuación y cierre (2026-10-26)

Evidencia local en `C:/Users/Jonnathan/Mamut system/basis-runs/MAM-814/`.
Fuente: `continuation-c-snapshot.md`, `run-continuation-gates.py`, logs `gate-*.txt`
y `browser-c/browser-report.json`. **VERIFIED en la tabla siguiente describe la
ejecución previa MAM-814c, no una repetición en MAM-814d ni aceptación del ticket.**
No se repitieron esos gates por instrucción de `prompt-finish.md`.
Los logs son ordinarios, no evidencia runner-sealed: no se importan como sellos
válidos ni se afirma equivalencia verificable de candidato/entorno completo.
Los `gate-initial-*.txt` conservan fallos históricos; no se sobrescribieron.

| Gate previo MAM-814c | Resultado registrado | Alcance / resultado | Log |
|---|---|---|---|
| ruff-check | VERIFIED | Ruff global previo, exit 0 | `gate-ruff-check.txt` |
| ruff-format | VERIFIED | 380 archivos, exit 0 | `gate-ruff-format.txt` |
| mypy-core | VERIFIED | 123 archivos, exit 0 | `gate-mypy-core.txt` |
| mypy-django | VERIFIED | 378 archivos, exit 0 | `gate-mypy-django.txt` |
| architecture | VERIFIED | Fronteras/capas/inventario, exit 0 | `gate-architecture.txt` |
| lint-imports | VERIFIED | 8 contratos conservados, 0 rotos | `gate-lint-imports.txt` |
| djlint | VERIFIED | 42 archivos, 0 cambios requeridos | `gate-djlint.txt` |
| tests-architecture | VERIFIED | 209 pruebas, OK | `gate-tests-architecture.txt` |
| django-check | VERIFIED | 0 incidencias | `gate-django-check.txt` |
| makemigrations | VERIFIED | No changes detected; sin migraciones nuevas | `gate-makemigrations.txt` |
| swimming | VERIFIED | 35 pruebas deportivas, OK | `gate-swimming.txt` |
| sqlite | VERIFIED | 500 pruebas, OK (skipped=64) | `gate-sqlite.txt` |
| postgres | VERIFIED | 500 pruebas, OK (skipped=2) | `gate-postgres.txt` |
| browser | VERIFIED | 1 prueba, Chromium 153.0.8010.12, 390/1440 px | `gate-browser.txt` |
| prettier | FAILED | 9 archivos compartidos; exit 1 | `gate-prettier.txt` |
| git-diff | VERIFIED | git diff --check previo, exit 0 | `gate-git-diff.txt` |

**MAM-814d VERIFIED:** una invocación de `ruff check` y una de
`ruff format --check`, solo sobre los cuatro archivos Python del ticket; exit 0
ambas, cuatro archivos ya formateados, sin cambiar imports ni semántica.
Log `gate-ruff-final.txt`, con Python 3.13.7, comandos y SHA256 de entradas.
Los restantes gates: **NOT RUN en esta sesión de cierre**; resultados previos arriba.

#### Entorno y comandos exactos registrados

Desde la raíz del worktree. MAM-814c usó `DJANGO_SETTINGS_MODULE=config.test_settings`,
`DJANGO_DEBUG=1`, `DJANGO_SECRET_KEY=mam814-public-disposable-test-key`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`,
`BASIS_DATABASE_PATH=C:/Users/Jonnathan/Mamut system/basis-wt/MAM-814/.cache/mam814-gates.sqlite3`
y `DATABASE_URL=sqlite:///C:/Users/Jonnathan/Mamut system/basis-wt/MAM-814/.cache/mam814-gates.sqlite3`.
No usar `DATABASE_URL` vacío: el intento inicial falló por ENGINE ausente.
Navegador opt-in desactivado en suites generales; sus omisiones no son cobertura LIVE.

```text
# ruff-check
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m ruff check .

# ruff-format
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m ruff format --check basis config tests tests_architecture scripts/architecture_check.py scripts/browser_smoke.py scripts/acceptance_browser.py scripts/verify_environment.py

# mypy-core
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m mypy --config-file mypy-core.ini --cache-dir .cache/mam814-mypy-core

# mypy-django
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m mypy --config-file mypy-django.ini --cache-dir .cache/mam814-mypy-django

# architecture
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B scripts/architecture_check.py

# lint-imports
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\lint-imports.exe" --no-cache

# djlint
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m djlint basis --check

# tests-architecture
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m unittest discover -s tests_architecture

# django-check
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py check

# makemigrations
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py makemigrations --check --dry-run

# swimming
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py test tests.regression.test_swimming tests.regression.test_endurance tests.regression.test_running tests.regression.test_cycling --noinput --verbosity 2

# sqlite
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput

# postgres
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput

# browser
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B manage.py test tests.regression.test_swimming_browser --noinput --verbosity 2

# prettier
"C:\Program Files\nodejs\node.exe" node_modules/prettier/bin/prettier.cjs --check assets/css/**/*.css assets/js/**/*.js basis/**/static/basis/**/*.css basis/**/static/basis/**/*.js --no-error-on-unmatched-pattern

# git-diff
git diff --check
```

Únicos gates ejecutados en MAM-814d (timeout 45 s por proceso):

```text
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m ruff check basis/modules/training/adapters/templatetags/training_tags.py tests/regression/test_swimming.py tests/regression/test_swimming_browser.py tests_architecture/test_swimming.py
"C:\Users\Jonnathan\Mamut system\basis-wt\MAM-814\.venv-win\Scripts\python.exe" -B -m ruff format --check basis/modules/training/adapters/templatetags/training_tags.py tests/regression/test_swimming.py tests/regression/test_swimming_browser.py tests_architecture/test_swimming.py
```

PostgreSQL empleó la misma suite general con
`DATABASE_URL=postgresql://mam814@127.0.0.1:55814/postgres`, no el rol inexistente
`postgres` del intento inicial. Clúster desechable local `.cache/mam814-pg`,
inicio acotado y parada registrados; `gate-postgres-stop.txt` confirma parada exit 0.

```text
C:/Users/Jonnathan/scoop/apps/postgresql/current/bin/pg_ctl.exe -D .cache/mam814-pg status
C:/Users/Jonnathan/scoop/apps/postgresql/current/bin/pg_ctl.exe -D .cache/mam814-pg -l .cache/mam814-pg.log -o "-p 55814" -w -t 60 start
C:/Users/Jonnathan/scoop/apps/postgresql/current/bin/pg_ctl.exe -D .cache/mam814-pg stop -m fast -w -t 30
```

El navegador anterior usó `BASIS_SWIMMING_BROWSER=1`,
`BROWSER_EXECUTABLE=C:/Users/Jonnathan/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe`
y `BASIS_SWIMMING_OUTPUT=C:/Users/Jonnathan/Mamut system/basis-runs/MAM-814/browser-c`.
El script comprobó Chromium SHA256
`9b07943f834485b43c9d54caea2951c78715f9f07070a80ab6658465ebd3e711`.
Informe: ocho comprobaciones, sin errores JavaScript ni solicitudes externas
entregadas; intentos externos bloqueados. Capturas `swimming-390.png` y
`swimming-1440.png`; esto no sustituye revisión visual independiente.

### Prettier FAILED — no ocultar ni ampliar alcance

El gate configurado terminó en exit 1 sobre estos nueve archivos compartidos,
que MAM-814 **no modifica**:

- `basis/adapters/web/static/basis/css/app.css`
- `basis/adapters/web/static/basis/css/tokens.css`
- `basis/adapters/web/static/basis/js/app.js`
- `basis/adapters/web/static/basis/js/forms.js`
- `basis/adapters/web/static/basis/js/offline.js`
- `basis/adapters/web/static/basis/js/service-worker.js`
- `basis/adapters/web/static/basis/js/theme.js`
- `basis/adapters/web/static/basis/js/timer.js`
- `basis/adapters/web/static/basis/js/updates.js`

`git ls-files --eol` confirmó en MAM-814d `i/lf w/crlf` en los nueve: CRLF del
checkout frente a configuración LF. El diagnóstico previo con `--end-of-line auto`
pasa según el brief de cierre, pero **no reemplaza el gate configurado** y no se
repitió ni se presenta como PASS del gate. No se normalizaron archivos compartidos,
no se cambió configuración ni `core.autocrlf` y no se ejecutó Prettier con escritura.

## Límites, revisión y entrega draft

Ruta Systems instalada incompatible con las reservas vigentes: el runner previo
escribe fuera de la carpeta de evidencia permitida y exige el revisor fuerte
prohibido por el brief. Se conserva la continuación directa segura sin modificar
políticas ni fabricar sellos. Contadores heredados: implementación 1, fix 0,
review 0. LEVEL 2, MATH_VERIFY ON, METHOD_REGISTRY REUSE training; no rediseño.

- Revisión independiente: **BT2**, NOT RUN; revisión matemática/UI y aceptación
  independiente BT2/BT3: NOT RUN. `UI_REVIEW_REQUIRED=YES`, pendiente.
- Revisor externo/no autorizado: NOT RUN; no se lanzaron subagentes.
- Lector de pantalla, dispositivos reales, GPS/wearables, LIVE/Polar y evaluación
  clínica/deportiva: NOT RUN; fuera de la autorización de esta entrega manual.
- CI del PR: NOT RUN al preparar este documento; se consulta por SHA en GitHub.
- Aceptación local, integración/merge, publicación de release, sincronización de
  tracker y cierre Done: NOT RUN. Un push/PR draft no significa aceptación.

Se autorizaron commits convencionales pequeños, push sin force de la rama
`ticket/MAM-814-swimming` y PR **draft** a `main`, no merge ni limpieza.
El resultado remoto se entrega con número/URL y SHA en el cierre de la sesión.

**AVISO MAM-628/MAM-629:** posible choque de migraciones, rutas/URLs y archivos
compartidos de `basis/modules/training`. Este candidato no añade migraciones ni
cambia URLs; revisar compatibilidad de integración antes de cualquier merge,
sin renumerar migraciones ni resolver conflictos semánticos silenciosamente.
