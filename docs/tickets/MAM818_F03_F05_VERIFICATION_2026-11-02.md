# MAM-818 — F03/F04/F05, verificación local 2026-11-02

## Estado y procedencia

Implementación local en worktree aislado `C:/Users/Jonnathan/.t3/worktrees/django-basis-trainning-app/t3-8cf5fdb3`, desde padre `fb9c17ea6ecc804ac2c3a27936fba1537c908976`. Plan escrito antes de editar: [MAM818_F03_F05_PLAN_2026-11-02.md](MAM818_F03_F05_PLAN_2026-11-02.md).

Commit de implementación: `8db53600fb24e2d4b28b41f82003615aeb04bced`. Alcances locales F03/F04/F05 verificados; MAM-818 permanece abierto. Los commits documentales posteriores no cambian fuentes ni pruebas.

MAM-818 consultado en Linear el 2026-11-02: In Progress, sin modificación remota. Leídos PENDIENTES, PLAN_PARALELIZACION, WAVE2_PLAN y arquitectura. No agentes adicionales, tickets nuevos, push, PR, Actions, producción, pagos ni proveedor IA LIVE. No lectura de archivos de secretos. No conciliación de bases existentes.

## Comportamiento implementado

- **F03:** `PricingPolicy.freeze()` produce `PricingSnapshot` inmutable: versión, tasas USD por token, límites de entrada/salida e identidades de modelo permitidas. Enqueue reserva con ese snapshot; ORM conserva JSON y versión. Settlement y conciliación calculan desde el job, aunque cambie la política/configuración actual. El cambio sintético 0.30 → 0.60 por millón produce 0.00036120 en el job anterior y 0.00060120 en el nuevo para el mismo uso; son resultados de fixtures locales.
- **Historia:** coach0002 identifica exclusivamente `flash-peak-2026-10-17`, modelos locales conocidos, kind y reserva histórica exacta. Fija las tarifas locales históricas 0.30 / 0.006 / 1.20 USD por millón y límites 4000/1500 o 8000/3000. Conserva costos, versiones y estados previos; no recalcula facturas. Versión/modelo/reserva desconocidos quedan sin snapshot verificable. El worker los retiene antes de llamar al proveedor. Un no-cobro acreditado explícitamente puede resolver falta de snapshot sin imputar tarifa; el uso conocido no puede hacerlo.
- **F04:** éxito exige modelo reportado dentro del conjunto explícito del snapshot. Modelo `reported`, desconocido o incompatible queda uncertain, sin costo inventado, sin liberar reserva y con bloqueo del servicio. Conserva observaciones numéricas seguras y el modelo reportado. Fixtures de éxito ahora reportan `deepseek-v4-flash`; existe prueba dedicada del desacuerdo.
- **F05:** `Jobs.reconcile()` recibe job, clave idempotente, actor, referencia, evidencia y decisión. `no_charge` exige confirmación explícita, sin tokens imputados; `usage` exige uso y modelo admitido y calcula por snapshot. Discrepancias, límites excedidos, uso contrario al ya observado, saldo incompatible o costo preexistente permanecen retenidos y auditados. No se reenvía proveedor, consulta facturación actual, crea propuesta ni reintenta el job.
- Ajusta solo reserva/gasto del período y fondo originales; conserva cuotas consumidas, incluso al renovar o pasar de trial a pago. Un job resuelto termina failed con resultado administrativo, sin aplicar respuesta. Repetición con misma clave/contenido devuelve el recibo original; clave con otro contenido se rechaza. Una decisión nueva sobre job resuelto se registra retenida y no ajusta saldos.
- Orden de locks: fondo original, cuenta, job, período; coincide con settlement. Ajustes, estado y auditoría comparten UoW. Dry-run sale sin commit; fallos después de insertar auditoría revierten todas las escrituras. Nunca se desbloquea automáticamente el servicio.
- Historial `AIReconciliation` append-only: triggers PostgreSQL/SQLite impiden UPDATE/DELETE, incluidos QuerySet/bulk. Triggers también congelan snapshot, versión y anclas contables del job. Constraints impiden saldos negativos, exceso de presupuesto/cuota y costos fuera de reserva. Un downgrade de 0002 se rechaza si ya existe historial de conciliación; la reversión probada sin auditorías conserva los importes/versiones históricos.

Estas tarifas/identidades describen **política local histórica**, no precio LIVE ni vigencia comercial de un alias. No se consultaron ni se afirman tarifas actuales de DeepSeek.

## Alcance de archivos

