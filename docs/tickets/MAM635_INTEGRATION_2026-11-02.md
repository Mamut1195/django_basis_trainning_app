# MAM-635: integración parcial de coordinación

**VERIFIED** sobre árbol funcional13b2b9c, con fuente633/634 ya integrada y sin ledger818: commits propios del ejecutor36d6968fa757f9c8dd1e0f4b2e424b483121376f y e76c50fbc0d02224694ee0aa763b731264867d47 incorporados como8718f94 y13b2b9c. Coordinación revisó el diff: prueba/recibo y16 líneas de template de consumo; no cambian jobs, contratos ni contabilidad.

- PostgreSQL18.4, base exclusiva basis_wave3_integration/test_basis_wave3_integration: **10 pruebas OK, cero omisiones,3.218s**. Comando: `.venv-win/Scripts/python.exe .cache/wave3-20261102/run_guarded.py test basis.bootstrap.tests.test_mam635_acceptance --noinput -v 1`. Log `.cache/wave3-20261102/acceptance635-integrated.log`.
- Mypy Django focal: un archivo sin errores. Ruff check y format de la prueba: satisfactorios. DjLint lint/check de coach/jobs/_result.html: cero errores y cero cambios. git diff --check satisfactorio.
- Configuración sintética; HTTP real denegado por runner, worker real con MockTransport. No proveedor LIVE ni datos reales.

Las pruebas verifican consulta/recuperación sin segundo enqueue, propiedad404, fallo ambiguo sin reenvío, entrenamiento manual disponible, cuarentena, límite, propuesta inválida, aceptación/descarte, adaptación que preserva historial y consumo que distingue costo desconocido de cero. No acreditan tarifas o conciliación818.

El navegador390×844/1280×800, teclado e interrupción/reinicio del servidor pertenecen al ejecutor y su recibo MAM635_ACCEPTANCE_2026-11-02.md; coordinación no repitió navegador. La prueba de caída del servidor no fue modo avión ni dispositivo físico.

**PENDING**: aviso local de fallo de polling y desaparición tras recuperación, delegado al mismo ejecutor; cancelación pendiente conforme al contrato propio; integración con ledger818 después de corregir y revisar su barrera de intento. Suite completa de este conjunto, CI remoto, IA/pagos LIVE, lector de pantalla y dispositivos físicos: **NOT RUN**. MAM-635 continúa parcial y abierto.

La candidata633/634 en codex/basis-context-proposals-20261102 permanece exactamente en f42b86160c0afe3a545488fd07f0e5dd8a61a15f; no contiene estos cambios635. Publicación/Actions todavía esperan respuesta a la solicitud de autorización. Los tres documentos untracked ajenos se preservan sin añadir al índice.
