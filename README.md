# BASIS Training

PWA de entrenamiento para cuentas individuales privadas. Django 5.2 LTS sirve la interfaz y la API; Django Cotton UI, HTMX y Alpine proporcionan los componentes e interacciones. PostgreSQL es obligatorio en producción. No usa OpenDesign.

La arquitectura actual se organiza en `config/`, `basis/modules/<area>/{domain,application,adapters}`, contratos `public.py`, `basis/bootstrap/` y `basis/shared/`. Las pruebas originales están en `tests/regression/`. Consulta la [estructura y estado de aceptación](docs/ARCHITECTURE.md) y el [mapa de entradas y casos de uso](docs/architecture/ENTRYPOINTS.md). ARCH-01..10 y la épica BASIS-ARCH/MAM-821 están Done, con integración en `main/24484b7` y [recibo de aceptación](docs/architecture/ARCHITECTURE-ACCEPTANCE-2026-10-20.json). Al readback de Luna del **2026-10-21 19:47:27.908 UTC**, también están Done **MAM-810, MAM-620, MAM-622 y MAM-623**. Luna los encontró ya Done y conservó sus `completedAt`; no se le atribuyen transiciones nuevas. El proyecto suma **46 tickets: 22 Done, 23 In Progress y uno Backlog**; los **35 funcionales son 11 Done y 24 abiertos**, con 11 de arquitectura Done. MAM-626/MAM-627 siguen In Progress: lector de pantalla NOT RUN y aceptación humana PENDING. El [cierre de la cadena](docs/DEVELOPMENT_2026-10-21.md#cierre-de-la-cadena-mam-810--620--622--623) registra fuentes, fechas, PR y CI; los [registros históricos](docs/ARCHITECTURE_EXECUTION.md) conservan sus resultados originales.

Catálogo se integró en [PR #3](https://github.com/Mamut1195/django_basis_trainning_app/pull/3) y operaciones en [PR #4](https://github.com/Mamut1195/django_basis_trainning_app/pull/4). La cadena **MAM-810 → MAM-620 → MAM-622 → MAM-623 está cerrada**, mediante PR [#6](https://github.com/Mamut1195/django_basis_trainning_app/pull/6), [#7](https://github.com/Mamut1195/django_basis_trainning_app/pull/7), [#8](https://github.com/Mamut1195/django_basis_trainning_app/pull/8) y [#9](https://github.com/Mamut1195/django_basis_trainning_app/pull/9). El último merge de código es `71751bd2ee10fa7dff9f2c7a9d4f9ccda7c6c2cd`, con [CI postmerge verde](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39662083662). MAM-811 y MAM-816 son los dos High elegibles por dependencias, **sin iniciar trabajo nuevo**; MAM-638 conserva once bloqueantes pendientes. Esta conciliación cierra el lote actual.

## Funcionalidad implementada

- Registro de adultos, verificación por correo, acceso y recuperación de contraseña.
- Perfil, disponibilidad, equipo, experiencia por disciplina, objetivos, peso y bienestar.
- Planes versionados: objetivo → macrociclo → mesociclo → microciclo → sesión programada → ejecución.
- Fuerza por serie: repeticiones o rangos, cargas decimales, % RM medido, RPE/RIR objetivo y real, descansos, tempo, ROM, lado, isometrías y grupos.
- Cardio, running, ciclismo y natación: variables específicas, bloques e intervalos, objetivo y resultado separados. FC, potencia y cadencia son opcionales y nunca se inventan.
- Hiking: distancia, tiempos, ascenso/descenso, altitudes, terreno, dificultad declarada con escala/fuente y mochila. Trekking agrupa jornadas en etapas sin duplicar cargas o distancias.
- Progreso por disciplina, adherencia, carga interna con protocolo explícito y exportación privada. El historial anterior conserva sus registros y se muestra por separado.
- PWA con recursos locales, sesiones descargadas, registro offline, cola persistente e idempotente, conflictos revisables y exportación local.
- Integraciones preparadas para Polar y DeepSeek, deshabilitadas hasta configurarlas. Un retorno del checkout no concede acceso; una propuesta IA no cambia el plan hasta aceptarla.

## Desarrollo en Windows

El entorno `.venv` preexistente tiene estructura Linux. Se conserva; utiliza otro entorno en Windows:

```powershell
uv --cache-dir .cache/uv venv .venv-win --python 3.13
uv --cache-dir .cache/uv pip install --python .venv-win/Scripts/python.exe -r requirements-dev.txt
$env:BASIS_DATABASE_PATH = '.cache/dev-arch09.sqlite3'
.venv-win/Scripts/python.exe manage.py migrate
```

Para una demostración local con registro manual habilitado:

```powershell
$env:BASIS_DEVELOPMENT_ACCESS = '1'
$env:BASIS_DEMO_PASSWORD = 'elige-una-clave-local-larga'
.venv-win/Scripts/python.exe manage.py seed_demo --email demo@basis.test
.venv-win/Scripts/python.exe manage.py runserver
```

Abre `http://127.0.0.1:8000/`. El comando de demostración no borra datos ni cambia la contraseña de cuentas existentes. No crea una suscripción ni cuotas IA. El perfil personal, objetivo de texto, preferencias, disciplinas y peso son gratuitos para cuenta activa, vinculada y verificada; consulta/exportación propias conservan su política autenticada. Entrenamiento, RM, objetivos estructurados, planes e IA mantienen sus controles comerciales.

La configuración se recibe del entorno del proceso; no se carga `.env` automáticamente. `.env.example` documenta las variables. En desarrollo los correos se escriben en `.cache/mail/`; usa un SMTP configurado para entregas reales. El servidor genera una clave de desarrollo local en `.cache/`; producción exige `DJANGO_SECRET_KEY` explícita, nueva y privada.

## Datos anteriores

ARCH-09 follows [ADR-002](docs/architecture/ADR-002-FINAL-PERSISTENCE.md): there is no production deployment and the final module schema starts from an empty database. The original `db.sqlite3` is untouched; these initial migrations are not an in-place upgrade for the retired application schema. Use a new development database path as above. The old copy-migration verifier has been retired.

`link_legacy_profile --account-id 123 --profile-id 456` remains available for explicitly linking an unassigned profile already present in the final schema. Email verification remains independent. Historical records retain `legacy-unverified` provenance; no results are invented. `seed.py` conserva su contenido histórico, pero rechaza ejecución e importación antes de cargar Django o abrir una base. Para demostraciones usa `manage.py seed_demo`, que exige flags de desarrollo y contraseña explícitos, es idempotente y no se ejecuta en el arranque/despliegue. Consulta la [política y evidencia de integridad](docs/HISTORY_INTEGRITY.md).

## Integraciones y operación

Consulta [la arquitectura y contratos](docs/ARCHITECTURE.md), [el diccionario deportivo](docs/TRAINING_VARIABLES.md), [la validación histórica inicial](docs/VALIDATION.md), [el catálogo verificado](docs/CATALOG_VERIFICATION.md#readback-de-integración-y-cierre-2026-10-21) y [el runbook y readback operativo](docs/OPERATIONS_VERIFICATION.md#readback-de-integración-y-cierre-2026-10-21). El [cierre de integridad](docs/HISTORY_INTEGRITY.md#cierre-operativo-mam-617-2026-10-20) conserva su propia entrega anterior.

La app reutiliza el [logo y la identidad oficial de BASIS](docs/BRAND.md). Los colores compartidos se editan en `basis/adapters/web/static/basis/brand/identity.json`, cargado por `basis/adapters/web/brand.py`; los tokens semánticos y de componentes están en `basis/adapters/web/static/basis/css/tokens.css`.

La primera tanda añade un [contrato deportivo con semana ejecutable](docs/TRAINING_CONTRACT.md), las [reglas de fuerza y sus límites](docs/STRENGTH_METRICS.md) y un [verificador de entorno aislado](docs/REPRODUCIBILITY.md). El avance y los criterios pendientes están en [el registro de integración](docs/IMPLEMENTATION_WAVE_01.md).

Polar requiere un producto mensual con un único precio activo de USD 5, impuestos `exclusive` y prueba nativa de siete días con tarjeta. Configura token, producto y un secreto Standard Webhooks reciente. Usa sandbox primero. `/webhooks/polar/` valida firma y vigencia y consulta el estado autoritativo del cliente. Mantén una conciliación periódica además de los eventos.

La IA usa el alias configurable `deepseek-flash`. `AI_ENABLED=0` es el valor inicial. Con credenciales y evaluación aprobada, el worker se ejecuta con:

```powershell
.venv-win/Scripts/python.exe manage.py process_ai_jobs
```

No hay reintentos automáticos de llamadas ambiguas. El tope pagado es USD 1 por período, con hasta 200 consultas y 8 planes; la prueba tiene USD 0,03 vitalicios, 5 consultas y 1 plan, además de un fondo global de USD 5 por mes. La contabilidad usa tokens medidos y tarifas pico conservadoras; no representa una factura exacta del proveedor.

`Dockerfile`, `compose.yaml` y `deploy/Caddyfile` preparan web, worker, PostgreSQL y TLS. No despliegan recursos por sí solos. Aplica migraciones como una operación única antes de arrancar workers; configura SMTP, dominio, secretos, HTTPS y respaldos. `TRUST_PROXY=1` solo es válido detrás de un proxy controlado que sustituya las cabeceras de reenvío.

Respaldos PostgreSQL y restauración verificable en una base nueva:

```powershell
python scripts/backup_db.py backup artifacts/backups/basis.dump
python scripts/backup_db.py restore-test artifacts/backups/basis.dump --database basis_restore_check
```

Programa respaldos fuera de este servidor y prueba su restauración. Los archivos de respaldo contienen datos privados y se excluyen del repositorio.

## Verificación

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.test_settings'
.venv-win/Scripts/python.exe manage.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.sync.adapters.test_wire --noinput
.venv-win/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv-win/Scripts/python.exe -m unittest discover -s tests_architecture
.venv-win/Scripts/python.exe -m mypy --config-file mypy-core.ini
.venv-win/Scripts/python.exe -m mypy --config-file mypy-django.ini
.venv-win/Scripts/python.exe scripts/architecture_check.py
.venv-win/Scripts/lint-imports.exe
.venv-win/Scripts/ruff.exe check .
```

Para comprobar las carreras con bloqueos reales, define `DATABASE_URL` apuntando a un PostgreSQL local de pruebas. SQLite omite esas pruebas. El recorrido de navegador está en `scripts/browser_smoke.py`; usa una cuenta de demostración y un servidor local en el puerto 8765. Lee las variables `BROWSER_EXECUTABLE`, `BASIS_E2E_EMAIL` y `BASIS_E2E_PASSWORD`.

Linear es el estado del roadmap P-MAM-12. Un ticket solo puede pasar a Done cuando todo su alcance esté validado y exista un commit integrado en `main`; estar en el árbol de trabajo de esa rama no basta.

## Formato de presentación

Instalar `requirements-dev.txt` y ejecutar `npm ci --ignore-scripts`. Ruff está fijado en requirements.txt, djLint en requirements-dev.txt y Prettier en package-lock.json.

```powershell
python -m ruff format basis config tests tests_architecture scripts/architecture_check.py scripts/browser_smoke.py scripts/acceptance_browser.py scripts/verify_environment.py
python -m djlint basis --reformat
npm run format
```

Para comprobar sin modificar: añadir `--check` a Ruff format, usar `python -m djlint basis --check` y `npm run format:check`. CI aplica estos controles. Python usa 100 columnas; Django/Cotton, CSS y JavaScript usan dos espacios. Se excluyen migraciones históricas, evidencias, recursos generados y código de terceros. Prettier conserva el orden de las reglas CSS; JavaScript continúa en esta entrega.

Referencias: [djLint Django](https://djlint.com/docs/languages/django/), [instalación fijada de Prettier](https://prettier.io/docs/install.html).
