# MAM-630 — matriz de aceptación, 2026-11-02

Base: `98ea2923f6a675001bc9951f971d8a43759b58a3`. Alcance: UX de progreso, recuperación, perfil y exportación; se reutilizan las consultas de MAM-624/625. No se modifica el servicio de analítica de MAM-815 ni se afirma cierre del ticket.

## Continuación local: gráficos y contexto MAM-815

Se conserva `7bf307d`; `ba5c42e` añade las barras de observaciones y el cherry-pick `f77f15d` incorpora el contrato MAM-815 (origen `6e672bc0bac66f2bb1070ceca6058d429e91f526`). Coordinación ya integró el original: no volver a aplicar ese commit allí. El commit posterior de UX muestra el contrato en Progreso y contiene esta actualización.

| Alcance | Evidencia y límites actuales |
| --- | --- |
| Evolución y fuentes | Peso fechado, fatiga y disposición tienen barras por observación, fecha, unidad o escala, valor textual y enlace a su registro. Las marcas de fuerza tienen barras solo al seleccionar un ejercicio; medido declarado y estimado se presentan por separado con método Epley y fuentes existentes. Cada grupo usa el máximo de la página desde cero y advierte que no compara páginas. No se interpolan observaciones; valores legados sin fecha y datos faltantes no generan barras. Los historiales textuales siguen disponibles. |
| Contexto 815 | Se muestran sesiones completadas, fecha, disciplinas, protocolo, segundos, RPE, carga y su método, fecha distinta previa, diferencia de fechas, días consecutivos y número de sesiones de la fecha; cada ficha enlaza a sesión. Si existe etapa, enlaza al recorrido y muestra orden, altitud y nota declarada. La plantilla escapa notas; cero y ausencia son distintos. El método aclara que no se infieren descanso, horas de recuperación ni riesgo. La selección del período limita los días observados. |
| Móvil y teclado | **VERIFIED local, parcial:** navegador colaborativo, viewport 390 × 844 CSS píxeles, con datos sintéticos. Se inspeccionaron gráficos de peso, bienestar y marcas, más el contexto; no se observó desbordamiento horizontal en las páginas medidas. Con Tab/Enter se abrió un registro de bienestar; con Enter se abrió una marca y un recorrido; foco visible verificado en esos enlaces y en Guardar. Esto es emulación de tamaño, no dispositivo físico ni auditoría integral de accesibilidad. |
| Ajustes y exportación | **VERIFIED local:** el recorrido sintético guardó 55 minutos y equipo, que persistieron al volver a abrir el formulario. La descarga en navegador contenía esos ajustes, tres pesos y dos check-ins de la cuenta sintética. Las pruebas de propiedad entre cuentas y cabeceras siguen siendo necesarias para el alcance completo de privacidad. |
| Filtro, vacío y error | **VERIFIED local:** en navegador el filtro de bienestar mostró el período, barras del rango y ausencias sin barra; un rango sin registros mostró vacío, y un rango invertido mostró error sin afirmar vacío. Las pruebas automatizadas cubren rangos, paginación y aislamiento. |

En el navegador la nota sintética `Nota ficticia <b>sin interpretar</b>` apareció como texto escapado. El medidor nativo inicialmente mostraba verde; se sustituyó por un color uniforme de interfaz para no sugerir que más fatiga sea favorable. El valor numérico sigue visible. Las filas de contexto se materializan para todo el período, igual que el contrato MAM-815: no se acredita capacidad para historiales grandes.

### Comprobaciones de la continuación

- **VERIFIED:** con PostgreSQL autorizado, `config.test_settings`, `DJANGO_SECRET_KEY` sintética y `AI_ENABLED=0`, `manage.py test basis.bootstrap.tests.test_progress_context_ux basis.bootstrap.tests.test_observation_charts basis.bootstrap.tests.test_wellness basis.bootstrap.tests.test_strength_marks basis.bootstrap.tests.test_progress basis.bootstrap.tests.test_progress_periods basis.bootstrap.tests.test_progress_agenda basis.bootstrap.tests.test_export basis.bootstrap.tests.test_export_ownership tests.regression.test_profile_onboarding tests.regression.test_multisport_815 tests.regression.test_training_contract tests.regression.test_trekking_820 tests_architecture.test_multisport_815 tests_architecture.test_progress tests_architecture.test_progress_periods --noinput`: **113 pruebas OK**, sin omisiones, sobre el árbol combinado. Django creó y destruyó `test_basis_wave2_630`.
- **VERIFIED:** Ruff check/formato para los seis Python de UX, djLint para las cinco plantillas afectadas y `git diff --check`.
- **VERIFIED:** `mypy --config-file mypy-django.ini` sin errores en 416 archivos; `unittest discover -s tests_architecture` 233 pruebas OK; `scripts/architecture_check.py` y ocho contratos de Import Linter correctos.
- **NOT RUN:** Prettier: no hay ejecutable instalado en este worktree ni en el repositorio raíz; no se instaló ningún paquete.
- La ejecución general `manage.py test --noinput` terminó con **847 OK, 5 omitidas**, pero empezó antes del cherry-pick de MAM-815 y siguió mientras cambiaba el árbol. Se conserva como observación histórica, no como validación de un árbol combinado estable.
- **FAILED inicial, corregido:** la primera regresión de perfil contaba fechas directamente en todo el HTML; el gráfico añadió otra aparición. Se cambió para comprobar los dos registros del historial; pasó en la batería posterior de 113.

