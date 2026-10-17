# Primera tanda de implementación — 2026-10-17

## Goal

Desarrollar y revisar BASIS-001 (MAM-615), BASIS-005 (MAM-618) y
BASIS-003 (MAM-619). El coordinador integra; tres implementadores trabajan
con contratos y archivos disjuntos. Esta tanda no acredita los otros tickets.

## Context

La rama de partida es `main`, commit `459f530`. Ya había una implementación
amplia sin commit y cambios previos del usuario. Los campos de perfil y su
migración 0007 son requisitos del producto actual y se conservan. El cambio
de modo de `manage.py` y las ampliaciones sintéticas de `seed.py` quedan fuera
de los commits de integración. La protección del seed que existe en el archivo
de trabajo permanece pendiente junto con sus cambios previos.

## Constraints

Conservar los datos originales y el trabajo previo. No activar infraestructura,
pagos ni llamadas al modelo. No acceder a credenciales. Done exige aceptación
completa, evidencia pertinente y commit en `main`.

## Affected areas

| Responsable | Ticket | Archivos asignados |
|---|---|---|
| Popper | BASIS-001 | Verificador de entorno, sus pruebas y `REPRODUCIBILITY.md`. |
| Epicurus | BASIS-005 | Contrato deportivo, fixture semanal y su prueba ejecutable. |
| Euclid | BASIS-003 | Servicio de métricas, modelos/serializador/admin heredados, pruebas y documentación de fuerza. |
| Coordinador | Integración | Preservación, revisión, validación PostgreSQL, commits y conciliación Linear. |

## Implementation steps

1. Leer criterios actuales de Linear y revisar la implementación existente.
2. Entregar contratos con aceptación verificable y límites de escritura.
3. Preservar una copia recuperable de las fuentes y ejecutar la suite de partida.
4. Revisar las entregas, integrar y ejecutar las comprobaciones pertinentes.
5. Actualizar Linear con evidencia y mantener abiertos los criterios pendientes.

## Required skills

`task-planning`, `implementation-handoff`, `safe-git-workflow` y
`verify-before-complete`.

## Validation

Resultados de partida ejecutados en esta tanda:

| Comprobación | Estado | Evidencia |
|---|---|---|
| Suite PostgreSQL 18.4 | VERIFIED | 52 pruebas; creación y destrucción de la base de prueba completadas. |
| Django check y migraciones pendientes | VERIFIED | Sin problemas; `makemigrations --check --dry-run` sin diferencias. |
| Ruff | VERIFIED | Sin errores. |
| Estáticos y JavaScript | VERIFIED | `collectstatic`; `node --check` de app/offline. |
| Migración de copia anonimizada | VERIFIED | Todos los valores de las columnas originales, IDs y cantidades conservados; claves foráneas válidas; hash del archivo original sin cambios. |
| Instalación en venv nueva | FAILED | Resolución de las 22 dependencias completada; copia de `certifi/cacert.pem` denegada por la política de archivos del entorno. |
| Integraciones externas y despliegue | NOT RUN | Fuera de esta tanda. |

La copia de migración conserva las medidas y fechas necesarias para comparar
el esquema; se sustituyeron los textos identificativos del perfil. No representa
una certificación de anonimización para compartir datos. Ni la copia ni el
respaldo de fuentes se publican: permanecen en directorios ignorados.

Evidencia local: `artifacts/orchestration/legacy-anonymized-result.json` y
`source-before-integration.zip`. El zip contiene solo fuentes seleccionadas,
sin bases de datos ni archivos de credenciales.

## Risks

BASIS-001 conserva abierto el criterio de instalación limpia. La comprobación
con el entorno existente no sustituye ese criterio. BASIS-003 depende de
BASIS-001 y BASIS-005. Las pruebas de contrato y fórmulas no certifican la
calidad de planes de IA ni recomendaciones clínicas.

## Entregas revisadas

Los tres agentes terminaron sus contratos. El coordinador revisó los cambios,
solicitó correcciones de administrador, ausencia histórica de RM, cálculo
compartido y desbordamientos, y ejecutó la validación integrada.

| Entrega | Resultado comprobado |
|---|---|
| BASIS-001 | CLI real: 22 pins coincidentes, seis etapas VERIFIED, health 200 y login con CSRF 200/302; limpieza del temporal confirmada. Siete pruebas del verificador. |
| BASIS-005 | Contrato revisable y fixture de siete jornadas; seis pruebas cubren planificación, ejecución parcial/completada, omisión derivada, reprogramación, historial, cuentas y evaluación. |
| BASIS-003 | 32 pruebas: Decimal, Epley compartido, RM fechado e inmutable, referencia ausente estable, PATCH y guardado parcial, formularios reales de admin, RPE separado y overflow HTTP 400 sin persistencia. |
| Integración | 97 pruebas PostgreSQL pasaron. La ejecución final se repitió después del formato de los agentes; los hashes de las fuentes permanecieron estables. Ruff, formato de los ocho archivos comprobados y migraciones sin diferencias. |
| Configuración de producción | `check --deploy --fail-level WARNING` sin problemas, usando configuración efímera de prueba. No es evidencia de un despliegue. |

Se verificó además una protección alternativa del seed anterior que falla antes
de importar Django o ejecutar borrados. No se integró: la revisión automática
rechazó sustituir el contenido del índice mientras se preservaba el archivo de
trabajo, por exceder su interpretación de la autorización. La alternativa segura
excluye `seed.py` completamente del commit; sus ampliaciones sintéticas y su
protección actual permanecen intactas y pendientes. El seed del commit anterior
no queda certificado y no debe formar parte del arranque o despliegue.

