# MAM-818 — F03/F04/F05, verificación local 2026-11-02

## Continuación tras tercera revisión: uso inválido en frontera JSON

Base documental limpia `1639fd6d8fbb301aaed8a959b7dfe6d055fffd86`, código previo `129ff4c8d8c9bfdb9fa34f3b0debddf6bf16eabc`. Plan específico escrito antes de editar pruebas y código en el plan 818. Código y plan de esta ronda: `fa4f2ef2cabaccb028194e4936e5acc0d0350d5c`. No se reescribieron commits ni se modificó el checkout padre.

### Red → green y alcance

- **FAILED antes del fix:** contrato desde `decode_reply` hasta settlement y reconcile en fake y PostgreSQL: 32 subcasos fallaron por `released` frente a `retained`; hubo además 10 errores por reutilización de la clave de prueba, corregida antes de la pasada verde. Logs `review3-red-fake.log` y `review3-red-pg.log`. Las decisiones fueron sintéticas.
- **FAILED antes del fix:** worker real con `DeepSeekProvider`, `httpx.MockTransport` y ORM recibió `prompt_tokens=10**40` con `completion_tokens=false`; la conciliación no_charge devolvió `released` en vez de `retained` (`review3-red-worker.log`). No hubo HTTP real.
- **VERIFIED tras el fix:** el decoder marca explícitamente uso presente malformado, incluidos campos obligatorios ausentes, objeto no válido y tipos bool/string/null/float/lista para cada conteo. La ausencia completa de `usage` y JSON superior no objeto permanecen sin observación inventada; el campo opcional de cache ausente mantiene su comportamiento anterior. Settlement persiste True en la marca irreversible existente aun si `usage=None`; conciliaciones no_charge y uso pequeño producen recibos retained idempotentes, sin reenviar ni alterar reserva/gasto paid/trial. El worker conserva el bloqueo existente y deja el siguiente trabajo pendiente.
- La marca conserva únicamente el hecho de que hubo uso inválido, no el contenido ni qué campo falló. Cuando el decoder no puede tipar el conjunto, omite todos los conteos de las columnas enteras, incluso los que individualmente parecían válidos o eran demasiado grandes; no calcula costo. La historia desconocida sigue siendo None y no se reconstruye. Las pruebas compartidas fake/ORM comprueban columnas omitidas, fondos, auditoría, replay y no reenvío.

### Comandos y resultados de esta ronda

Desde el worktree, `$python = 'C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe'`; runner `.cache/mam818/run_guarded.py` conservado, config.test_settings, secreto sintético, AI_ENABLED=0, base `basis_wave2_818` y solo `test_basis_wave2_818` temporal. Barrera HTTP y sockets externos verificada (`review3-guard.log`).

```powershell
& $python .cache/mam818/run_guarded.py unittest tests_architecture.test_coach_jobs.JobsTests.test_contract_decoded_malformed_usage_retains_evidence_and_reservations -q # red
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs.DjangoJobsTests.test_contract_decoded_malformed_usage_retains_evidence_and_reservations --noinput -v 1 # red
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_provider_policy.FrozenProviderPolicyTests.test_worker_decodes_mixed_invalid_usage_and_reconciliation_retains_it --noinput -v 1 # red
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration --noinput -v 1
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs.DjangoJobsTests.test_contract_decoded_malformed_usage_retains_evidence_and_reservations basis.bootstrap.tests.test_coach_jobs.DjangoJobsTests.test_contract_missing_usage_does_not_invent_historical_observation basis.bootstrap.tests.test_coach_jobs.DjangoJobsTests.test_contract_worker_decodes_malformed_usage_without_resending basis.bootstrap.tests.test_coach_provider_policy.FrozenProviderPolicyTests.test_worker_decodes_mixed_invalid_usage_and_reconciliation_retains_it --noinput -v 1
& $python .cache/mam818/run_guarded.py unittest discover -s tests_architecture -q
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-core.ini
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-django.ini
& $python .cache/mam818/run_guarded.py script scripts/architecture_check.py
& $python .cache/mam818/run_guarded.py script .cache/mam818/check_imports.py
& $python .cache/mam818/run_guarded.py ruff check .
& $python .cache/mam818/run_guarded.py ruff format --check basis/modules/coach/adapters/provider.py basis/modules/coach/application/jobs.py basis/modules/coach/domain/jobs.py basis/bootstrap/tests/test_coach_provider_policy.py tests_architecture/coach_jobs_contract.py
& $python .cache/mam818/run_guarded.py manage check
& $python .cache/mam818/run_guarded.py manage makemigrations --check --dry-run
& $python .cache/mam818/run_guarded.py script .cache/mam818/verify_guard.py
git diff --check
```