**NOT RUN:** lector de pantalla real, dispositivo físico, auditoría exhaustiva de contraste/foco en todos los estados, pruebas de capacidad, CI remoto e integración final en main. La validación local no cambia el estado de Linear ni sustituye la aceptación del árbol final por coordinación.

## Evidencia de la primera entrega

La siguiente matriz y sus NOT RUN describen el estado anterior a esta continuación; no contradicen los resultados locales posteriores indicados arriba.

| Criterio | Evidencia y estado |
| --- | --- |
| Procedencia y apertura de fuentes | **VERIFIED parcialmente:** el resumen explica sesiones, bloques, series, duración y RPE; agenda y sesiones enlazan a sus registros, y marcas distinguen declarado/estimado y fuente. El resumen enlaza ahora a historiales completos de bienestar y peso. Pruebas de períodos, agenda y marcas ejercitan aislamiento y rutas. Falta revisar el flujo completo en navegador con el árbol integrado. |
| Ausencia frente a cero | **VERIFIED parcialmente:** pruebas de períodos y bienestar distinguen cero observado, ausencia y no aplicación; no se introduce otro cálculo. Falta aceptación visual integral con datos incompletos. |
| Móvil y accesibilidad sin color | **NOT RUN:** existen alternativas textuales, listas y tabla de registros legados; no se demuestra legibilidad en móvil, teclado ni lector de pantalla en esta ejecución. No hay evidencia de gráficos de evolución completos. Emulación no demostraría dispositivo físico. |
| Ajustes e historial | **VERIFIED parcialmente:** regresión de perfil y bienestar ejercita persistencia, propiedad y conservación de observaciones. Falta recorrido completo de edición y revisión accesible en navegador. |
| Filtros, vacío y error | **VERIFIED parcialmente:** períodos inclusivos, zona horaria, paginación y rangos inválidos probados. El rango inválido de bienestar ahora solicita corrección sin afirmar que no hay registros. Falta revisión visual de todos los estados. |
| Exportación íntegra y privada | **VERIFIED parcialmente:** pruebas de propiedad, estructura y perfil; descarga incorpora `Cache-Control: private, no-store` mediante `never_cache`. La suite de propiedad cubre relaciones existentes; no demuestra por sí sola integridad de requisitos futuros ni comportamiento de todos los intermediarios. Falta recorrido de descarga en navegador. |

## Verificación local

- **VERIFIED:** PostgreSQL 127.0.0.1:55482, base autorizada `basis_wave2_630`, `config.test_settings` y `AI_ENABLED=0`; Django creó y destruyó la base de pruebas correspondiente. `manage.py test basis.bootstrap.tests.test_progress_periods basis.bootstrap.tests.test_wellness basis.bootstrap.tests.test_export basis.bootstrap.tests.test_export_ownership tests.regression.test_profile_onboarding --noinput`: 61 pruebas, OK. Corrección de evidencia: ese primer comando estableció `SECRET_KEY`, pero la configuración consume `DJANGO_SECRET_KEY`; no se verificó la procedencia de la clave que tomó ese proceso. Los comandos posteriores establecen explícitamente `DJANGO_SECRET_KEY` sintética.
- **VERIFIED:** `manage.py test basis.bootstrap.tests.test_progress basis.bootstrap.tests.test_progress_agenda basis.bootstrap.tests.test_strength_marks tests_architecture.test_progress tests_architecture.test_progress_periods --noinput`: 23 pruebas, OK.
- **NOT RUN:** conexión HTTP real, navegación visual, teclado/lector de pantalla, dispositivo físico, suite completa, integración en main y CI remoto. No se cambió Linear ni se ejecutaron servicios pagos o de producción.

El ticket permanece abierto: la aceptación requiere el árbol final integrado, validación visual y accesible, y resolver las brechas de evolución/gráficos y cualquier hallazgo de integración con MAM-815. Los resultados anteriores no acreditan el cierre de MAM-630.
