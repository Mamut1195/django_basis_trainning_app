# Validación de la entrega — 2026-10-17

## MAM-624 / BASIS-010: check-in y evolución

Wellness distingue `day` (general del día, valor de las filas anteriores),
`before` y `after`. Hay un registro por cuenta, fecha y momento. Crear no
sobrescribe: un duplicado devuelve un error en español; las correcciones usan
la edición explícita desde **Perfil → Evolución del bienestar**.
Solo fecha y momento son siempre necesarios; un formulario sin observaciones,
con fecha y momento válidos, sigue siendo válido. Se conserva el contrato
histórico: si indicas HRV (incluido 0 ms), indica también el método; si el dolor
es mayor que 0, indica la zona o regiones. Dolor 0 no requiere regiones y la
ausencia de HRV no exige método. Estas reglas se aplican en dominio, modelo y
formulario, cuya ayuda las muestra. Registrar entrenamiento sigue sin requerir
check-in. Las escalas muestran sus extremos y unidades.

La evolución (`/profile/wellness/`) incluye ambos extremos del rango; por defecto
son los últimos 30 días incluido hoy. `start`/`end` usan AAAA-MM-DD; fechas
inválidas o invertidas devuelven 400 con explicación. Un dato ausente aparece
como `Sin dato`, y cero sigue siendo cero. Las fechas futuras de check-in se rechazan.
La página requiere login y solo consulta la cuenta autenticada; editar una fila
ajena devuelve 404 con acceso de escritura. Se conserva la política comercial
existente para escribir; consultar el historial propio no exige suscripción.

La tarjeta del día y el contexto más reciente del coach eligen primero la fecha
más reciente y, dentro de ella, **after > before > day**. No se combinan valores
de distintas filas. La historia conserva las últimas 14 observaciones (no días),
y la exportación conserva todas con `moment`. El wire del coach incluye `moment`
y acepta payloads anteriores sin ese campo como `day`.
Es solo un registro para seguimiento: sin puntuaciones agregadas, alertas,
diagnósticos ni predicciones. No cambia el catálogo ni duración/RPE de sesión.

Los resultados ejecutados de esta entrega se registran en `result.md` y logs de
la carpeta de evidencia indicada por el operador; las tablas siguientes son
evidencia histórica y no acreditan esta entrega.

La tabla siguiente registra la validación de la implementación inicial, antes de su integración. La ejecución posterior se documenta en [la primera tanda](IMPLEMENTATION_WAVE_01.md), con sus comprobaciones y límites propios. No se activaron despliegues, pagos ni llamadas reales al modelo. El estado no equivale a una versión publicada ni al cierre de todos los criterios del roadmap.