Dominio/aplicación/adaptador jobs, modelos coach, coach0002, comando administrativo, contratos fake/ORM y pruebas contables. Fuera de la lista inicial de pruebas contables, fue indispensable ajustar únicamente el inventario de `basis/bootstrap/tests/test_installation.py`: registrar AIReconciliation, cambiar total 29 → 30 y comprobar descubrimiento del comando. Sin cambio de composición en `basis/bootstrap/coach.py`.

No se modificaron training/progress, DTO/codecs/contexto/prompts de 633, propuestas de 634, plantillas, offline, seed/manage ni migraciones 0001. Integración serializada queda con coordinación.

## Entorno y barrera

VERIFIED por SQL: PostgreSQL **18.4**, base `basis_wave2_818`, usuario `basis_wave0`, endpoint `127.0.0.1:55482`. Django creó/destruyó exclusivamente `test_basis_wave2_818`; no se detuvo instancia ni se operaron otras bases. Python **3.13.7**, Django **5.2.18**, intérprete raíz:

```powershell
$python = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'
```

Runner local `.cache/mam818/run_guarded.py`: `config.test_settings`, secreto sintético, `AI_ENABLED=0`, clave DeepSeek vacía, URL exclusiva sin contraseña. Bloquea HTTPTransport/AsyncHTTPTransport reales y socket.connect/connect_ex hacia destinos distintos de 127.0.0.1; permite PostgreSQL y el sink SMTP local efímero propiedad de las pruebas. Los tests de jobs habilitan su configuración fake explícitamente. La barrera es Python en el proceso del runner; no es una política de firewall del sistema. Los procesos de concurrencia de la suite ejecutan fixtures locales.

SHA-256 del runner final local (UTF-8 con BOM): `31a8e0050cf6c3d6e3437556e4977dc11e79002e48111d7301a760a195275859`. `run_guarded_sqlite.py` difiere solo en DATABASE_URL=`sqlite:///:memory:`. Logs locales conservados en `.cache/mam818/`.

## Comandos y resultados

Ejecutados desde este worktree con el intérprete anterior y el runner descrito:

```powershell
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_installation tests.regression.test_billing_ai tests.regression.test_accounts.ReferenceSMTPTests --noinput -v 1
& $python .cache/mam818/run_guarded.py manage test --noinput -v 1
& $python .cache/mam818/run_guarded.py unittest discover -s tests_architecture -q
& $python .cache/mam818/run_guarded_sqlite.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_reconciliation --noinput -v 1
& $python .cache/mam818/run_guarded.py script scripts/architecture_check.py
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-core.ini
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-django.ini
& $python .cache/mam818/run_guarded.py script .cache/mam818/check_imports.py
& $python .cache/mam818/run_guarded.py ruff check .
& $python .cache/mam818/run_guarded.py manage check
& $python .cache/mam818/run_guarded.py manage makemigrations --check --dry-run
git diff --check
```

- **VERIFIED:** focal PostgreSQL final, **75 tests, OK, sin omisiones**, 11.647 s (`postgres-final-v2.log`). Incluye decisiones concurrentes iguales, distintas y contrapuestas paid/trial; settlement concurrente; rollback después de insertar auditoría; snapshot histórico/desconocido; restricciones e inmutabilidad; migración ida/vuelta sintética y rechazo de downgrade con auditorías.
- **VERIFIED:** suite Django completa final **904 tests, OK, cinco omisiones opt-in de navegador**, 235.039 s (`postgres-full-final.log`). Las cinco omisiones son hiking, PWA, running, trekking-820 y swimming; no son omisiones contables PostgreSQL.
- **VERIFIED:** **253 pruebas puras, OK**, 4.274 s (`pure-final-v2.log`).
- **VERIFIED:** SQLite focal **38 tests, OK, tres omisiones PostgreSQL**, 0.776 s (`sqlite-final-v2.log`).
- **VERIFIED:** mypy core **130** archivos y Django **417**; architecture_check y ocho contratos de importación, cero rotos. `check_imports.py` invoca `from importlinter.cli import lint_imports; lint_imports()`.
- **VERIFIED:** Ruff check global; Ruff format --check de los **13 archivos Python modificados no migración**; Django check; makemigrations --check --dry-run sin cambios; git diff --check.
- **VERIFIED:** self-test de la barrera: HTTP real y socket a dirección externa de documentación rechazados mediante AssertionError, antes de enviar; SQL al endpoint exclusivo permitido. Sin credenciales reales de IA.

