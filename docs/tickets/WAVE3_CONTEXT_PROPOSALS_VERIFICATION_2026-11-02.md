# Integración local de contexto y propuestas

Árbol funcional probado: **5cb9498294655b769b948a4639909a4b7d843dd0**, rama codex/basis-wave3-20261102, sobre main ca87ebe. Se incorporaron por separado los cuatro commits633 y los cinco commits propios634; no se duplicaron los cherry-picks de sus dependencias. El comentario obsoleto de anchors señalado como P3 fue corregido, sin cambio funcional. Los tres documentos untracked preexistentes siguen separados.

Las segundas revisiones independientes cerraron las objeciones propias633 y634, con los límites registrados en sus matrices. La revisión633 comprobó ocho pruebas puras y codec/fechas, además de los hashes de logs del ejecutor; no repitió PostgreSQL. La revisión634 comprobó catorce pruebas puras y siete reproducciones en memoria; tampoco repitió PostgreSQL o navegador. Las pruebas PG y UI de los ejecutores no se atribuyen a los reviewers ni a coordinación.

## Ejecuciones de coordinación sobre árbol estable

Intérprete .venv-win/Scripts/python.exe; PostgreSQL18.4 real en127.0.0.1:55482, base exclusiva basis_wave3_integration y su test_ creada/destruida por Django. config.test_settings, DJANGO_SECRET_KEY sintética, AI_ENABLED=0, credencial sintética y runner local que impide HTTP externo y admite sockets loopback. No proveedores, pagos o datos reales.

- VERIFIED: focal conjunta de contexto, locks, correcciones633, propuestas/RM/no-finitos634, jobs/edges y planning: **105 pruebas OK**, cero omisiones,35.499s. Incluye órdenes concurrentes reales con espera en cuenta y terminación sin ciclos.
- VERIFIED: suite equivalente a checks.yml: **704 pruebas OK con9 omisiones**,350.075s. El HEAD y los archivos rastreados se mantuvieron estables durante la ejecución.
- VERIFIED: **257 pruebas puras**,5.363s; checker de arquitectura; ocho contratos Import Linter, cero rotos.
- VERIFIED: mypy core133/Django424 archivos; Ruff global, Ruff format435 archivos y djLint de basis sin cambios pendientes.
- VERIFIED: git diff --check y preservación del trabajo ajeno por propiedad de archivos e índice acotado.

Comando focal: `python .cache/wave3-20261102/run_guarded.py test tests.regression.test_coach_context_633 tests.regression.test_coach_context_locks_633 tests.regression.test_coach_context_review_633 basis.bootstrap.tests.test_mam634_proposals basis.bootstrap.tests.test_mam634_rm_provenance basis.bootstrap.tests.test_mam634_review_regressions basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_planning --noinput -v 1`.

Comando completo: `python .cache/wave3-20261102/run_guarded.py test tests.regression basis.bootstrap.tests basis.modules.billing.adapters.test_persistence basis.modules.billing.adapters.test_polar basis.modules.training.adapters.test_metrics basis.modules.training.adapters.test_player basis.modules.sync.adapters.test_wire --noinput`.

Logs conservados en .cache/wave3-20261102/: context-proposals-combined.log, source-proposals-full-5cb9498.log, core/django/pure/architecture/imports/format/djlint-5cb9498.log. Los fallos y fixes previos están en las matrices633/634 y no se reetiquetan como éxitos retroactivos.

## Gates que no cubre esta verificación

818 continúa aislado. Su tercera revisión encontró pérdida de evidencia en el decoder antes de la marca durable; fa4f2ef y recibo12ab729 corrigen esa frontera y están en cuarta revisión. Sus pruebas no forman parte de704. El turno previo de Sol terminó por capacidad; coordinación recuperó solo el recibo/logs del commit129ff4c sin fingir éxito de la orquestación. La integración posterior de provider.py y contratos requerirá sus propias pruebas.

635 abrió aceptación independiente de UI/tareas con base5cb9498, sin propiedad sobre cuotas/jobs818; cualquier cancelación/control faltante deberá coordinarse antes de editar esos contratos.636 tiene corpus preparado, no evaluación ejecutada. Integración/main y CI remoto de esta tanda, proveedor LIVE, lector de pantalla/dispositivos físicos, calidad deportiva y producción: NOT RUN. La autorización anterior de Actions cubría PR35, no estos cambios posteriores.
