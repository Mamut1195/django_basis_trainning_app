# Validación de la entrega — 2026-10-17

La tabla siguiente registra la validación de la implementación inicial, antes de su integración. La ejecución posterior se documenta en [la primera tanda](IMPLEMENTATION_WAVE_01.md), con sus comprobaciones y límites propios. No se activaron despliegues, pagos ni llamadas reales al modelo. El estado no equivale a una versión publicada ni al cierre de todos los criterios del roadmap.

## Evidencia ejecutada

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
