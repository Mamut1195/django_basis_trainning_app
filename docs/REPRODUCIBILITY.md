# Verificación reproducible — BASIS-001 / MAM-615

El lanzador `scripts/verify_environment.py` usa solo stdlib. El intérprete indicado
con `--python` debe tener Python **3.13**, Django **5.2** y todas las versiones de
`requirements.txt`. No instala paquetes ni inicia servicios. Ejecutar desde la raíz
del repositorio; no requiere activar el venv ni configurar variables de producción.

## Windows / PowerShell

Con el entorno disponible:

```powershell
$python = (Resolve-Path .venv-win/Scripts/python.exe).Path
& $python -B scripts/verify_environment.py --python $python
$LASTEXITCODE
```

Para guardar evidencia, elegir un nombre **nuevo**, con directorio padre existente:

```powershell
$report = ".cache/basis001-$(Get-Date -Format yyyyMMdd-HHmmss)-$([guid]::NewGuid().ToString('N')).json"
& $python -B scripts/verify_environment.py --python $python --report $report
$LASTEXITCODE
Get-Content $report
```

Instalación desde cero, cuando las políticas del entorno lo permitan, en un venv
nuevo de nombre exclusivo (no reutilizar ni borrar el venv de otro ejecutor):

```powershell
$venv = ".cache/basis001-fresh-$([guid]::NewGuid().ToString('N'))"
py -3.13 -m venv $venv
# Ejecutar el siguiente paso solo si el anterior terminó con código 0.
$freshPython = (Resolve-Path "$venv/Scripts/python.exe").Path
& $freshPython -m pip install -r requirements.txt
# Ejecutar el verificador solo si la instalación terminó con código 0.
& $freshPython -B scripts/verify_environment.py --python $freshPython
```

El CLI puede lanzarse con otro Python que tenga stdlib; `--python` selecciona el
intérprete que importa Django y ejecuta todas las comprobaciones. No admite un
comando de shell con argumentos dentro de `--python`: usar la ruta al ejecutable.

## Comprobaciones y aislamiento

1. Valida Python 3.13, Django 5.2 y versiones instaladas contra cada pin simple
   `paquete==versión` de `requirements.txt`. Registra versiones y SHA-256 del archivo.
2. Crea `.cache/environment-<nombre exclusivo>/verification.sqlite3`, inicialmente
   inexistente. Nunca lee, copia ni abre `db.sqlite3` ni migra una DB proporcionada
   por el usuario. Rechaza `.cache` redirigida fuera del proyecto y DBs existentes.
3. Lanza un subproceso con `-I -B` y entorno mínimo. No hereda `DATABASE_URL`,
   `PYTHONPATH`, secretos ni configuración de servicios. Fija `BASIS_DATABASE_PATH`
   y `DJANGO_SETTINGS_MODULE=basis_trainning_app.test_settings`. Usa una clave
   efímera para evitar leer o crear la clave local de desarrollo.
4. Antes de `django.setup()`, importa `test_settings` y configura explícitamente
   una única conexión SQLite al archivo temporal, sin routers, con correo/cache
   en memoria, IA desactivada, sin proxy confiado, sin redirección HTTPS y con
   almacenamiento de archivos dentro del temporal. Esta configuración de prueba
   no sirve para producción; `test_settings` usa hashing rápido de contraseñas.
5. Ejecuta en orden `check`, `migrate --noinput`,
   `makemigrations --check --dry-run`, deteniéndose ante el primer fallo.
6. Con Django test client comprueba `GET /health/` (200 y `status=ok`),
   `GET /accounts/login/` (200) y un POST de login con CSRF habilitado y credenciales
   efímeras. Verifica la redirección 302 y la identidad en la sesión persistida.
7. Cierra conexiones y elimina solo su propio directorio temporal incluso al
   fallar el subproceso o agotarse el timeout. No elimina `.cache`, venvs ni
   directorios vecinos. Cada ejecución y cada proceso paralelo usa otra DB.

No hay servidor HTTP ni llamadas a servicios externos en este recorrido. El
timeout del subproceso es 180 segundos, configurable con `--timeout N` positivo.
Si un proceso es terminado forzosamente o el SO impide el cleanup puede quedar
su directorio temporal; el CLI no busca ni elimina restos de otras ejecuciones.

## JSON y códigos de salida