**VERIFIED:** focal PG 75 pruebas OK, sin omisiones (`review3-pg.log`); posteriormente se añadieron solo aserciones sobre columnas y anotaciones de tipos, y la focal de cuatro pruebas de regresión volvió a pasar (`review3-focused.log`). Puras 258 OK (`review3-pure-final.log`); mypy core 130 y Django 418, arquitectura e imports ocho contratos, Ruff, formato, Django check y migraciones sin cambios. Mypy falló inicialmente por tres anotaciones de la prueba nueva, corregidas sin suprimir errores. Los logs locales están en `.cache/mam818/` y no forman parte del commit.

**NOT RUN:** suite completa en este candidato (coordinación ejecutará la integrada), revisión independiente nueva, integración, CI remoto, push, Linear, proveedor/precios LIVE, pagos, producción y conciliación de datos existentes. Este fix es un candidato local, no aprobación de integración ni cierre de MAM-818.

## Correcciones tras segunda revisión de 216d54f

Base `cd9fa8829ced9ffd72bf5433212d1b3afd707f02`, commits anteriores preservados, código aún no integrado. Commit correctivo de esta ronda: `129ff4c8d8c9bfdb9fa34f3b0debddf6bf16eabc`. Suite completa nueva: 922 pruebas OK, cinco omisiones. El transporte congelado aprobado en la segunda revisión no se modifica; tampoco source codec/contexto/prompts 633 ni guard/bootstrap 634.

El turno terminó con error de capacidad del modelo antes de guardar este recibo. Coordinación recuperó el documento pendiente y leyó los logs del ejecutor: focal estable91, puras255 y suite completa922/5 en274.714s. No son reejecuciones de coordinación. SHA256 de review2-full.log: 46586CB06361C116F7C921AD97381FDD6D419D8994379E74B556518AB9F73580. Los archivos Python del correctivo se habían escrito antes de iniciar esa suite; el único cambio sin commit recuperado era este recibo. Se conserva el error terminal de orquestación y no se presenta como una respuesta final exitosa del subagente.

### Reproducciones propias anteriores al fix

- **FAILED**, `review2-repro-fake.log`: una prueba compartida, **12 subcasos fallidos**, paid/trial × entrada/salida/cache 10**40 × no_charge/uso pequeño. Tras settlement uncertain, el conteo excedente se proyectaba como None; la conciliación liberaba la reserva o cargaba **0.00000030 USD sintéticos** con uso (1,0,0), contradiciendo la respuesta recibida.
- **FAILED**, `review2-repro-pg.log`: tres pruebas, **14 fallos**: los mismos doce subcasos con ORM PostgreSQL y downgrade permitido para límites 4000.0 y 1500.0. Python dict equality equiparaba float/int y la reaplicación cambiaba la política de inválida a válida. Todo ocurrió con datos sintéticos en test_basis_wave2_818, sin bases existentes ni HTTP real.

### Correcciones y compatibilidad