**Aclaración actual,2026-10-21:** la cadena810/620/622/623 está Done con integración y CI, según el [readback de cierre](DEVELOPMENT_2026-10-21.md#cierre-de-la-cadena-mam-810--620--622--623). SMTP LIVE/proveedor continúa NOT RUN, pero **no es gate de MAM-810 ni de MAM-623**; el transporte SMTP local de810 es evidencia separada. La tabla y la continuación siguientes son históricas. Esto no retira los pendientes de correo operativo, Polar/IA LIVE, despliegue, dispositivos o aceptación humana del producto completo.

## Integración GitHub y CI verificadas

La primera tanda se integró en `main` mediante el commit
[`50583c6`](https://github.com/Mamut1195/django_basis_trainning_app/commit/50583c69757fa528e8e47246483de177baa0cb60).
Los 138 archivos se compararon por hash; `seed.py` y `manage.py` quedaron fuera.
[CI 39067380697](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39067380697)
terminó SUCCESS: instalación en runner nuevo, Ruff, check, migraciones sin
diferencias, **97 pruebas PostgreSQL 18.4** y 176 archivos estáticos. Esta evidencia
sustituye los pendientes anteriores de integración e instalación limpia para
BASIS-001/005/003, ya Done en Linear. El checkout local sigue en `459f530` con
sus cambios preservados; no se ejecutó reset ni pull sobre ese trabajo.

Proveedores LIVE, despliegue, dispositivos físicos y capacidad siguen sin
certificarse. El [registro de la tanda](IMPLEMENTATION_WAVE_01.md) contiene los
límites y la reanudación del checkout. La tabla siguiente es evidencia histórica
de la implementación inicial, no una segunda ejecución de sus comprobaciones.

## Evidencia anterior a la primera tanda

| Comprobación | Estado | Resultado / alcance |
|---|---|---|
| Suite Django con PostgreSQL 18.4 | VERIFIED | 52 pruebas pasaron, incluida creación/destrucción de la base de prueba. |
| Concurrencia PostgreSQL | VERIFIED | Dos conexiones no exceden el presupuesto individual ni el fondo global; una operación sync concurrente se aplica una vez. |
| Privacidad y acceso | VERIFIED | Datos ajenos rechazados, catálogo restringido, CSRF, verificación, acceso caducado y exportación. |
| Lógica deportiva | VERIFIED | RM fechado/inmutable, cálculos al modificar o poner cero, decimales JSON, cargas separadas, ciclos, versiones, adherencia y trekking sin doble conteo. |
| Integraciones contractuales | VERIFIED | Firmas/replays, conciliación con respuestas simuladas, precio/prueba, checkout reutilizado, reservas, cuotas y timeout sin reintento. **No son pruebas LIVE de Polar o DeepSeek.** |
| Recorrido de navegador Chromium/Edge | VERIFIED | Vistas a 1440×1000 y 390×844; descarga de sesión, ingreso offline, recarga sin red, cola ordenada, reconexión y ejecución completada en revisión 3. Sin errores JavaScript. |
| Accesibilidad automatizada | VERIFIED | axe-core 4.14.0: cinco páginas en tema claro y oscuro a 390 px, sin infracciones detectadas en WCAG A/AA/2.1AA. Esta muestra no es una certificación completa. |
| Estáticos y JavaScript | VERIFIED | `collectstatic`, `node --check` y sintaxis de plantillas; recursos locales sin depender de CDN para el producto. |
| Lint y migraciones | VERIFIED | Ruff y `makemigrations --check --dry-run` sin diferencias. |
| Configuración de producción | VERIFIED | `check --deploy --fail-level WARNING`, con configuración de prueba segura, sin avisos. No demuestra HTTPS desplegado. |
| Migración de base anterior | VERIFIED | Copia de `db.sqlite3`: mismos identificadores y cantidades antes/después: 13 clasificaciones, 3 ejercicios, 15 perfiles, 30 RM y 16 registros. Identidades públicas únicas y perfiles sin asignación automática. Hash del archivo original sin cambios. |
| Backup/restauración PostgreSQL | VERIFIED | Formato custom restaurado en `basis_restore_final`, base nueva con 33 migraciones. No se restauró sobre la base original. |
| Roadmap Linear | VERIFIED | 35 tickets, 86 dependencias nativas, sin diferencias respecto al grafo previsto: 34 In Progress, 1 Backlog, 0 Done. Identificadores originales conservados. |
| Git | VERIFIED | Se revisó estado/diff y espacios. Los cambios previos se conservaron; `manage.py` mantiene el cambio de modo previo. No se hizo commit ni push. |

Los archivos de evidencia local están en `artifacts/`: `browser/result.json`, `browser/accessibility.json`, capturas de escritorio/móvil, `legacy-migration.json` y respaldos de prueba. Se excluyen del repositorio porque pueden contener registros del entorno de prueba. `docs/ROADMAP.json` conserva únicamente el mapa de tickets y dependencias verificado.

## No ejecutado y criterios abiertos

| Comprobación | Estado | Condición para completarla |
|---|---|---|
| Polar sandbox LIVE | NOT RUN | Configurar producto, precio, impuestos exclusivos, tarjeta/prueba y secreto webhook; verificar cobro, renovación, impago, cancelación y reembolso reales. |
| Entrenador DeepSeek LIVE | NOT RUN | Credenciales, fondo autorizado y evaluación de `evals/coach_cases.json` con revisión humana. La IA sigue deshabilitada inicialmente. |
| SMTP real | NOT RUN | Configurar remitente y comprobar verificación/recuperación con entrega real. Las pruebas usan correo en memoria; desarrollo escribe archivos locales. |
| Build/arranque Docker | NOT RUN | No hay daemon Docker disponible. Se proporcionaron los archivos, pero no se presenta el build como aprobado. |
| CI remota | NOT RUN | No hubo commit/push ni ejecución de GitHub Actions. |
| Instalación y uso en dispositivos físicos | NOT RUN | Android/iOS, permisos de almacenamiento, instalación, actualización y recuperación en condiciones reales. Solo hubo emulación de viewport en Chromium. |
| Capacidad de 1.000 usuarios activos | NOT RUN | Carga sostenida sobre despliegue representativo, medición de latencia, conexiones, worker y recuperación. Es objetivo, no capacidad demostrada. |
| Aceptación de UI/UX y programación deportiva | NOT RUN | Revisión del producto por su propietario y evaluación de planes del modelo; el esquema y las pruebas no certifican calidad del entrenamiento. |
| Typecheck estático | NOT APPLICABLE | El repositorio no define una comprobación de tipos estáticos. Se ejecutaron compilación/importación y pruebas Python. |

## Continuación operativa

1. Revisar el diff conjunto y separar un commit verificable de los cambios anteriores del usuario. Estar en `main` sin commit no cumple la regla de integración.
2. Certificar primero correo y Polar sandbox; ejecutar `manage.py reconcile_billing --all` periódicamente para recuperar eventos perdidos.
3. Evaluar la IA con casos de contexto incompleto, carga multideporte, dolor, altitud, inyección y límites de costo antes de habilitarla.
4. Validar PWA en dispositivos, el contenedor y el despliegue con HTTPS, respaldos externos y observabilidad.
5. Cerrar únicamente los tickets cuyo alcance completo y pruebas pertinentes estén integrados en `main`. Los criterios aún abiertos siguen abiertos en Linear.
