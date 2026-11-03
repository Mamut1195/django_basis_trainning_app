# MAM-818 R4: barrera durable del intento

Base `463dc93e1ae050c2d0c4c558ef53dbf63715ae34`, que conserva la reproducción roja. Candidato local pendiente de revisión independiente e integración; no cierra MAM-818.

## Política y comportamiento

Claim genera y persiste un UUID de intento en la misma transacción que `running`, antes de cualquier llamada al proveedor. Cuarentena no lo elimina. `settle` ordinario, o con otro identificador, no cierra ni ajusta un intento abierto. `process_one` entrega el identificador al settlement al retornar o lanzar el intento; bajo orden fondo → cuenta → job → período, este guarda la evidencia y cierra la barrera en la misma transacción. El UUID es una identidad de coordinación interna, no autenticación frente a un actor con acceso de escritura a la base.

Mientras la barrera esté abierta, reconcile con `--apply` registra `retained` append-only e idempotente; dry-run devuelve el mismo resultado sin persistir, conforme al contrato previo. Una respuesta tras cuarentena conserva modelo y conteos representables o la marca irreversible de invalidez, sin aplicar propuesta ni ajustar saldos automáticamente. El retorno ambiguo o definitivo también cierra su propio intento; la ausencia de uso no inventa invalidez. Tras el cierre, otra clave de conciliación sigue las reglas de evidencia existentes; replay de un recibo anterior devuelve ese recibo sin reinterpretarlo.

La migración 0003 cerca conservadoramente todos los `running` y `uncertain` históricos, incluso si alguno no llegó a despacharse; no los declara muertos. Rechaza downgrade si existe una barrera abierta. Un worker muerto sin cierre deja la reserva retenida indefinidamente: no existe liberación ni desbloqueo automático. Para un despliegue futuro se requiere detener y cercar procesos con código anterior antes de migrar y habilitar workers nuevos: el código anterior no conoce ni respeta esta barrera. La migración y las pruebas aquí se realizaron solo en bases sintéticas, no en producción.

## Evidencia

La reproducción RED previa, decoder → DeepSeekProvider → worker → ORM con MockTransport y PostgreSQL, tiene dos pruebas y tres fallos en `review4-red-final.log`: liberación antes de retorno y pérdida de marca después de cuarentena. SHA256 `FE58E02A050302E2AF8ADE47711B59FA52839050CBB80ABCA5676815CAA1DD12`. Las mismas pruebas pasan en la focal nueva.

La matriz nueva usa paid/trial × respuesta válida/inválida × conciliación antes/después × no_charge/usage; comprueba dry-run, recibos, replay, segundo settlement, falta de reenvío y saldos. En el orden anterior al retorno usa una segunda clave después del cierre para comprobar la política de evidencia, sin reescribir el primer recibo. Se adelanta 45 días y se comprueba fondo original y fondo posterior. Otra prueba confirma que un plan tardío válido no crea propuesta. Se cubren falta de usage, timeout ambiguo y rechazo definitivo, y rollback de barrera, marca y bloqueo. Migración prueba estado histórico y rechazo de downgrade. En ambos órdenes, pruebas con dos hilos y transacciones PostgreSQL verifican mediante `pg_blocking_pids` el backend preciso que bloquea el otro; no se retiene transacción durante HTTP.

Entorno verificado: PostgreSQL 18.4, `basis_wave2_818`, usuario `basis_wave0`, puerto 55482; Django creó y destruyó solo `test_basis_wave2_818`. Python del `.venv-win` del checkout raíz, ejecutado desde este worktree. `run_guarded.py` SHA256 `31A8E0050CF6C3D6E3437556E4977DC11E79002E48111D7301A760A195275859`: settings de prueba, secreto sintético, AI deshabilitada salvo fixture, transporte real y sockets externos denegados. `r4-guard.log` confirma ambos bloqueos.

Comandos, con `$python = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'` y `$runner = '.cache/mam818/run_guarded.py'`:

