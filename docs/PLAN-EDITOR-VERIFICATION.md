# MAM-629 · Calendario y editor de planes y ciclos

Base de esta revisión: `f76b873`, rama `ticket/MAM-629-calendario-editor`.
Incluye cuatro commits del editor y el merge `--no-ff` de `origin/main`
`128e746`, que integra PR #22. PR #24 permanece DRAFT. `head: ver PR #24`;
el ejecutor humano fijará el nuevo head después de revisar estos cambios.
La ampliación H2/H6 modificó únicamente tests y documentación, sin commits.
La corrección H1 parte de `e24c9cf` y añade la regla de dominio y su cobertura,
también sin commits.

## Comportamiento

- Desde Plan se abre el calendario semanal: siete días, selector de fecha,
  semana anterior/siguiente y árbol macro → meso → micro → sesión concreta.
- Los enlaces de semana usan HTMX, conservan el foco por identificadores
  estables y funcionan por navegación GET cuando JavaScript está deshabilitado.
- Crear desde plantilla privada copia un plan propio a un linaje independiente,
  desplaza fechas y conserva solo prescripciones programadas. No existe catálogo
  de programas predefinidos. No copia ejecuciones, resultados ni identidades de
  intención de la plantilla.
- Editar plan o ciclo crea otra versión con motivo, autor y fecha efectiva.
  Conserva borradores. Solo copia sesiones futuras sin ejecución; las demás
  permanecen consultables en su versión histórica y en la agenda efectiva.
- Por decisión de Jonathan, los ciclos hermanos del mismo plan no pueden
  solaparse, incluidos los macrociclos raíz con padre vacío. Las fechas son
  inclusivas: `[inicio, final]`, como la pertenencia de sesiones a un ciclo y
  los ciclos de un día que ya admite el dominio. Terminar el 7 y empezar el 8
  es adyacencia válida; terminar y empezar el 7 comparte un día y se rechaza.
  Se comprueba al crear, editar, cambiar de padre y aplicar una plantilla.
  La contención entre padre e hijo sigue siendo válida.
- Reprogramar, editar nombre/notas, omitir, cancelar o sustituir una sesión utiliza
  los casos de planificación existentes con bloqueo cuenta/linaje y revisión.
  La fecha y relación de intención se conservan al sustituir la prescripción.
- Antes de guardar se informa cuántas sesiones se copian y cuántas permanecen
  históricas. Una operación explícita puede afectar una sesión pasada sin
  ejecución. Conflictos y validaciones aparecen en el formulario correspondiente.
- La comparación muestra antes/después de metadatos, ciclos y sesiones; señala
  cambios de prescripción y permite consultar cada versión completa. La
  comparación de ciclos es de presentación por orden, sin atribuir identidad
  persistente entre ciclos de distintas versiones.
- Cotton, composiciones BASIS y tokens existentes; sin nuevo CSS, dependencia,
  modelo, migración, proveedor ni modificación de recursos PWA.

## Evidencia y conteos por fuente

Las cifras corresponden a alcances distintos. Los conteos de BT1 y BT3 son
anteriores a los 14 tests añadidos aquí; no se presentan como una nueva ejecución
completa después de esta ampliación.

| Alcance                                            | Conteo    | Fuente                                                                                               | Resultado y límite                                                           |
| -------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Suite completa mergeada, SQLite                    | 734 tests | BT1: `../../basis-runs/MAM-629/merge-main/gate-tests-sqlite.txt`                                     | VERIFIED histórico; `OK (skipped=64)`                                        |
| Suite completa mergeada, PostgreSQL                | 734 tests | BT1: `../../basis-runs/MAM-629/merge-main/gate-tests-postgresql.txt`                                 | VERIFIED histórico; `OK (skipped=2)`                                         |
| Subconjunto de tests de `checks.yml` en `f76b873`  | 525 tests | BT3, cifra comunicada en el encargo H6; etiquetas en `.github/workflows/checks.yml`                  | No equivale a la suite completa de BT1; no repetido aquí                     |
| Nuevos tests H2, `PlanEditorSecurityTests`         | 14 tests  | `tests/regression/test_plan_editor.py`; `../../basis-runs/MAM-629/codex2/gate-tests-plan-editor.txt` | VERIFIED en esta revisión                                                    |
| Módulo `tests.regression.test_plan_editor` tras H2 | 26 tests  | `../../basis-runs/MAM-629/codex2/gate-tests-plan-editor.txt`                                         | VERIFIED; 12 existentes + 14 nuevos; `OK`, sin omisiones ni fallos esperados |