JSON por stdout; `--report` escribe el mismo objeto en un archivo nuevo mediante
creación exclusiva. Nunca sobrescribe un reporte existente ni crea sus padres.
Las etapas llevan `VERIFIED`, `FAILED` o `NOT RUN`, tiempos, versiones y resultados
HTTP sin cuerpos, cookies, contraseñas, claves ni variables de entorno. Los logs,
tracebacks y mensajes de excepción externos se omiten para evitar filtraciones;
un fallo muestra la etapa y el tipo de excepción, con un identificador fijo cuando
es propio del verificador. Un timeout puede perder los detalles de etapas parciales.

| Código | Significado |
| --- | --- |
| 0 | Todas las comprobaciones y cleanup verificados. |
| 1 | Dependencias, aislamiento, comando Django o runtime fallido. |
| 2 | Error de argumentos, ejecutable, reporte, protocolo o cleanup. |
| 3 | Timeout del subproceso; se intenta cleanup igualmente. |

Los errores de argumentos de argparse usan stderr y código 2. Los demás errores
gestionados generan JSON. El código 0 certifica solo este recorrido SQLite.

## Tests del verificador

```powershell
& .venv-win/Scripts/python.exe -B -m unittest training.tests.test_environment_verifier -v
& .venv-win/Scripts/python.exe -B -m ruff check scripts/verify_environment.py training/tests/test_environment_verifier.py
```

Los tests stdlib no arrancan el runner Django ni crean una base de suite. Cubren
allowlist de entorno, rechazo de DBs existentes/ajenas, archivos vecinos intactos,
errores de arranque/protocolo/cleanup, timeout y rechazo de sobrescritura de reportes.
El test de integración ejecuta el CLI real con `DATABASE_URL` y
`BASIS_DATABASE_PATH` heredados apuntando a una SQLite señuelo propia: exige que
sus bytes queden intactos y que las seis etapas pasen en otra DB temporal.

## Límites y estado de instalación limpia

Evidencia local de esta entrega (2026-10-17): **VERIFIED** los 7 tests stdlib,
Ruff check/format sobre los dos archivos Python y el CLI real con `.venv-win`.
Reporte: `.cache/basis001-environment-8cdc97a4b39a44d3882b45c27fee429f.json`
(evidencia local ignorada por Git). Registra Python 3.13.7, Django 5.2.18,
SQLite 3.50.4, 22 pins coincidentes, las seis etapas verificadas, login 200/302,
health 200, sesión autenticada, CSRF habilitado, cleanup verificado y salida 0.
También se comprobó un fallo real con ejecutable inexistente: JSON sin traceback,
`launcher_failed`, código 2 y cleanup verificado. No se ejecutó la suite completa,
PostgreSQL ni una instalación fresh en esta entrega.

SQLite comprueba importación, dependencias, migraciones desde cero, consistencia
de modelos y acceso web básico. No certifica PostgreSQL: concurrencia, bloqueos,
aislamiento transaccional, SQL específico, índices, permisos ni backups deben
validarse por separado en una DB PostgreSQL exclusiva autorizada. Este verificador
no conecta con PostgreSQL y no ejecuta la suite compartida del coordinador.
Tampoco certifica navegador/PWA, archivos estáticos compilados, despliegue,
configuración productiva, SMTP, pagos ni IA LIVE.

El 2026-10-17 el coordinador informó que la instalación fresh con uv en
`.cache/verification-venv` quedó **FAILED por el entorno**: la política deny
`**/*.pem` impidió copiar `certifi/cacert.pem`. No se intentó leer ese archivo,
escalar permisos ni eludir la restricción. Ese venv es ajeno y no se usa ni se
borra. La validación con `.venv-win` existente no reemplaza una instalación limpia.
Ese bloqueo local quedó resuelto como criterio de aceptación por la instalación
en un runner nuevo de [CI 39067380697](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39067380697):
dependencias, checks, 97 pruebas PostgreSQL y estáticos terminaron correctamente
sobre el commit `50583c6` integrado en `main`. **BASIS-001/MAM-615 está Done**.
El [registro de integración](IMPLEMENTATION_WAVE_01.md#integración-remota-y-cierre-verificados)
separa esa evidencia remota de la restricción que sigue vigente en Windows.
El workspace es compartido: esta entrega solo asigna los tres archivos indicados
y no integra ni certifica los demás cambios preexistentes del repositorio.
