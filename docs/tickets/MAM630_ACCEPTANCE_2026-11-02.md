# MAM-630 — matriz de aceptación, 2026-11-02

Base: `98ea2923f6a675001bc9951f971d8a43759b58a3`. Alcance: UX de progreso, recuperación, perfil y exportación; se reutilizan las consultas de MAM-624/625. No se modifica el servicio de analítica de MAM-815 ni se afirma cierre del ticket.

| Criterio | Evidencia y estado |
| --- | --- |
| Procedencia y apertura de fuentes | **VERIFIED parcialmente:** el resumen explica sesiones, bloques, series, duración y RPE; agenda y sesiones enlazan a sus registros, y marcas distinguen declarado/estimado y fuente. El resumen enlaza ahora a historiales completos de bienestar y peso. Pruebas de períodos, agenda y marcas ejercitan aislamiento y rutas. Falta revisar el flujo completo en navegador con el árbol integrado. |
| Ausencia frente a cero | **VERIFIED parcialmente:** pruebas de períodos y bienestar distinguen cero observado, ausencia y no aplicación; no se introduce otro cálculo. Falta aceptación visual integral con datos incompletos. |
| Móvil y accesibilidad sin color | **NOT RUN:** existen alternativas textuales, listas y tabla de registros legados; no se demuestra legibilidad en móvil, teclado ni lector de pantalla en esta ejecución. No hay evidencia de gráficos de evolución completos. Emulación no demostraría dispositivo físico. |
| Ajustes e historial | **VERIFIED parcialmente:** regresión de perfil y bienestar ejercita persistencia, propiedad y conservación de observaciones. Falta recorrido completo de edición y revisión accesible en navegador. |
| Filtros, vacío y error | **VERIFIED parcialmente:** períodos inclusivos, zona horaria, paginación y rangos inválidos probados. El rango inválido de bienestar ahora solicita corrección sin afirmar que no hay registros. Falta revisión visual de todos los estados. |
| Exportación íntegra y privada | **VERIFIED parcialmente:** pruebas de propiedad, estructura y perfil; descarga incorpora `Cache-Control: private, no-store` mediante `never_cache`. La suite de propiedad cubre relaciones existentes; no demuestra por sí sola integridad de requisitos futuros ni comportamiento de todos los intermediarios. Falta recorrido de descarga en navegador. |

## Verificación local

- **VERIFIED:** PostgreSQL 127.0.0.1:55482, base autorizada `basis_wave2_630`, `config.test_settings`, clave sintética y `AI_ENABLED=0`; Django crea/destruye la base de pruebas correspondiente. `manage.py test basis.bootstrap.tests.test_progress_periods basis.bootstrap.tests.test_wellness basis.bootstrap.tests.test_export basis.bootstrap.tests.test_export_ownership tests.regression.test_profile_onboarding --noinput`: 61 pruebas, OK.
- **VERIFIED:** `manage.py test basis.bootstrap.tests.test_progress basis.bootstrap.tests.test_progress_agenda basis.bootstrap.tests.test_strength_marks tests_architecture.test_progress tests_architecture.test_progress_periods --noinput`: 23 pruebas, OK.
- **NOT RUN:** conexión HTTP real, navegación visual, teclado/lector de pantalla, dispositivo físico, suite completa, integración en main y CI remoto. No se cambió Linear ni se ejecutaron servicios pagos o de producción.

El ticket permanece abierto: la aceptación requiere el árbol final integrado, validación visual y accesible, y resolver las brechas de evolución/gráficos y cualquier hallazgo de integración con MAM-815. Los resultados anteriores no acreditan el cierre de MAM-630.
