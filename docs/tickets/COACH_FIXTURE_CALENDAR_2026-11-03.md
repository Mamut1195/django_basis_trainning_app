# Coach: propuestas sintéticas independientes del día de ejecución

## Causa y alcance

El helper de pruebas `test_coach_edges.account()` declaraba disponibilidad lunes/miércoles/viernes, mientras `proposal()` fijaba la sesión siempre en la fecha de ejecución. El martes, jueves y fin de semana, el validador real rechaza correctamente esa propuesta. El ejecutor636 conservó una focal con ocho errores y comprobó su relación con el calendario; congelar globalmente la fecha al lunes no corrige el helper.

Se conserva exactamente la disponibilidad `(1, 3, 5)` en una constante de fixture. La propuesta conserva su semana desde hoy hasta hoy+6 y ubica la sesión en el primer día disponible dentro de ella. No consulta ni adapta la propuesta a modificaciones deliberadas del perfil: una incompatibilidad real sigue fallando. No cambian producción, fuentes633/634, reglas deportivas, reloj de la aplicación ni rama congelada.

## Regresión RED → GREEN

Nueva prueba con siete fechas explícitas de lunes a domingo, cada una bajo un patch acotado al subcaso. Construye las entidades/codec/contexto reales y pasa el resultado al validador de producción. Confirma que los días disponibles siguen siendo `(1, 3, 5)`. Otra prueba cambia la sesión a un martes y exige que el mismo validador la rechace.

- **RED reproducido por coordinación:** dos pruebas; cuatro errores en los subcasos martes/jueves/sábado/domingo. El caso de rechazo intencional pasa. Log `.cache/wave4-calendar/red.log`, SHA256 `F09D4E689B0C1CF6635024994BBE3FF8E9F01AFDFEFA59A0AC16E30543329F32`.
- **GREEN por coordinación:** nueva regresión, `test_coach_edges` y `test_mam635_acceptance`: **27 pruebas, cero omisiones, 4.637 s, salida 0**, sin congelar globalmente la suite al lunes. Log `.cache/wave4-calendar/green.log`, SHA256 `A0E2450A38017C057061740E522561298349831DAE33D230B797215A79FE9FD0`.
- **VERIFIED:** mypy Django focal, dos archivos; Ruff check y formato de ambos; checker de arquitectura y diff check. No se relajaron aserciones o guardas.

Comando desde coordinación:

```powershell
.venv-win/Scripts/python.exe -B .cache/wave4-818-20261102/run_guarded.py manage test basis.bootstrap.tests.test_coach_fixture_calendar basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_mam635_acceptance --noinput -v 2
```

PostgreSQL18.4 compartido, `basis_wave3_integration`/`test_basis_wave3_integration`, settings/credenciales sintéticos, AI0 fuera de fixtures y guardas de transporte/red del runner existente. Django creó y destruyó solo la base temporal; no se detuvo PostgreSQL. Las ejecuciones originales de636 y sus 94 pruebas con reloj global siguen siendo evidencia del ejecutor, no de este recibo.

**NOT RUN:** suite global nueva, CI remoto, proveedor LIVE y producción. No se publicaron cambios, no se cerraron tickets y se conservaron los tres documentos ajenos untracked.