- `Job.invalid_usage_observed` y la columna nullable homónima distinguen una observación inválida conocida (**True**) de historia/ausencia no reconstruida (**None**). Los flujos nuevos comienzan False (sin invalidez conocida). Settlement marca True antes de descartar de la proyección Integer cualquier valor no representable y también ante rechazo contable de los conteos. La marca se guarda con estado y observaciones en la misma UoW; no se finge que la columna limitada conserva el entero enorme.
- La marca True es persistente y no borrable: guards PostgreSQL/SQLite impiden pasarla a False/NULL, incluso mediante bulk update; el fake respeta el mismo carácter irreversible. Conciliación de cualquier decisión y liberación contable rechazan esa evidencia conocida, conservan uncertain, reserva y gasto, y generan retained/cost=NULL auditado e idempotente. No hay endpoint ni vía de borrado de marca.
- Los jobs anteriores a 0002 reciben **None**, no una observación inventada. None expresa desconocimiento, no prueba de conteos válidos. Se mantienen sus observaciones seguras previas y las reglas de conciliación con evidencia explícita; un entero que ya se perdió en una versión anterior no se reconstruye ni se declara conocido. Esta entrega no concilia ni reclasifica datos existentes.
- La guarda de downgrade compara JSON canónico sensible a representaciones/tipos relevantes: distingue int/float y bool/int, conservando el orden significativo de arrays e ignorando solo el orden de claves. El trigger de snapshot PostgreSQL compara representación textual de jsonb, para impedir también que una actualización convierta 4000 en 4000.0 pese a igualdad numérica. Se rechaza downgrade antes de retirar triggers ante cualquiera de esas diferencias, auditorías o marca no NULL, que tampoco puede reconstruirse desde 0001.
- Pruebas compartidas fake/ORM: settlement previo real con cada campo enorme, paid/trial, ambas decisiones contradictorias y replay; rollback después de escribir marca y después de insertar recibo retained. Pruebas PG de tres participantes: settlement inválido contra decisiones repetidas o diferentes, sin liberación ni cargo y con marca durable. Pruebas de almacenamiento/CLI verifican visibilidad de marca y bloqueo de borrado; las de migración verifican snapshot tipado intacto, escritura todavía rechazada por el trigger y ambos triggers todavía instalados tras fallar downgrade. La ida/vuelta histórica conserva también NULL de la nueva marca.

### Verificación exclusiva del árbol de esta ronda

Mismo runner reproducible sin cambios: Python raíz 3.13.7, config.test_settings, secreto sintético, AI_ENABLED=0, PostgreSQL 18.4; solo test_basis_wave2_818 creado/destruido. HTTP real y sockets externos bloqueados. No se alteraron 0001 ni el servidor PostgreSQL.

```powershell
& $python .cache/mam818/run_guarded.py unittest tests_architecture.test_coach_jobs.JobsTests.test_contract_settlement_huge_counts_cannot_be_reinterpreted_as_absent -v
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs.DjangoJobsTests.test_contract_settlement_huge_counts_cannot_be_reinterpreted_as_absent basis.bootstrap.tests.test_coach_pricing_migration.HistoricalPricingMigrationTests.test_downgrade_cannot_change_float_input_limit_into_int basis.bootstrap.tests.test_coach_pricing_migration.HistoricalPricingMigrationTests.test_downgrade_cannot_change_float_output_limit_into_int --noinput -v 1
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_installation tests.regression.test_billing_ai tests.regression.test_accounts.ReferenceSMTPTests --noinput -v 1
& $python .cache/mam818/run_guarded.py unittest discover -s tests_architecture -q
& $python .cache/mam818/run_guarded_sqlite.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation --noinput -v 1
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-core.ini
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-django.ini
& $python .cache/mam818/run_guarded.py script scripts/architecture_check.py
& $python .cache/mam818/run_guarded.py script .cache/mam818/check_imports.py
& $python .cache/mam818/run_guarded.py ruff check .
& $python .cache/mam818/run_guarded.py manage check
& $python .cache/mam818/run_guarded.py manage makemigrations --check --dry-run
& $python .cache/mam818/run_guarded.py script .cache/mam818/verify_guard.py
& $python .cache/mam818/run_guarded.py manage test --noinput -v 1
git diff --check
```

Las primeras dos órdenes corresponden a las reproducciones rojas previas, no a un resultado verde atribuido retroactivamente. Gates nuevos:

- **VERIFIED:** focal estable **91 tests PostgreSQL, OK, cero omisiones**, 19.343 s (`review2-focal-stable.log`). La pasada previa de 91 también fue verde; después solo se reforzó la prueba de trigger con un valor de longitud legal y la comparación histórica de la nueva marca.
- **VERIFIED:** **255 pruebas puras, OK**, 4.991 s (`review2-pure.log`).
- **VERIFIED:** SQLite **47 tests, OK**, cuatro omisiones PG, 1.337 s (`review2-sqlite.log`).
- **VERIFIED:** mypy core 130 / Django 418; architecture_check y ocho contratos import, cero rotos; Ruff global y format --check de diez fuentes/pruebas no migración; Django check y makemigrations --check --dry-run sin cambios; diff sin errores. Barrera HTTP/sockets probada nuevamente.
- **VERIFIED por log del ejecutor recuperado:** suite completa nueva, 922 pruebas OK con cinco omisiones, 274.714s (`review2-full.log`), lanzada tras focal estable91 verde. Pendiente verificación del conjunto integrado por coordinación.