```powershell
& $python $runner manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_coach_attempt_fence --noinput -v 1
& $python $runner unittest discover -s tests_architecture -q
& $python .cache/mam818/run_guarded_sqlite.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_attempt_fence --noinput -v 1
& $python $runner mypy --config-file mypy-core.ini
& $python $runner mypy --config-file mypy-django.ini
& $python $runner script scripts/architecture_check.py
& $python $runner script .cache/mam818/check_imports.py
& $python $runner ruff check .
& $python $runner manage check
& $python $runner manage makemigrations --check --dry-run
& $python $runner script .cache/mam818/verify_guard.py
& $python $runner manage test --noinput -v 1
git diff --check
```

**VERIFIED:** focal PG 84 OK sin omisiones (`r4-pg-verified.log`, SHA256 `141C85CBACA967E76FEF205E3FDB3C26F850BA1919A199614D2B174921D0B028`); focal específica ambos órdenes siete pruebas OK (`r4-fence-both-orders.log`, `86DC6B098D089AC7AF0F816815FBA1DE811F8CDFCE5AB717BE0B0A0944DD8D3C`); puras 258 OK (`r4-pure.log`, `88200096EE336D309BA98AE49F11D662C2C463AA8B46E7E96914C7676E074C0F`); SQLite 58 OK con nueve omisiones por funcionalidades PG (`r4-sqlite.log`, `D3CB23C6BB05C61C2DBB2F627C706AEBE6269251713C45A54FC18185C1E868CA`; anterior a la última prueba adicional PG-only); mypy core 130 y Django 420 archivos (`r4-mypy-core.log`, `60C30A1059D61F00EC111C60094A5492DAAF54FC52EC25987859433A1DE43EAD`; `r4-mypy-django-verified.log`, `F86CE68FF5F5B52E32AEB7ACA9E316E49CFCFA6CF230FD2C45205410ECD68245`); arquitectura e imports ocho contratos, Ruff global y formato de diez archivos, Django check, migraciones sin cambios y guard de red. Los logs residen en `.cache/mam818/`, fuera del commit.

**VERIFIED:** suite Django completa 938 OK, cinco omisiones, 333.032 s (`r4-full.log`, SHA256 `98F3ED307AC4661DE4BC5DA8B996010D0B2EEBA1DCB927ADD158A71569775BAE`). La salida `-v 1` no identifica los nombres de esas omisiones.

Otros SHA256: `r4-architecture.log` `AA0841E62B8D2CF1F5A822AA375FEF31621B67DDE03E9C10FCDE11F97DD2A4B6`; `r4-imports.log` `FDF1A6F15AE4AFE0D5CD1ADE43A4FFD3279861D100186C93F491024D98B2A48E`; `r4-guard.log` `B9ACDA7E63E456ED765A5A0876A7C43CF0C084586869225E214B0E4349EC6FAB`; `r4-check.log` `569740892270A412C02F5021E0703ECAAFDC8A409E03320C9BDAC90BB6558F0B`; `r4-migrations.log` `B2B37BBB238BC60F5FC324FB0A247DB27A287DF18CDEC79272AA733487AA5FD7`; `r4-ruff-verified.log` `AF352A86840AD0AF3D37EA0D9197F868363A6DAC6B1C2EF5D2722F6B41D2D9AF`.

**FAILED y recuperado:** una repetición de focal (`r4-pg-final2.log`, SHA256 `23A472AF3479422100B2DB2B21506746F5BD2C52A5031A01AAA98774F1255453`) tuvo un timeout al abrir conexión PostgreSQL antes de un subcaso; no se conoce su causa. El puerto respondió posteriormente, la focal específica y la focal final se ejecutaron de nuevo con éxito. No se detuvo ni reinició el servidor compartido.

**NOT RUN:** revisión independiente nueva, integración, CI remoto, push, Linear, proveedor/precios LIVE, pagos, producción, conciliación de datos existentes, despliegue con versiones mezcladas y capacidad de 1000 usuarios.
