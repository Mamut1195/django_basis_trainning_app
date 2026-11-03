# MAM-635: integración parcial de coordinación

**VERIFIED** sobre árbol funcional13b2b9c, con fuente633/634 ya integrada y sin ledger818: commits propios del ejecutor36d6968fa757f9c8dd1e0f4b2e424b483121376f y e76c50fbc0d02224694ee0aa763b731264867d47 incorporados como8718f94 y13b2b9c. Coordinación revisó el diff: prueba/recibo y16 líneas de template de consumo; no cambian jobs, contratos ni contabilidad.

- PostgreSQL18.4, base exclusiva basis_wave3_integration/test_basis_wave3_integration: **10 pruebas OK, cero omisiones,3.218s**. Comando: `.venv-win/Scripts/python.exe .cache/wave3-20261102/run_guarded.py test basis.bootstrap.tests.test_mam635_acceptance --noinput -v 1`. Log `.cache/wave3-20261102/acceptance635-integrated.log`.
- Mypy Django focal: un archivo sin errores. Ruff check y format de la prueba: satisfactorios. DjLint lint/check de coach/jobs/_result.html: cero errores y cero cambios. git diff --check satisfactorio.
- Configuración sintética; HTTP real denegado por runner, worker real con MockTransport. No proveedor LIVE ni datos reales.

Las pruebas verifican consulta/recuperación sin segundo enqueue, propiedad404, fallo ambiguo sin reenvío, entrenamiento manual disponible, cuarentena, límite, propuesta inválida, aceptación/descarte, adaptación que preserva historial y consumo que distingue costo desconocido de cero. No acreditan tarifas o conciliación818.

El navegador390×844/1280×800, teclado e interrupción/reinicio del servidor pertenecen al ejecutor y su recibo MAM635_ACCEPTANCE_2026-11-02.md; coordinación no repitió navegador. La prueba de caída del servidor no fue modo avión ni dispositivo físico.

**PENDING**: aviso local de fallo de polling y desaparición tras recuperación, delegado al mismo ejecutor; cancelación pendiente conforme al contrato propio; integración con ledger818 después de corregir y revisar su barrera de intento. Suite completa de este conjunto, CI remoto, IA/pagos LIVE, lector de pantalla y dispositivos físicos: **NOT RUN**. MAM-635 continúa parcial y abierto.

La candidata633/634 en codex/basis-context-proposals-20261102 permanece exactamente en f42b86160c0afe3a545488fd07f0e5dd8a61a15f; no contiene estos cambios635. Publicación/Actions todavía esperan respuesta a la solicitud de autorización. Los tres documentos untracked ajenos se preservan sin añadir al índice.

## Integración del aviso de actualización

Se revisó e incorporó `d74b8e8d215c3d15c20fd43b21fe5d88e56d69b8` como `fff3a4197b7449b22d1f9d633ab65c36b61a2a3f`. El aviso permanece fuera del fragmento reemplazado por HTMX, conserva el último resultado ante fallos de polling y se limpia tras un swap exitoso. Los errores HTTP de ese fragmento no duplican el aviso global; los demás conservan su comportamiento. No cambia jobs, ledger ni el indicador de Internet.

Coordinación repitió sobre la integración: focal PostgreSQL mediante `run_guarded.py` (**10 pruebas, cero omisiones, 2.916 s**), mypy Django focal, Ruff check/format, djLint lint/check del detalle, `node --check`, Prettier local del JS y `git diff 3bfc17a..HEAD --check`. Todos satisfactorios. Prettier estaba disponible en este checkout; su ausencia en el worktree del ejecutor no aplica a esta comprobación.

El proceso de pruebas terminó con código 0. Después del `OK`, la destrucción de la base temporal esperó un checkpoint de PostgreSQL: `DROP DATABASE "test_basis_wave3_integration"`, estado `IPC/CheckpointDone`, sin sesiones bloqueantes. La espera terminó sin intervención sobre procesos o sesiones ajenas.

El navegador y los ensayos de interrupción/reinicio en 390×844 y 1280×800 son evidencia del ejecutor, descrita en el recibo de aceptación; coordinación no los repitió. Timeout y error HTTP se ensayaron allí mediante eventos sintéticos. Suite completa, CI remoto, proveedor LIVE, dispositivo físico, modo avión, lector de pantalla e integración con MAM-818: **NOT RUN** en esta continuación.

El aviso ya no está pendiente. Cancelación y ledger818 siguen pendientes; MAM-635 permanece parcial y abierto. La candidata633/634 continúa en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`; los tres documentos untracked ajenos se conservan.

## Continuación: compatibilidad con MAM-818

MAM-818 se incorporó después de la aprobación independiente R7; el candidato funcional integrado es `cecea65419dd5e9782805b39e6b317a207a0107c`. Coordinación verificó la focal que incluye estas diez pruebas de aceptación y luego la suite completa: 1.047 casos, 1.038 satisfactorios y nueve omisiones optativas de navegador. Comandos, procedencia, fallos del runner y límites están en [MAM818_INTEGRATION_2026-11-02.md](MAM818_INTEGRATION_2026-11-02.md). La compatibilidad automatizada con ledger818 ya no queda pendiente; no se repitió navegador sobre este conjunto. Cancelación continúa pendiente y MAM-635 sigue parcial y abierto. La rama congelada633/634 no cambia ni se publica.
