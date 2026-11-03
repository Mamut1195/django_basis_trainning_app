# Continuación — verificación de integración local

## F01/F02 sobre main con MAM-820

Base `98ea2923f6a675001bc9951f971d8a43759b58a3`; rama local `codex/basis-wave2-20261102`. El commit conservado `4a0414b` se incorporó sin conflictos como `332a0605f049bc40c4410d744d308a05050e7018`. La evidencia original permanece fechada en F01_F02_VERIFICATION_2026-11-02.md; sus resultados no sustituyen las ejecuciones siguientes.

Entorno actual: intérprete `.venv-win/Scripts/python.exe`; PostgreSQL 18.4 real consultado por SQL, instancia desechable de la tanda anterior, `127.0.0.1:55482`. Base exclusiva `basis_wave2_integration`, configuración `config.test_settings`, secreto y credencial sintéticos, AI_ENABLED=0. El runner local `.cache/wave2-20261102/run_guarded.py` bloquea transporte HTTP real y sockets Python salvo el endpoint PostgreSQL. Los tests HTTP usan transportes simulados. Sin llamadas pagadas ni datos de producción.

| Comprobación ejecutada | Resultado |
| --- | --- |
| `run_guarded.py test tests_architecture.test_coach_jobs basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges tests.regression.test_billing_ai --noinput -v 1` | VERIFIED: 65 tests, cero omisiones, 25.764 s; test_basis_wave2_integration creada/destruida. Incluye concurrencia real de liquidación paid/trial. |
| `python -m unittest discover -s tests_architecture` | VERIFIED: 237 tests, 36.572 s. |
| `python scripts/architecture_check.py` | VERIFIED: límites e inventario. |
| `python -m mypy --config-file mypy-core.ini` | VERIFIED: 130 archivos. |
| `python -m mypy --config-file mypy-django.ini` | VERIFIED: 413 archivos. |
| `lint-imports` | VERIFIED: ocho contratos, cero rotos. |
| `python -m ruff check .` | VERIFIED. |
| `python -m ruff format --check basis/modules/coach basis/bootstrap/tests/test_coach_edges.py basis/bootstrap/tests/test_coach_jobs.py tests_architecture/coach_jobs_contract.py tests_architecture/test_coach_jobs.py` | VERIFIED: 35 archivos formateados. |
| `run_guarded.py check` y `run_guarded.py makemigrations --check --dry-run` | VERIFIED: cero incidencias y sin cambios de migración. |
| `git diff --check` | VERIFIED. Tres documentos untracked preexistentes conservados, sin incorporarlos al commit. |

Logs locales: `.cache/wave2-20261102/` (f01-f02-postgres, architecture-tests, mypy-core, mypy-django, imports, django-check y migrations). El primer reinicio de la instancia tomó 5432 por omitir opciones de arranque; la conexión prevista a 55482 falló. Se detuvo exclusivamente esa instancia desechable y se reinició con `-p 55482 -h 127.0.0.1`; conexión/version y cuatro bases separadas quedaron verificadas antes de las pruebas.

Revisión independiente Sol high terminada: sin bloqueos ni regresiones identificadas por inspección estática de 332a060 contra 98ea292, incluidos locks, persistencia NOT NULL, idempotencia y rollback. No ejecutó pruebas adicionales ni contactó proveedores.

NOT RUN en este corte: suite Django completa del árbol combinado de la tanda, CI remoto, publicación/PR, imagen/operación, dispositivos y proveedores LIVE. MAM-635/818 siguen abiertos por alcance adicional y dependencias; esta corrección no resuelve tarifas versionadas, modelo reportado ni conciliación de reservas ambiguas.

## Frentes en ejecución

MAM-815 (Sol high), MAM-630 (Terra high) y MAM-632 (Terra high) ejecutan trabajo aislado desde main98ea292; las bases sintéticas autorizadas son respectivamente basis_wave2_815, basis_wave2_630 y basis_wave2_632. No se afirma terminación ni integración de sus resultados en este corte.

El primer lote MAM-630 (`7bf307d`) se revisó e incorporó localmente como `fb9c17e`: enlaces a historiales, error de rango y Cache-Control privado/no-store en exportación. Sus 84 pruebas PostgreSQL pertenecen a la ejecución del subagente; la suite combinada aún no se ejecutó. Terra continúa gráficos y aceptación visual/accesible. Se abrió además MAM-818 F03/F04/F05 con Sol high aislado desde fb9c17e y base exclusiva basis_wave2_818; ningún resultado de ese frente se afirma todavía.