La revisión lee los logs históricos de BT1; no vuelve a levantar PostgreSQL.
La suite completa posterior a H2 y el subconjunto BT3 posterior a H2 quedan
NOT RUN. No se suman ni confunden conteos de suites con alcances diferentes.

## Cobertura añadida en H2

Los 14 métodos nuevos se distribuyen así; los subcasos no se cuentan como tests
adicionales:

| Grupo                          | Métodos nuevos | Cobertura                                                                                                                                                                                                                         |
| ------------------------------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Aislamiento entre cuentas      | 7              | Plantilla con origen u objetivo ajenos; GET/POST de plan, alta/edición de ciclo y alta de sesión ajenos; ciclo ajeno dentro de un plan propio; acciones de sesión `edit`, `move`, `change` con `skipped`, `cancelled` y `replace` |
| Referencias a otro plan propio | 4              | Padre ajeno al plan al crear/editar ciclo; microciclo de otro plan al mover/crear sesión                                                                                                                                          |
| Sustitución ajena              | 1              | `replacement` apuntando a una sesión planificada de otra cuenta, con prescripción completa                                                                                                                                        |
| CSRF estricto                  | 1              | `Client(enforce_csrf_checks=True)`: 20 POST sin token, diez variantes con y sin cookie CSRF; todos devuelven 403                                                                                                                  |
| GET sin efectos de mutación    | 1              | Las diez variantes reciben por query string los mismos campos de mutación; todas devuelven 200 sin alterar la BD                                                                                                                  |

Las diez variantes son `plan-template`, `plan-edit`, `editor-cycle-new`,
`editor-cycle`, `editor-session-new` y `editor-session` con `edit`, `move`,
`change/skipped`, `change/cancelled` y `change/replace`.

Cada petición cubierta compara el estado completo antes/después de todos los
modelos gestionados de la BD de tests, incluidas relaciones intermedias,
versiones y registros de auditoría. Las fixtures y el login se preparan antes
del snapshot. Las rutas de recursos ajenos devuelven 404; las referencias
inválidas devuelven 200 con error en el campo correspondiente y sin persistir
cambios. El editor usa una sesión planificada como `replacement`; no dispone
de campos de sustitución por ejercicio o por entidad plantilla independiente.

Bugs encontrados en estos escenarios H2: ninguno. No se añadieron
`expectedFailure`. H1 está corregido por decisión de Jonathan; su evidencia
se registra por separado a continuación.

## Corrección H1: ciclos hermanos sin solapes

`validate_cycle` comprueba intersecciones inclusivas entre hermanos y omite
el propio ciclo al editar. `validate_definition` aplica la regla al agregado.
El alta individual obtiene los hermanos del mismo plan bajo el bloqueo ya
existente; `Cycle.clean` usa la misma regla para el formulario. El editor
reutiliza sus errores de formulario, sin 500 ni escrituras parciales. No hay
migraciones ni conversión de fechas o corrección automática de datos históricos.
Una plantilla histórica con solapes se rechaza antes de copiarla.

Evidencia H1: `../../basis-runs/MAM-629/codex3/result.md`, logs `gate-*.txt`
y recibos `status-*.json`. El wrapper `gate-h1.py` usa SQLite en memoria,
`config.test_settings`, `AI_ENABLED=0`, `POLAR_ENABLED=0` y una clave ficticia
de tests. Sus auxiliares y cachés se guardan en esa carpeta.