Fallos previos corregidos, sin atribuirles éxito: fixtures de éxito sin identidad/modelo correcto y claves sintéticas reutilizadas; serialización CLI de cero `0` frente a `0E-8` normalizada a ocho decimales; import de IrreversibleError corregido a django.db.migrations.exceptions. La primera suite completa ejecutó **900 tests** y falló en inventario del nuevo modelo y en bloqueo del SMTP loopback por la barrera inicial limitada al puerto PG. Se actualizó el inventario y se permitió solo loopback; SMTP local e inventario pasan en la focal final. La invocación `-m importlinter` no tiene __main__; se usó su entrada CLI y los ocho contratos pasan.

## Operación disponible, no ejecutada contra datos existentes

`reconcile_ai_job JOB_UUID` consulta estado, snapshot y reserva. Añadir `--key CLAVE` consulta un recibo persistido y sus actor/referencia/evidencia/resultado. No expone prompt ni contexto privado.

Decisión administrativa requiere `--decision no_charge|usage --key CLAVE --actor ACTOR --reference REFERENCIA --evidence EVIDENCIA`. `no_charge` exige `--confirmed-no-charge`. `usage` exige `--reported-model MODELO --input-tokens N --output-tokens N --cache-hits N`, todos aportados desde evidencia externa. Sin `--apply` es dry-run; `--dry-run` también es explícito. `--apply` es la única vía que confirma ajustes/auditoría. Actor y evidencia son declaraciones del operador administrativo; esta implementación no verifica una factura LIVE por sí sola.

## Límites y gates conservados

- **NOT RUN:** proveedor/precios/alias LIVE, pagos, producción, aplicación/conciliación de datos existentes, endpoints a usuarios, navegadores/dispositivos físicos, CI remoto/push/PR, integración en main y revisión independiente del candidato.
- **NOT RUN / fuera de estos hallazgos:** contexto y evaluación deportiva pendientes de 633/634/635/636; P03 (lock mensual compartido), capacidad/carga y rentabilidad/margen real. Estos criterios no se recortan ni se declaran resueltos.
- Costos/snapshots desconocidos o discrepantes siguen requiriendo revisión explícita; no se inventa tarifa ni se aplica un costo arbitrario. La vía disponible conserva esos casos retenidos y deja evidencia. No hay desbloqueo automático.
- Inmutabilidad cubre operaciones ordinarias de filas y downgrade de esta migración; un administrador privilegiado capaz de quitar triggers, truncar o cambiar el esquema requiere controles operativos externos.
- La migración falla ante agregados históricos que incumplan las nuevas restricciones, en vez de corregirlos silenciosamente. Solo se probó con datos sintéticos en bases de prueba.
- MAM-818 permanece **In Progress** hasta integración y aceptación completa, incluidos sus demás criterios y evidencia LIVE pertinente. Este recibo acredita los alcances locales F03/F04/F05, no el cierre del ticket.

## Runner reproducible de esta verificación

Guardar el siguiente contenido en `.cache/mam818/run_guarded.py` permite repetir los comandos. Es infraestructura local de prueba, no una configuración de despliegue. El runner SQLite sustituye únicamente la URL por `sqlite:///:memory:`. Los auxiliares verify_guard/check_imports descritos arriba se conservan en la misma carpeta local.

```python
import os
import runpy
import socket
import sys
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
os.environ['DJANGO_SECRET_KEY'] = 'synthetic-mam818-test-only'
os.environ['AI_ENABLED'] = '0'
os.environ['DEEPSEEK_API_KEY'] = ''
os.environ['DATABASE_URL'] = 'postgresql://basis_wave0@127.0.0.1:55482/basis_wave2_818'
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
import httpx

def forbidden(*args, **kwargs):
    raise AssertionError('Real HTTP forbidden during MAM818 verification')
httpx.HTTPTransport.handle_request = forbidden
httpx.AsyncHTTPTransport.handle_async_request = forbidden
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex

def guarded_connect(self, address):
    if not isinstance(address, tuple) or address[0] != '127.0.0.1':
        raise AssertionError('External socket forbidden during MAM818 verification')
    return original_connect(self, address)

def guarded_connect_ex(self, address):
    if not isinstance(address, tuple) or address[0] != '127.0.0.1':
        raise AssertionError('External socket forbidden during MAM818 verification')
    return original_connect_ex(self, address)
socket.socket.connect = guarded_connect
socket.socket.connect_ex = guarded_connect_ex
mode = sys.argv.pop(1)
if mode == 'manage':
    runpy.run_path(str(root / 'manage.py'), run_name='__main__')
elif mode == 'script':
    path = sys.argv.pop(1)
    sys.argv[0] = path
    runpy.run_path(path, run_name='__main__')
else:
    runpy.run_module(mode, run_name='__main__')

```
