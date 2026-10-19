# Reanudación y privacidad — 2026-10-19

## Goal

Continuar BASIS-002 / MAM-616: comprobar aislamiento por cuenta en API, HTML,
exportación y contexto IA; reducir los datos personales anidados en registros.

## Context

El handoff de Linear del 17 de octubre registra `main` remoto en `ea551a0` y
el checkout local en `459f530`, con la implementación ya publicada. La consulta
actual a GitHub confirma tres commits por delante del HEAD local. Linear
conserva 3 Done, 31 In Progress y 1 Backlog. Las búsquedas de Notion no
localizaron una página específica de BASIS Training.

## Constraints

Conservar todos los cambios anteriores, especialmente `seed.py`, `manage.py`
y la base original. No activar proveedores ni producción. No cerrar tickets
sin pruebas pertinentes y commit integrado en main. Solo existe el worktree
principal: no hay worktrees adicionales para eliminar.

## Affected areas

Serializadores y permisos de la API heredada, pruebas de privacidad y
documentación de esta tanda. Se conserva el vínculo OneToOne explícito y el
comando operativo de vinculación de perfiles antiguos.

## Implementation steps

1. Contrastar handoff, dependencias de Linear y main remoto.
2. Revisar permisos, filtros y asignación de propietario existentes.
3. Sustituir el perfil completo anidado por su identificador en entrenamientos
   y RM; declarar autenticación obligatoria en las vistas privadas.
4. Ejecutar una matriz de anónimo, propietario, otra cuenta y cuenta sin perfil,
   incluyendo CSRF, latest, reasignaciones, HTML, exportación y contexto IA.
5. Registrar verificaciones, integración y límites reales.

## Required skills

`safe-git-workflow`, `task-planning`, `notion-spec-to-implementation` y
`verify-before-complete`. No se delega trabajo en esta tanda.

## Validation

| Comprobación | Estado | Resultado |
| --- | --- | --- |
| Seguridad de partida | VERIFIED | 9 pruebas sobre SQLite temporal. |
| Matriz BASIS-002 | VERIFIED | 14 pruebas: anonimato, dos cuentas, latest, creación con IDs de cuenta/perfil diferentes, referencias ajenas, perfil ausente, CSRF real, respuestas mínimas, HTML/exportación/contexto IA y vinculación explícita sin fusión ni verificación implícita. |
| Suite completa local | VERIFIED | 111 pruebas descubiertas; 108 ejecutadas correctamente y 3 de concurrencia omitidas por SQLite. |
| Django | VERIFIED | `check` sin problemas; `makemigrations --check --dry-run` sin diferencias. |
| Ruff | VERIFIED | `check .` y formato de los tres archivos Python cambiados sin diferencias. |
| Comparación con main remoto | VERIFIED | 145 archivos de implementación revisados por hash Git: 143 idénticos y solo los dos archivos API cambiados en esta tanda diferentes. Los dos archivos nuevos son esta documentación y la matriz de pruebas. |
| Fuentes anteriores | VERIFIED | `seed.py` y `manage.py` conservan los SHA256 del handoff; quedan excluidos de la integración. |
| Diff | VERIFIED | `git diff --check` sin errores; índice vacío. El estado local todavía incluye la implementación anterior por HEAD desactualizado. |
| CI PostgreSQL de esta tanda | NOT RUN | Pendiente del nuevo commit. No reutilizar las 97 pruebas históricas como evidencia de esta tanda. |
| Sincronización de metadatos locales | FAILED | Fetch no puede escribir `.git/FETCH_HEAD`, también con ejecución elevada. |
| Proveedores LIVE, producción y dispositivos físicos | NOT RUN | Fuera de BASIS-002; no se activaron. |
| Tipado estático | NOT APPLICABLE | El repositorio no define esta comprobación. |

La primera ejecución de las pruebas nuevas detectó tres supuestos erróneos
del propio test (factory con título fijo, respuesta DRF vacía y nombres del
catálogo público); se corrigieron y las 14 pruebas pasaron antes de ejecutar
la suite completa. No se modificaron factories ni el contrato de latest.

## Contrato de privacidad

La cuenta autenticada elige el perfil por `User.account`, nunca por igualdad
de claves primarias. Los perfiles históricos permanecen sin asignación hasta
la vinculación explícita del operador; el comando no verifica el correo ni
fusiona perfiles. El índice OneToOne impide más de un perfil por cuenta.

Entrenamientos y RM devuelven `user` como identificador de perfil. Ya no
repiten nombre, correo, edad, ubicación, objetivos ni descripción personal.
La consulta `/api/v1/users/` conserva el perfil completo del propietario.
`user_id` solo admite el perfil de la cuenta, y el servidor vuelve a asignar
el dueño al guardar. `rm_referencia` continúa siendo controlado por el servidor.

Las consultas privadas, latest, exportación y contexto IA se filtran por cuenta.
Las referencias ajenas fallan con 400; los detalles ajenos con 404; anónimos en
API con 403 y en HTML con redirección al acceso. Escribir mediante sesión exige
CSRF, correo verificado y acceso vigente. No se añaden clubes ni organizaciones.

## Risks

`git fetch origin` falla al escribir `.git/FETCH_HEAD`, también al solicitar
ejecución elevada. La sincronización local sigue pendiente por permisos del
entorno. No modificar ACL ni sustituir el checkout para eludir esta restricción.
El cliente de registros recibirá `user` como ID en vez de un objeto de perfil;
el perfil propio continúa disponible en `/api/v1/users/`.