| Gate H1                                    | Estado   | Resultado                                                           |
| ------------------------------------------ | -------- | ------------------------------------------------------------------- |
| Dominio de planning                        | VERIFIED | 25 tests: 18 existentes y 7 nuevos                                  |
| `tests.regression.test_plan_editor`         | VERIFIED | 32 tests: 26 existentes y 6 nuevos                                  |
| Ruff check global                          | VERIFIED | Sin incidencias                                                     |
| Ruff format --check de los archivos H1     | VERIFIED | 7 archivos Python conformes                                        |
| Ruff format --check global                 | FAILED   | Formato preexistente en `manage.py` y `scripts/arch09_remediation.py` |
| Mypy core                                  | VERIFIED | 126 archivos sin errores                                           |
| Mypy Django                                | FAILED   | 4 errores preexistentes en `PlanEditorSecurityTests`                |
| Django check                               | VERIFIED | Cero incidencias                                                    |
| Makemigrations --check --dry-run            | VERIFIED | Sin cambios detectados                                              |
| PostgreSQL, navegador y suite completa H1  | NOT RUN  | Fuera del alcance solicitado                                       |

Los fallos de formato se reprodujeron con el contenido de `HEAD`; ambos
archivos permanecen intactos. Los cuatro errores de mypy Django se reprodujeron
con `--shadow-file` del test original de `HEAD`. No se modificaron ni eliminaron
métodos de tests existentes; solo se amplió la fixture en memoria para aportar
los ciclos al contexto de alta. Todos los existentes de las dos suites
solicitadas pasan. Los 13 métodos nuevos cubren adyacencia,
extremos compartidos, contención/igualdad de rangos, orden inverso, creación,
edición, cambio de padre, plantilla y rechazo antes de un escritor permisivo.
Los rechazos web comparan todos los modelos gestionados antes/después,
incluidas versiones y auditoría. Estos conteos no sustituyen la evidencia
histórica de suite completa.

Para repetir un gate desde la raíz:

```powershell
.venv-win/Scripts/python.exe -B ../../basis-runs/MAM-629/codex3/gate-h1.py tests-domain
.venv-win/Scripts/python.exe -B ../../basis-runs/MAM-629/codex3/gate-h1.py tests-editor
```

El mismo wrapper admite `ruff-check`, `ruff-format`, `ruff-format-h1`,
`mypy-core`, `mypy-django`, `django-check` y `migrations`. `result.md` detalla
los comandos y las comprobaciones de la base.

## Checks de esta revisión H2/H6

Evidencia: `../../basis-runs/MAM-629/codex2/`. Cada gate conserva su salida y
un recibo `status-*.json` con comando, código de salida y fechas UTC.

| Gate                                              | Estado   | Evidencia                                                  |
| ------------------------------------------------- | -------- | ---------------------------------------------------------- |
| Ruff check de todo el worktree                    | VERIFIED | `gate-ruff-check.txt`                                      |
| Ruff format --check del test                      | VERIFIED | `gate-ruff-format.txt`                                     |
| Regresión del editor, SQLite en memoria           | VERIFIED | `gate-tests-plan-editor.txt`; 26 tests                     |
| Django check                                      | VERIFIED | `gate-django-check.txt`; cero incidencias                  |
| Prettier del documento por stdin con contenido LF | VERIFIED | `gate-prettier.txt`                                        |
| Suite completa SQLite/PostgreSQL después de H2    | NOT RUN  | Este encargo limita la ejecución a la regresión del editor |
| Aceptación de navegador de esta revisión          | NOT RUN  | No solicitada; no se inicia navegador                      |
| Systems                                           | NOT RUN  | Prohibido por el encargo                                   |
| LIVE, Polar, IA y SMTP reales                     | NOT RUN  | Proveedores deshabilitados; correo de tests en memoria     |
| Dispositivos reales                               | NOT RUN  | Pendiente de aceptación humana                             |
| Integración con PR #23                            | NOT RUN  | Pendiente de integración conjunta                          |
| Certificación WCAG                                | NOT RUN  | Los tests y las capturas históricas no la acreditan        |
| Lector de pantalla                                | NOT RUN  | Pendiente de aceptación humana                             |