**NOT RUN:** tercera revisión independiente nueva, integración/main, CI remoto/push/PR, producción, pagos/proveedor LIVE y conciliación de bases existentes. MAM-818 sigue abierto, incluidos contexto/evaluación deportiva, P03, capacidad y demás gates originales. Los recibos anteriores que siguen son históricos y no sustituyen esta verificación.

---

## Correcciones tras revisión independiente de 8db5360

Base de esta continuación: `a2b596fc37286f1083fc4461c4cc6de01dd4a135`, preservando todos los commits anteriores. Plan ampliado antes de editar implementación. Commit correctivo: `216d54fabb7d5f7f4eadb468120c086eba250e1f`. Suite completa de esta continuación: VERIFIED, 911 tests con cinco omisiones de navegador opt-in. El commit documental posterior no cambia código ni pruebas.

La revisión encontró tres defectos reales en 8db5360. Los resultados del recibo inicial conservado más abajo pertenecen a aquel árbol y **no acreditan** estas correcciones. No se integró código en main ni se reutilizó una revisión histórica como aprobación del nuevo candidato.

### Reproducción antes de corregir

- `review-repro-domain.log`: **FAILED**, una prueba; `input_tokens=10**40` escapó con `decimal.InvalidOperation` durante quantize.
- `review-repro-postgres.log`: **FAILED**, cinco pruebas nuevas, cuatro fallos y un error. Enqueue aceptaba un byte sobre el presupuesto congelado; MockTransport recibió max_tokens=1500 con una reserva limitada a 100; cambiar LIMITS global a (1,1) impidió enviar el job válido reservado; downgrade no rechazó snapshot nuevo sin auditorías; CLI de uso enorme escapó con InvalidOperation en lugar de registrar retained.
- La reproducción usó exclusivamente datos sintéticos, la base de pruebas exclusiva y MockTransport. Ninguna llamada HTTP real ni conciliación de datos existentes.

### Cambios correctivos

- **P1 / transporte:** PricingSnapshot es parámetro obligatorio de Provider.prepare/call y del adaptador request_body. Enqueue pasa exactamente el snapshot reservado; el worker vuelve a validar el snapshot persistido y lo pasa al proveedor. max_tokens usa output_limit y la cota conservadora UTF-8 (bytes serializados + margen de 128) usa input_limit de ese snapshot. No es una medición LIVE ni un tokenizer. provider.py deja de leer LIMITS global. Tres pruebas enqueue → worker → MockTransport verifican max_tokens=100, la frontera exacta de bytes, rollback al excederla y cambios de política/globales entre reserva y envío. La fachada legacy actions.request_body conserva únicamente su preview con política histórica explícita; no participa en dispatch durable.
- **P2 / downgrade:** 0002 fija un único constructor de política histórica y compara el JSON completo de cada snapshot con lo que reconstruiría al reaplicar la migración. Rechaza snapshots nuevos, representaciones JSON distintas aunque las tasas sean numéricamente equivalentes y NULL que se convertiría en política identificada. Rechaza también toda auditoría existente. PostgreSQL toma locks exclusivos de job y auditoría durante comprobación/reversión, evitando una escritura entre el control y el cambio de esquema. Se conserva la prueba de ida/vuelta histórica y se amplía para comparar exactamente snapshots, versiones, costos, reservas y estados; tres nuevas pruebas sin auditorías acreditan los rechazos sin perder datos.
- **P2 / uso enorme:** usage_cost valida tipos, signo, cache y límites de entrada/salida **antes** de multiplicar o cuantizar. La conciliación registra retained/cost=NULL y conserva la reserva y saldos para 10**40. Contrato fake/ORM ampliado para entrada, salida y cache enormes con replay idempotente; CLI verifica un único recibo durable con el valor original y sin mutar el job.
- Sin cambios de contexto/codec/prompts 633, propuestas/bootstrap 634, migraciones 0001 ni datos existentes. Extensión autorizada limitada a provider.py, puerto/fakes, fachada de preview y pruebas pertinentes.

