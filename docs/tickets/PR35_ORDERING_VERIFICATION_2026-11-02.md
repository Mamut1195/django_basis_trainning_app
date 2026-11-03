# PR35 — orden determinista del snapshot de planificación

El aviso automático indicó checks obligatorios aprobados sobre c9646c2, pero la lectura directa de GitHub mostró dos ejecuciones distintas: push41562693880 SUCCESS y pull_request41562700397 FAILURE/postgres. La PR continuaba BLOCKED. No se tomó el aviso como autorización de integrar un candidato fallido.

Fallo real: test_contract_definition_creates_private_prescription_without_results, planning_contract.py:31; 638 pruebas, un fallo, nueve omisiones en el CI de pull_request. El snapshot consultaba cycles y sessions sin ORDER BY y su contrato depende de un orden estable.

Se reprodujo en PostgreSQL18.4 desechable basis_pr35_order/test_basis_pr35_order: después de actualizar una fila y elegir un plan secuencial permitido (SET LOCAL enable_indexscan/enable_bitmapscan=off), los ciclos devolvieron meso/micro/macro. Al ordenar solo ciclos, la misma prueba reprodujo future/past/executed para sesiones. La primera variante sin forzar ese plan pasó; no se ocultó ese resultado. Logs locales pr35-order-red.log, pr35-order-red-sequential.log y pr35-order-red-sessions.log.

Corrección: el adaptador snapshot ordena ambas colecciones por pk, conservando el orden de creación. Sin cambios de modelos, migraciones, fórmulas o datos. La regresión mantiene las mismas expectativas bajo ese plan de consulta y comprueba ciclos y sesiones.

VERIFIED: manage.py test basis.bootstrap.tests.test_planning tests_architecture.test_planning --noinput: 29 pruebas OK, cero omisiones,1.429s en PostgreSQL18.4. Mypy Django418 archivos y Ruff check pasaron; Ruff format detectó una línea de prueba larga y se corrigió antes de repetir ese control. Configuración config.test_settings, DJANGO_SECRET_KEY sintética, AI_ENABLED=0 y DEEPSEEK_API_KEY vacía. No proveedor ni datos reales. Logs en .cache/wave2-20261102/ de la raíz; el worktree del arreglo es .cache/worktrees/pr35-orderfix.

NOT RUN localmente para el código corregido: suite completa y navegador. El CI completo de PR35 debe repetirse y aprobarse antes de integrar. Los resultados previos de c9646c2 permanecen históricos.

## MAM-1011: comprobación negativa de la política

Antes de publicar este arreglo, con PR35 todavía en c9646c2 y postgres fallido, se verificaron enforce_admins=true, strict=true, estado OPEN/BLOCKED y SHA exacto. Se intentó la integración normal por gh pr merge --merge --match-head-commit c9646c2adea13a3846e9286ab17fdf377ba1be6a, sin admin/auto ni bypass. La CLI la rechazó por política de la rama con exit1. Una lectura posterior confirmó OPEN, mergedAt=null y mismo SHA. Es evidencia de rechazo del flujo normal por la CLI, no un HTTP405 de una mutación REST enviada directamente. No se introdujo un fallo deliberado ni se gastó otra ejecución para esta comprobación.

Log local pr35-policy-negative.log; no se usaron las opciones admin/auto sugeridas por el mensaje. La aceptación positiva anterior de PR33/34 se conserva en Linear. MAM-1011 solo puede cerrarse después de incorporar este recibo a main y revisar el estado final.