## Comandos reproducibles desde la raíz del worktree

El wrapper de esta revisión fuerza SQLite en memoria y una clave ficticia
exclusiva de tests, sin leer ni imprimir credenciales. Configuración común:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
$env:AI_ENABLED = '0'
$env:POLAR_ENABLED = '0'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:PYTHONDONTWRITEBYTECODE = '1'
```

Invocaciones exactas del wrapper, una por gate:

```powershell
../../basis-runs/MAM-629/codex2/gate-h2-h6.ps1 ruff-check
../../basis-runs/MAM-629/codex2/gate-h2-h6.ps1 ruff-format
../../basis-runs/MAM-629/codex2/gate-h2-h6.ps1 tests-plan-editor
../../basis-runs/MAM-629/codex2/gate-h2-h6.ps1 django-check
.venv-win/Scripts/python.exe -B ../../basis-runs/MAM-629/codex2/prettier-doc.py --check
```

Los cuatro primeros ejecutan, respectivamente:

```powershell
.venv-win/Scripts/python.exe -B -m ruff check .
.venv-win/Scripts/python.exe -B -m ruff format --check tests/regression/test_plan_editor.py
.venv-win/Scripts/python.exe -B manage.py test tests.regression.test_plan_editor -v 2 --noinput
.venv-win/Scripts/python.exe -B manage.py check
```

`prettier-doc.py` comprueba que el archivo esté en LF y envía su contenido a
`node node_modules/prettier/bin/prettier.cjs --check --stdin-filepath
docs/PLAN-EDITOR-VERIFICATION.md --ignore-path .gitignore`. El uso de
`.gitignore` evita que `.prettierignore`, que excluye `docs/`, omita el documento.
No se altera la configuración del repositorio.

## Evidencia histórica y límites

- BT1 conserva los gates de la base mergeada en
  `../../basis-runs/MAM-629/merge-main/gate-*.txt`.
- La aceptación Chromium histórica del editor está en
  `../../basis-runs/MAM-629/acceptance-codex1/run-20261027-190100-409/`;
  la aceptación posterior al merge, en
  `../../basis-runs/MAM-629/acceptance-merge-20261027-191732/`.
  Estas rutas identifican evidencia previa; no se ejecutó ni se revalidó una
  aceptación de navegador en esta revisión H2/H6.
- Las fixtures son locales y ficticias. La distancia usada para comprobar
  conservación de una ejecución es un dato de prueba, sin atribución a personas
  ni entrenamientos reales.
- Las comparaciones de ciclos son descriptivas por orden; para cambios
  complejos deben consultarse ambos árboles completos. No hay edición masiva
  por arrastre.
- La plantilla conserva prescripciones y referencias de medición; no calcula
  ni actualiza umbrales deportivos para el nuevo período.
- Las verificaciones automáticas no equivalen a certificación WCAG, uso con
  lector de pantalla ni aceptación en dispositivos físicos.

## Convivencia con PR abiertos

- PR #22 está integrado en `origin/main` mediante `128e746` y mergeado en
  `f76b873`. Las rutas de editor y reproductor conviven en la base real;
  los conteos BT1 anteriores corresponden a esa suite completa mergeada.
- PR #23: integración conjunta NOT RUN. Esta ampliación no cambia PWA, offline,
  service worker, reproductor, rutas ni migraciones.
- PR #24 continúa DRAFT; el nuevo head lo fijará el ejecutor humano.
- H1 corregido por decisión de Jonathan: hermanos del mismo plan sin solapes,
  con fechas inclusivas y adyacencia permitida.