### Verificación del candidato corregido

Mismo intérprete raíz, config.test_settings, AI_ENABLED=0, secreto sintético, HTTP real y sockets externos bloqueados. Base `basis_wave2_818`, solo test `test_basis_wave2_818`; PostgreSQL 18.4. No se detuvo instancia ni se operaron otras bases.

```powershell
& $python .cache/mam818/run_guarded.py unittest tests_architecture.test_coach_jobs.JobsTests.test_invalid_token_values_cannot_be_billed -v
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation.ReconciliationCommandTests.test_enormous_usage_is_retained_audited_and_idempotent_in_cli basis.bootstrap.tests.test_coach_pricing_migration.HistoricalPricingMigrationTests.test_downgrade_preserves_unreconstructible_snapshot_even_without_audit --noinput -v 2
& $python .cache/mam818/run_guarded.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_installation tests.regression.test_billing_ai tests.regression.test_accounts.ReferenceSMTPTests --noinput -v 1
& $python .cache/mam818/run_guarded.py unittest discover -s tests_architecture -q
& $python .cache/mam818/run_guarded_sqlite.py manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation --noinput -v 1
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-core.ini
& $python .cache/mam818/run_guarded.py mypy --config-file mypy-django.ini
& $python .cache/mam818/run_guarded.py script scripts/architecture_check.py
& $python .cache/mam818/run_guarded.py script .cache/mam818/check_imports.py
& $python .cache/mam818/run_guarded.py ruff check .
& $python .cache/mam818/run_guarded.py manage check
& $python .cache/mam818/run_guarded.py manage makemigrations --check --dry-run
& $python .cache/mam818/run_guarded.py script .cache/mam818/verify_guard.py
& $python .cache/mam818/run_guarded.py manage test --noinput -v 1
git diff --check
```

Las primeras dos órdenes documentan la reproducción roja anterior a la corrección; no se declaran verdes retroactivamente. Los comandos restantes corresponden al candidato corregido:

- **VERIFIED:** focal PostgreSQL **82 tests, OK, cero omisiones**, 16.337 s (`review-focal-final.log`). Focal anterior de 75 ampliada, sin retirar assertions. Una primera pasada de 80 también pasó antes de agregar los dos casos adicionales de exactitud JSON/NULL.
- **VERIFIED:** puras **253 tests, OK**, 3.805 s (`review-pure.log`); se ampliaron casos de uso enorme en tests existentes.
- **VERIFIED:** SQLite focal **42 tests, OK**, tres omisiones de concurrencia PG, 0.943 s (`review-sqlite.log`).
- **VERIFIED:** mypy core 130 archivos, Django 418; arquitectura y ocho contratos de importación, cero rotos; Ruff check global y format --check de diez fuentes/pruebas modificadas no migración; Django check y ausencia de migraciones pendientes; git diff --check. Mypy detectó inicialmente JSONField opcional indexado sin estrechar tipo en la nueva prueba CLI; corregido con comprobación explícita de dict, sin suprimir errores ni retirar assertions.
- **VERIFIED:** barrera HTTP/sockets externos comprobada nuevamente; proveedor usa MockTransport. Runner y su bloque Python reproducible permanecen sin cambios.
- **VERIFIED:** suite completa nueva **911 tests, OK**, cinco omisiones de navegador opt-in, 261.847 s (`review-full.log`); iniciada únicamente después de focal 82 verde y árbol estabilizado. Sin omisiones contables PostgreSQL. Corresponde a las fuentes de `216d54f`, no a las de 8db5360.

**NOT RUN:** nueva revisión independiente del candidato, integración en main, CI remoto/push/PR, producción, proveedor/precios/alias LIVE y conciliación de datos existentes. La próxima revisión será una delegación nueva bajo coordinación. MAM-818 sigue abierto por estos gates y los demás criterios conservados; estas correcciones no resuelven contexto/evaluación deportiva, P03 ni capacidad.

---

Las secciones siguientes conservan el recibo original de 8db5360 y sus resultados históricos.

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
