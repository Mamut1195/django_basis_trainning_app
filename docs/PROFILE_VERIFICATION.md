# MAM-620 / BASIS-006 — perfil y configuración inicial

## Alcance y contrato

Base de implementación: `c8b9ae8ab4cb53290d9445aa23ebf2060ab57fd3`. Criterios literales:
export saneado de Luna `luna-auth-plan-20261021-0241/luna-auth-plan.sources.sanitized.md`,
sección MAM-620, líneas 123–139. Las capturas locales de implementación siguientes conservan su contexto anterior a integración; el [readback final](#readback-de-integracion-y-cierre-2026-10-21) registra MAM-620 y su dependencia810 Done. El usuario eligió explícitamente **Perfil gratuito**:
perfil, objetivo personal de texto, disponibilidad, disciplinas y mediciones de
peso requieren cuenta activa, perfil vinculado y correo verificado, sin suscripción.
La misma autorización se aplica en HTTP y casos de uso. La lectura/exportación
propia conserva su acceso autenticado existente, incluso al vencer acceso
comercial; no se endurece su política de lectura por este cambio. Un perfil sin
verificar puede consultar/exportar lo propio, pero no realizar escrituras personales.

| Criterio | Implementación y evidencia ejecutable |
| --- | --- |
| Objetivo y disponibilidad para planificar | Objetivo personal de texto gratuito + días/minutos, equipo y restricciones. La configuración parcial/completa se deriva de objetivo personal (o estructurado existente) + días. Objetivos estructurados se consultan mediante `TrainingPresentation.goals`, pero su creación mantiene autorización comercial. El estado no certifica calidad deportiva ni factibilidad del plan. |
| Evolución de peso conserva historial | `Measurement` añade observaciones sin reemplazar otras, incluso el mismo día. Cada cambio de peso mediante el servicio/formulario de perfil archiva el valor anterior dentro de la misma UoW y con bloqueo de perfil. Correcciones son nuevos registros con notas. |
| Ausente frente a cero y completar después | Peso/edad/umbrales son opcionales. Una línea base objetivo cero se muestra como cero. El peso legado cero se conserva explícitamente, pero no se presenta como medición corporal válida. Formularios inválidos conservan valores; disciplina existente se edita con su ID propio. |
| Consulta/exportación privada documentada | `/profile/`, `/profile/measurements/` paginado, Progreso y `/export/`. Tests de dos cuentas, PK cuenta/perfil distintas, IDs/origen inyectados, CSRF, ausencia de perfil y descarga de navegador. |

## Peso, unidades y fechas

- `Measurement.weight_kg` usa kg decimales canónicos, 0,01–500 para mediciones
  realizadas. Campo unidad del formulario admite kg; no convierte lb ni interpreta
  un número cero como información ausente. Fecha obligatoria ISO `AAAA-MM-DD`,
  no futura respecto al día de la aplicación (`America/Guayaquil` actualmente).
- No se convierte `User.peso` en una medición fechada. Es dato legado opcional sin
  fecha conocida; al reemplazarlo o borrarlo se archiva como
  `origin=legacy_profile`, `date=null`, conservando también un cero explícito.
  El valor actual sigue en el perfil. No se inventa retrospectivamente una fecha.
- `origin=measured` identifica observaciones fechadas. El historial de Progreso
  usa solo estas observaciones, no los snapshots legados. El perfil muestra la
  última por fecha, con desempate por ID; consultar/exportar permite ver todas.
- Una meta `Goal` es intención planificada: su fecha futura es válida. Su línea
  base y meta mantienen la misma unidad declarada en el contrato existente; esta
  entrega no añade un catálogo dimensional ni conversiones a los objetivos.
  Los umbrales por disciplina validan unidad/fecha/método; su fecha de medición
  también es ISO y no futura. No se inventan umbrales ausentes.
- La zona horaria se declara y muestra; no cambia el reloj del calendario ni las
  fechas históricas. La aplicación global de zonas corresponde al contrato de
  calendario posterior, no a una supuesta preferencia ya aplicada.

## Privacidad y exportación v1

`basis-export-v1` conserva las 19 secciones de datos del atleta: perfil,
preferencias, mediciones, disciplinas, bienestar, RM e historial legado,
objetivos, planes, ciclos, prescripciones, sesiones, bloques, series, intervalos,
viajes, etapas, propuestas y trabajos IA en su proyección de exportación existente.
Solo se exportan filas propias y sus hijos. `measurement` incorpora `origin`;
`weight_kg` declara la unidad y `date=null` significa fecha desconocida, nunca hoy.
Se conservan etiquetas externas de modelos y el formato decimal/ISO existente.
No se incluye `auth.User`, hashes de contraseña, sesiones/cookies, tokens de
verificación/recuperación, CSRF ni credenciales de proveedores. Notas, limitaciones,
mediciones y propuestas pueden ser sensibles: el usuario decide dónde guarda su
descarga. No se prometen datos que solo están pendientes en IndexedDB del navegador.

## Esquema y compatibilidad

La migración `basis_athletes/0002_measurement_origin` sigue al esquema final actual
(26 migraciones en la base de partida; catálogo 0002 ya incluido). Agrega origen,
admite fecha desconocida solo para snapshots legados y restringe combinaciones
origen/fecha/peso por constraint. Filas medidas existentes reciben `measured`.
No cambia PK, UUID, account, email_verified, preferencias, ni historias de
entrenamiento. Se prueba fresh y upgrade desde el esquema final anterior con
filas sintéticas, incluido perfil sin cuenta. Datos inválidos insertados por fuera
del contrato requieren revisión: no se corrigen ni eliminan silenciosamente.
ADR-002 retiró las apps/migraciones antiguas; no es una migración in-place de la
SQLite original del usuario. La API de perfil sigue siendo de solo lectura.
La conservación descrita pertenece a los casos de uso del producto; no convierte
en inmutables escrituras SQL/ORM directas ni cambios administrativos por fuera de
ellos. El admin legado mantiene su contrato independiente.

## Verificación reproducible

Toolchain existente del main, sin instalación: Python 3.13.7/Django 5.2.18,
PostgreSQL 18.4, mypy 1.19.1 y Playwright 1.64.0/Chromium shell 1243.
El ejecutor local `.cache/verify_mam620_revision.py` crea un directorio UUID, cluster y
puertos propios; usa correo en memoria y no llama proveedores. Ejecuta SQLite
focalizado, suite PostgreSQL completa incluida concurrencia/upgrade, puras,
mypy, lint, límites arquitectónicos y navegador real del perfil. Solo detiene
el cluster y servidor que creó. Sus logs/resultados quedan bajo `.cache/mam620-free-gate-*`.
El manifiesto SHA-256 anterior/posterior vincula los archivos exactos del candidato.

```powershell
& "C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Scripts/python.exe" -B .cache/verify_mam620_revision.py
```

Los resultados efectivos se registran en `.cache/MAM620_REVISION_REPORT.md`
y el `result.json` del run citado allí; no reutilizar los conteos históricos
288 PostgreSQL/174 puras/mypy 113–330 como evidencia de esta entrega.
Los skips de concurrencia en SQLite no acreditan PostgreSQL. No se declara
capacidad de producción, SMTP LIVE, aceptación humana ni dispositivos físicos.

### Revisión F1: errores parciales del peso

El revisor independiente detectó HTTP 500 con peso vacío, texto, NaN/Infinity,
exceso de dígitos o precisión: `ModelForm` ya había rechazado el campo y aun así
ejecutaba `Measurement.clean()` con `weight_kg=None`. La frontera del modelo ahora
rechaza explícitamente valores no convertidos y fechas inválidas mediante
`ValidationError`; no omite None ni modifica el contrato Decimal del dominio.
`objects.create`, `save` y `full_clean` siguen rechazando datos inválidos, incluso
None en un campo excluido y en el origen legacy. Cero medido sigue siendo inválido;
cero legado archivado sin fecha sigue permitido.

El control de peso usa entrada de texto con teclado decimal y el mismo
`DecimalField`/validadores: así el navegador también conserva visible `abc`, NaN
o precisión excesiva en la página de corrección, en lugar de sanear el valor a
vacío como haría un input numérico. Las regresiones incluyen respuesta HTTP 200
con errores/entradas conservadas, cero filas inválidas y corrección válida 302.
Los recibos y el RED anteriores se preservan como historia, no como PASS actual.

## Frontera para integrar después de MAM-810

Accounts/enrollment y campos de identidad no cambian. La autorización personal
consume `BillingProfiles`, proyección pública estable del perfil, y consulta
`auth.User.is_active` persistido mediante Django; nunca selecciona perfil por
coincidencia de PK/email ni por flags recibidos del navegador. Se compone en
`basis/bootstrap/athletes.py`; la guardia HTTP pertenece solo a athletes. No hay
imports de implementación privada de accounts ni modificaciones de `billing.can_write`.

Perfil/objetivo de texto, preferencias, disciplinas y peso usan esta autorización
personal. RM, historial de entrenamiento, bienestar de entrenamiento, metas
estructuradas/planes, calendario, prescripción e IA mantienen sus guardias y
cuotas actuales. Crear/activar una prueba, checkout o cambiar billing no forma
parte del onboarding gratuito. La UI separa CTA gratuitos de acciones comerciales.

Registro histórico de la implementación aislada: no se tocaron `test_identity.py`, `test_installation.py`, accounts/config, CI,
README ni ROADMAP. La integración con el estado `EmailVerification` del candidato
MAM-810 debe volver a comprobar actividad/verificación y el vínculo persistido;
la prueba aislada sobre esta base no acredita esa composición futura. El ticket
620 seguía pendiente de MAM-810 Done, revisión e integración/readback en aquella captura. Ese pendiente quedó resuelto por el readback siguiente; no se reescriben sus fallos ni recibos.

## Readback de integracion y cierre 2026-10-21

**MAM-620 ya estaba Done cuando Luna lo verificó**, `completedAt=2026-10-21T05:03:54.506Z`; se conservó, sin transición nueva. [PR #7](https://github.com/Mamut1195/django_basis_trainning_app/pull/7), merge `25af153d5108d39c97bf5cda6fea58d6a6346f7b`; [CI postmerge 39547452496](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39547452496) SUCCESS:346PG/176puras, mypy115/340 y ocho contratos. La composición integrada con810 mantiene perfil/objetivo de texto/preferencias/disciplinas/peso gratuitos bajo autorización personal; consulta/exportación propias conservan su política autenticada. RM, entrenamiento, Goal estructurado, planes e IA siguen comerciales.

Procedencia del [artefacto12322016375](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39547452496/artifacts/12322016375): **miembro `operations.json` SHA256 `7b66b7d53e6ed3d13cfdf533839fc50dd89a65dc501bedbc53156366ca302da0`**, no el ZIP; **ZIP SHA256 `43605d796a55fac63a50d0f3b5add73e080b6ed7215c5c7486f22082240d85d8`**. El fixture CI tiene10EmailVerification y0Measurement, no estados individuales verificables. Las3mediciones y12verificaciones de la restauración local son evidencia suplementaria separada, no conteos de CI. Los564hashes del candidato integrado y160/160HTTP200 constan en el readback de Luna, no como una ejecución local nueva de esta conciliación. SMTP/proveedores LIVE, producción y dispositivos físicos siguen NOT RUN. Fuente y cadena posterior: [diario de cierre](DEVELOPMENT_2026-10-21.md#procedencia-y-limites-de-la-evidencia).
