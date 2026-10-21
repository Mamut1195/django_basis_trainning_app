# Operación verificable — MAM-637 / BASIS-023

## Alcance y criterios

Instalación de referencia descartable: Django 5.2.18, Python 3.13.7 y PostgreSQL
18.4. Se comprueba arranque, controles deploy, conservación de perfiles, versiones
de planes, sesiones, series y referencias RM, recuperación y carga representativa.
Los cuatro criterios comunicados por Luna guiaron la entrega local. Estado actual:
**MAM-637 Done**, con integración y readback separados en
[el cierre postmerge](#readback-de-integración-y-cierre-2026-10-21). Los registros
locales y sus límites conservan la atribución a sus propios candidatos.

La evidencia local pertenece al candidato exacto (base Git más SHA-256 de todos
sus archivos versionados/nuevos no ignorados). Un cambio posterior invalida esa
identidad y exige repetir los checks afectados. `.cache` contiene resultados,
backups sintéticos y recursos de cada ejecución; no se publica ni reutiliza un
PASS de otro candidato.

## Configuración de referencia

Inyectar secretos mediante el entorno del servicio/gestor de secretos. No guardar
salidas de `docker compose config`, `docker inspect`, entornos completos ni URLs
con credenciales en tickets/logs. El archivo `.env.example` es orientativo; no se
carga automáticamente desde Python.

Gunicorn registra accesos sólo con método, status, duración y bytes, sin URL/query/cookies.
`deploy/gunicorn_config.py` protege también `gunicorn.error`: parser, excepciones
de worker y timeouts producen eventos contables con severidad, PID, código de
evento y clase permitida, nunca el mensaje de excepción. El status es 0 si el
evento no representa una respuesta HTTP o no se puede determinar con certeza.
En producción los loggers HTTP/seguridad de Django conservan sólo el código de
respuesta: no incluyen rutas con tokens de verificación/reset, objeto request ni
excepciones que pudieran contener filas o secretos. Para diagnosticar, reproducir
el fallo en un entorno aislado con datos sintéticos; no habilitar DEBUG público.

Variables requeridas para Compose:

- `DJANGO_SECRET_KEY`: secreto aleatorio único de al menos 50 caracteres.
- `POSTGRES_PASSWORD`: contraseña única; codificar caracteres reservados de URL
  porque Compose la interpola en `DATABASE_URL`. Para credenciales arbitrarias,
  suministrar una URL correctamente codificada mediante un override privado.
- `DJANGO_ALLOWED_HOSTS`: dominio(s) exactos, sin esquema ni wildcard.
- `DJANGO_HEALTH_HOST`: un host de esa lista, por ejemplo `app.example.com`;
  la sonda conecta a loopback, pero envía ese Host. No exige añadir localhost
  a los hosts públicos permitidos. Mantener `/health/` sin autenticación.
- `PUBLIC_URL` y `CSRF_TRUSTED_ORIGINS`: URL(s) HTTPS exactas.
- `TRUST_PROXY=1` sólo si el acceso a Gunicorn está restringido a un proxy TLS
  que elimina/reemplaza `X-Forwarded-Proto`. No exponer directamente ese puerto.
- SMTP: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
  `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` según el proveedor autorizado.
- IA/pagos: desactivados/sandbox por defecto; sus credenciales no son necesarias
  para deploy/health/backup ni para esta verificación.

Compose no publica PostgreSQL y enlaza HTTP sólo a `127.0.0.1`.
`BASIS_HTTP_PORT` permite asignar un puerto libre y `COMPOSE_PROJECT_NAME` aísla
red/volúmenes/contenedores. PostgreSQL 18 monta `/var/lib/postgresql` según el
layout upstream. Un proxy externo puede usar `deploy/Caddyfile` cuando esté
provisionado; este repositorio no activa DNS, certificados ni proveedores.

## Instalación / actualización controlada

Desde un checkout limpio del release deseado y con las variables anteriores
inyectadas (los comandos no contienen sus valores):

```sh
docker compose -p "$COMPOSE_PROJECT_NAME" build
docker compose -p "$COMPOSE_PROJECT_NAME" up -d db
docker compose -p "$COMPOSE_PROJECT_NAME" run --rm web python manage.py check --deploy --fail-level WARNING
# Antes de actualizar: detener escritores y tomar backup verificado (ver sección siguiente).
docker compose -p "$COMPOSE_PROJECT_NAME" --profile operations run --rm migrate
docker compose -p "$COMPOSE_PROJECT_NAME" up -d web worker
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T web python scripts/healthcheck.py
docker compose -p "$COMPOSE_PROJECT_NAME" ps
```

La imagen ejecuta como usuario sin privilegios, recolecta estáticos en build y
arranca Gunicorn con dos workers. Migraciones son un paso explícito único antes
de iniciar escritores; no se ejecutan en cada réplica. Ningún paso invoca seed.
Si migrate/check/readiness falla, no habilitar tráfico ni trabajadores. Registrar
release/imagen, fecha y resultado sin datos personales. Para la primera cuenta
usar el flujo de registro o administración explícita; nunca un seed de demo.

## Backup y restauración

`scripts/backup_db.py` utiliza los binarios PostgreSQL 18.4 de `PATH`. La imagen
web no los instala: usar el cliente nativo existente o el contenedor `db`.
Requiere conectividad y permisos de lectura/creación de la DB descartable para
el simulacro. Respeta `sslmode` de `DATABASE_URL`; para conexiones remotas usar
TLS con verificación y certificados administrados fuera del repo.

```sh
python -B scripts/backup_db.py backup /secure/backups/basis-RELEASE-TIMESTAMP.dump
python -B scripts/backup_db.py restore-test /secure/backups/basis-RELEASE-TIMESTAMP.dump --database basis_restore_UNIQUE
```

No sobrescribe archivos existentes, elimina dumps parciales al fallar y valida
el índice del archivo antes de declarar éxito. Usa formato custom, sin owners ni
ACL; no imprime diagnósticos de pg_dump/restore que pudieran contener filas o
credenciales. El restore crea una DB nueva y restaura en transacción; si falla,
la nueva DB puede quedar vacía y debe inspeccionarla/eliminarla su propietario.
Nunca usa `--clean` ni restaura sobre una base existente.

Con Compose y sin clientes en el host, un ejemplo para shell POSIX:

```sh
set -eu
umask 077
backup=/secure/backups/basis-RELEASE-TIMESTAMP.dump
test ! -e "$backup" && test ! -e "$backup.partial" || exit 1
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T db pg_dump -U basis -d basis -Fc --no-owner --no-acl > "$backup.partial" || { rm -f "$backup.partial"; exit 1; }
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T db pg_restore --list < "$backup.partial" >/dev/null || { rm -f "$backup.partial"; exit 1; }
mv -n "$backup.partial" "$backup"
docker compose -p "$COMPOSE_PROJECT_NAME" exec -T db createdb -U basis basis_restore_UNIQUE &&
  docker compose -p "$COMPOSE_PROJECT_NAME" exec -T db pg_restore -U basis -d basis_restore_UNIQUE --exit-on-error --single-transaction --no-owner --no-acl < "$backup" || exit 1
```

Para programar el backup, usar el scheduler del host ya disponible; sugerencia
inicial diaria y antes de cada release, con retención acordada por el propietario.
Trasladar copias cifradas a almacenamiento autorizado fuera del host y ensayar
restauraciones periódicamente. La frecuencia y retención son propuestas
operativas, no un RPO/RTO/SLA aprobado. No añadir cron, cloud ni infraestructura
enterprise sin necesidad medida. Los dumps contienen datos privados: permisos
0600/ACL equivalente, cifrado, acceso y eliminación competen al operador.

## Recuperación / rollback

1. Detener ingreso de escrituras y `worker`; identificar último release e imagen
   conocidos y el backup asociado. Preservar el estado fallido para diagnóstico.
2. Restaurar a una DB nueva. Comparar contenido, referencias y secuencias,
   ejecutar `migrate --plan`, checks y readiness con la versión elegida.
3. Para rollback de código sin cambio de esquema, arrancar la imagen anterior
   contra esa DB sólo después de comprobar compatibilidad; para migraciones
   incompatibles, recuperar código y backup emparejados. No ejecutar migraciones
   inversas/destructivas automáticamente.
4. Cambiar el secreto de conexión del servicio a la DB recuperada, recrear web,
   comprobar acceso autenticado/health y después reanudar worker y tráfico.
5. Documentar pérdida entre backup y parada de escritores, tiempo de restauración
   y validación. Conservar la DB anterior hasta aceptación y limpieza por su dueño.

El simulacro automatizado inyecta una modificación sólo en datos sintéticos,
recupera el snapshot previo en otra DB y sirve desde ésta. Prueba rollback de
datos/switchover bajo el mismo esquema. Un rollback entre dos releases con una
migración incompatible, restauración productiva real, DNS/TLS público y aceptación
humana son **NOT RUN** por esta herramienta.

## Verificador reproducible y carga

Proveer una DB PostgreSQL vacía creada expresamente, cuyo nombre empiece por
`basis_verify_`, con credencial exclusiva. No apuntar a una DB de usuario. Usar
puerto dinámico/cluster propio en ejecución paralela; el dueño del cluster lo
detiene y limpia. Ejemplo con herramientas PostgreSQL existentes:

```sh
# DATABASE_URL inyectada apunta exclusivamente a basis_verify_UNIQUE.
mkdir -p .cache
python -B scripts/verify_operations.py --report .cache/operations-UNIQUE.json --requests 160 --concurrency 4
```

El verificador rechaza nombres no descartables y bases no vacías antes de migrar;
no usa SQLite ni seed. Fuerza `config.settings`, DEBUG=0 y claves efímeras,
descarta credenciales de proveedores heredadas, ejecuta `check --deploy` con
warnings como error, migrate, drift y collectstatic. Produce 10 perfiles, 20
versiones de plan, 120 sesiones y 360 series con referencias RM explícitas.
Compara hashes de todas las tablas y secuencias tras backup, restore y migrate
idempotente; elimina únicamente la DB restore generada por esa ejecución.

Carga: HTTP real por loopback, ocho rutas (health, login, hoy, planes, progreso,
detalle de plan, sesión y exportación), sesión sintética autenticada, 160 lecturas
con cuatro clientes por defecto. Registra respuestas, p50/p95/máximo, throughput
y tiempos de backup/restore; nunca cuerpos, cookies ni URLs con secretos.
Verifica que las lecturas no alteran historia. El WSGI threaded de stdlib aquí
es un servidor de referencia descartable, no el Gunicorn de producción.

No hay umbral/SLA inventado: los errores HTTP bloquean el resultado; latencias
y throughput son mediciones para dimensionar una referencia. Para decidir
escalado, repetir en el host objetivo con Gunicorn, mezcla de escrituras y lecturas,
tamaño histórico esperado y métricas de CPU/RAM/conexiones PG. Ajustar workers
y límites de conexiones antes de introducir colas/cache/réplicas. La carga actual
no prueba saturación ni una capacidad de usuarios concurrentes productivos.

CI mantiene los checks existentes y añade construcción/arranque de la imagen,
deploy check estricto y un job operativo con clientes PG 18 y servidor PG 18.4. El JSON
operativo se publica como artefacto; no se suben dumps ni logs. El resultado
hosted sólo se acredita después de ejecutar CI sobre su SHA exacto. La preparación
local no lo presumía; el resultado de PR #4 se registra en el readback siguiente.

El job operativo corre en `ubuntu-24.04`, compatible con la distribución cold-cache
de Python 3.13.7 de `actions/setup-python@v7`; no ejecuta esa acción dentro de Debian.
Comprueba Git del runner **antes** de `actions/checkout` y exige un repositorio
real con HEAD, evitando el fallback REST sin `.git`. Instala clientes PostgreSQL
18 desde PGDG con su configurador upstream y antepone `/usr/lib/postgresql/18/bin`
al PATH. El servicio sigue siendo PG 18.4, accesible por loopback del runner.
Si falta Git o el checkout,
el verificador retorna FAILED y un JSON con etapa/tipo de error, sin traceback ni
entorno sensible. La regresión Linux de Gunicorn envía peticiones reales normales,
malformadas, con excepción y con timeout; comprueba estados/eventos y ausencia
de sentinels de ruta/query/excepción en los logs.

## Readback de integración y cierre (2026-10-21)

Rama real `feature/mam-637-operations`, commit de entrega
`55c10f2015ad88702a9ee8d9a1ffaf3d71648114`, integración de catálogo
`6bd14ea1539ebd671075562854a81f3ab852a5ac`; [PR #4](https://github.com/Mamut1195/django_basis_trainning_app/pull/4)
MERGED, merge `5edf6bd515ed56289b76da3339c9acaa4a7d4680`. El
[CI de código postmerge 39527756424](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424)
es SUCCESS en ese SHA, jobs
[operations](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424/job/118986296703) y
[postgres](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424/job/118986297018).
Logs: **288 PostgreSQL sin omisiones, 174 puras, mypy 113/330 y ocho contratos**;
build/arranque/deploy y regresión Gunicorn 200/400/500/500 sin sentinels sensibles.

El [artefacto operativo 12314030203](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424/artifacts/12314030203)
contiene `status=VERIFIED`, once checks VERIFIED,
`candidate.base_commit=5edf6bd515ed56289b76da3339c9acaa4a7d4680`,
`candidate_unchanged=true` y manifiesto
`2952ed477f977faa6f9c44806bc81c2f273b31690536fa70cdf1023df7b180d8`.
Python 3.13.7, Django 5.2.18, cliente PostgreSQL 18.6 de PGDG y servidor 18.4.
Verifica todas las tablas/secuencias, migración repetida y rollback de datos por
switchover: **10 perfiles, 20 planes, 120 sesiones, 360 series y 10 RM**;
backup **0,851 s**, restore **1,017 s**, limpieza VERIFIED.

Medición hosted del cierre de código PR #4, servidor WSGI threaded de referencia:

| Peticiones / HTTP 200 | Clientes | Rutas | Tiempo | Throughput | p50 | p95 | Máximo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 160 / 160 | 4 | 8 | 3,318 s | 48,23 req/s | 67,26 ms | 112,47 ms | 194,76 ms |

Esta medición no sustituye los recibos locales anteriores y sus entornos propios,
ni demuestra capacidad de Gunicorn en producción o de 1.000 usuarios. Producción,
restauración productiva y rollback entre releases con esquema incompatible siguen
**NOT RUN**; el rollback de datos bajo el mismo esquema sí está VERIFIED.

Luna `opencode-go/gpt-6-luna`, sesión `ses_ea3e2209dffehoFNLoBgWy77bW`, verificó
los cuatro criterios y **conservó el Done ya existente**, con
`completedAt=2026-10-21T01:30:50.347Z`. Corrigió el comentario de preparación
`7c01152f-50a9-4dec-9ad3-d72cd3913570` y dejó el comentario de cierre
`12f9062f-656f-4d04-b883-4098dca61bb8` a `2026-10-21T01:47:28.645Z`, con readback exacto.
No cambió el estado ni reejecutó tests de aplicación. El APPROVE independiente de
agentes no es un review de GitHub: el API de PR #4 devuelve cero reviews.

[Fuente y conteos conciliados](DEVELOPMENT_2026-10-20.md#cierre-del-lote-mam-621-y-mam-637-2026-10-21).
MAM-638 conserva once bloqueantes pendientes, incluido MAM-636 Backlog; cerrar
MAM-637 satisface sólo una dependencia. El CI del PR documental tiene identidad
propia y se comprobará por separado, sin atribuirle anticipadamente estos resultados.