La escritura ordinaria de `.git/objects` fue denegada por el sandbox; la
integración requiere ejecutar el comando Git con los permisos correspondientes.
Hasta confirmar el commit en `main`, ningún ticket se considera cerrado.

No se ejecutaron en esta tanda navegador/PWA, Docker, CI remota, dispositivos,
proveedores LIVE, carga de 1.000 usuarios ni evaluación deportiva profesional.
Las evidencias anteriores de navegador se conservan en `VALIDATION.md` como
registro histórico, sin presentarlas como nuevas comprobaciones.

## Estado antes de la integración remota

La escritura elevada tampoco pudo iniciarse: dos intentos de la alternativa
segura fallaron con `helper_unknown_error: setup refresh had errors`. No se
ejecutó `git add`, no se creó commit y no hubo push. `main` permanece en
`459f530dae787fc9cc72f2584b66e76652e212cb`, con el índice vacío. No se intentó
cambiar permisos, reemplazar `.git` ni modificar el historial.

Linear se actualizó y se leyó de vuelta: BASIS-005/MAM-618 y
BASIS-003/MAM-619 en **In Review**; BASIS-001/MAM-615 sigue **In Progress**.
El proyecto conserva 35 tickets: 32 In Progress, 2 In Review, 1 Backlog y 0 Done.
BASIS-005 tiene la aceptación técnica comprobada pero espera el commit;
BASIS-003 espera además la dependencia BASIS-001. BASIS-001 conserva pendiente
la instalación limpia. Ningún otro ticket se cierra por esta tanda.

La entrega recuperable está en `artifacts/orchestration/source-final.zip`, con
manifiesto SHA-256 en `source-final-manifest.json`. Incluye las fuentes de la
implementación y excluye `seed.py`, `manage.py`, bases de datos, entornos y
credenciales. `integrate-reviewed-wave.ps1` verifica el commit de partida,
la rama, el índice vacío y todos los hashes antes de preparar las fuentes.
Solo debe ejecutarse cuando se restablezca el ejecutor autorizado o la escritura
en Git; no cambia permisos ni intenta sortear las restricciones. Si cambió una
fuente o el commit de partida, exige una nueva revisión. No hace push ni escribe
en Linear.

Después de integrar, comprobar el commit en `main` y conciliar los tickets
contra sus criterios pendientes. Los procesos PostgreSQL de validación se
detienen al terminar; no se deja un servicio de aplicación en ejecución.

## Integración remota y cierre verificados

El usuario desarchivó `Mamut1195/django_basis_trainning_app`. Se integró la
instantánea revisada por el conector GitHub mediante un commit cuyo padre es
`459f530`, y se avanzó `main` sin force. No se modificaron permisos locales,
el índice, el historial anterior ni los archivos de trabajo del usuario.

- Commit de implementación en `main`: [`50583c69757fa528e8e47246483de177baa0cb60`](https://github.com/Mamut1195/django_basis_trainning_app/commit/50583c69757fa528e8e47246483de177baa0cb60).
- Árbol leído de vuelta: `ea0268051eafcc9d0f0155994e0694f23037a060`.
- Los 138 archivos coinciden por hash con la entrega revisada; el diff remoto
  contiene 123 archivos añadidos/modificados y ningún cambio en `seed.py` o
  `manage.py`, incluidos sus modos originales.
- Se ejecutaron nuevamente Ruff y el CLI de entorno aislado antes de integrar:
  seis etapas VERIFIED, 22 versiones coincidentes y limpieza confirmada.
- [CI Django checks 39067380697](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39067380697)
  terminó SUCCESS sobre ese commit. El job `117497736216` instaló dependencias
  en un runner nuevo Ubuntu/Python 3.13, pasó Ruff, check y migraciones sin
  diferencias, **97 pruebas PostgreSQL 18.4 en 7,768 s**, destrucción de la base
  de prueba y generación de 176 archivos estáticos. Todos los pasos terminaron
  correctamente, incluidos los contenedores de pruebas.

La instalación limpia de CI resuelve el criterio pendiente de BASIS-001. Las
97 pruebas incluyen el recorrido real del verificador con migración SQLite
desde cero, health y login con CSRF. El fallo del certificado en el sandbox
Windows sigue siendo un límite local; no invalida la instalación verificada
en CI ni se eludió su restricción.

Linear se actualizó y leyó de vuelta: **BASIS-001/MAM-615, BASIS-005/MAM-618 y
BASIS-003/MAM-619 están Done**, con criterios marcados y enlaces al commit,
pruebas y CI. Se cerró BASIS-003 después de verificar sus dos dependencias en
Done. El proyecto tiene 35 tickets: 31 In Progress, 1 Backlog y 3 Done.

El checkout local conserva `HEAD=459f530` y todos sus cambios de trabajo: su
Git continúa sin sincronizar por las restricciones locales. **No ejecutar el
script de recuperación para volver a crear la integración**; el commit ya
existe en el remoto. La sincronización futura del checkout requiere preservar
las modificaciones previas y conciliar contra `main`; no usar reset ni checkout
que descarte trabajo. El manifiesto y zip originales se conservan como evidencia
de la instantánea integrada, anterior a esta actualización documental.

Los otros 32 tickets conservan sus criterios y estados. No se activó producción
ni se hicieron llamadas o pagos de proveedores LIVE, pruebas físicas PWA o carga
de 1.000 usuarios. La CI de PostgreSQL no certifica esos ámbitos.
