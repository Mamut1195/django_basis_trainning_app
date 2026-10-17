# BASIS Training

PWA de entrenamiento para cuentas individuales privadas. Django 5.2 LTS sirve la interfaz y la API; Django Cotton UI, HTMX y Alpine proporcionan los componentes e interacciones. PostgreSQL es obligatorio en producción. No usa OpenDesign.

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
$env:BASIS_DATABASE_PATH = '.cache/dev.sqlite3'
.venv-win/Scripts/python.exe manage.py migrate
```

Para una demostración local con registro manual habilitado:

```powershell
$env:BASIS_DEVELOPMENT_ACCESS = '1'
$env:BASIS_DEMO_PASSWORD = 'elige-una-clave-local-larga'
.venv-win/Scripts/python.exe manage.py seed_demo --email demo@basis.test
.venv-win/Scripts/python.exe manage.py runserver
```

Abre `http://127.0.0.1:8000/`. El comando de demostración no borra datos ni cambia la contraseña de cuentas existentes. No crea una suscripción ni cuotas IA. Sin esta opción de desarrollo, editar requiere correo verificado y acceso activo en Polar.

La configuración se recibe del entorno del proceso; no se carga `.env` automáticamente. `.env.example` documenta las variables. En desarrollo los correos se escriben en `.cache/mail/`; usa un SMTP configurado para entregas reales. El servidor genera una clave de desarrollo local en `.cache/`; producción exige `DJANGO_SECRET_KEY` explícita, nueva y privada.

## Datos anteriores

`db.sqlite3` no fue migrada durante esta entrega. Antes de actualizarla, conserva un respaldo. Las migraciones añaden identidades únicas sin adivinar qué cuenta posee los perfiles anteriores. El operador puede verificar la titularidad y ejecutar:

```powershell
.venv-win/Scripts/python.exe manage.py link_legacy_profile --account-id 123 --profile-id 456
```

La verificación del correo sigue siendo independiente. Las métricas heredadas se conservan con procedencia `legacy-unverified`; no se convierten retrospectivamente en RPE real ni en sesiones detalladas inventadas. `seed.py` conserva los datos sintéticos previos, pero su reinicio destructivo quedó deshabilitado.

## Integraciones y operación

Consulta [la arquitectura y contratos](docs/ARCHITECTURE.md), [el diccionario deportivo](docs/TRAINING_VARIABLES.md) y [la validación de esta entrega](docs/VALIDATION.md).

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
$env:DJANGO_SETTINGS_MODULE = 'basis_trainning_app.test_settings'
.venv-win/Scripts/python.exe manage.py test training.tests --noinput
.venv-win/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv-win/Scripts/ruff.exe check .
```

Para comprobar las carreras con bloqueos reales, define `DATABASE_URL` apuntando a un PostgreSQL local de pruebas. SQLite omite esas pruebas. El recorrido de navegador está en `scripts/browser_smoke.py`; usa una cuenta de demostración y un servidor local en el puerto 8765. Lee las variables `BROWSER_EXECUTABLE`, `BASIS_E2E_EMAIL` y `BASIS_E2E_PASSWORD`.

Linear es el estado del roadmap P-MAM-12. Un ticket solo puede pasar a Done cuando todo su alcance esté validado y exista un commit integrado en `main`; estar en el árbol de trabajo de esa rama no basta.
