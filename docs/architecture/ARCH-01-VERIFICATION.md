# ARCH-01 / MAM-822 — evidencia y reanudación

Fecha: 2026-10-19. Base local `main` y referencia local `origin/main`: `08dcd020ad9e7ae2809b4a2376c8ae4cddd6b36e`. El fetch remoto falló; no se acredita que la referencia local represente el remoto actual.

**Implementación local verificada; integración parcial en main/21a8ab3.** Se comprobó el commit después de la ejecución externa del usuario: contiene 47 archivos (paquete basis, configuración, CI y controlador de arquitectura), pero no las pruebas, inventarios ni documentación de esta entrega. ARCH-01 permanece In Progress hasta integrar esos archivos y comprobarlos en main. ARCH-02 y las etapas siguientes no comenzaron porque el plan exige integración y verificación completa de la etapa anterior. La migración completa sigue pendiente.

## Cambios de esta entrega

- ADR-001, responsabilidades, contratos, extensión futura de planificación y mapa de etapas en ARCHITECTURE.md y ROADMAP.json.
- Paquete basis con las siete fronteras de negocio, capas reservadas, contratos públicos explícitos, identificadores NewType separados y protocolos Clock/UnitOfWork. Ningún flujo funcional ha sido migrado todavía.
- mypy estricto separado para núcleo e infraestructura Django; django-stubs y herramientas fijadas en requirements-dev.txt, instaladas en .venv-win con uv.
- Ocho contratos Import Linter; control AST de fronteras, imports relativos y TYPE_CHECKING, y lista explícita de legado que solo puede reducirse.
- Quince pruebas de arquitectura, incluidas independencia real sin site-packages/settings y rechazo efectivo de IDs intercambiados y Any por mypy.
- CI ejecuta esos controles antes de los checks existentes y obtiene dos commits para comparar inventarios.
- Linear: épica MAM-821, etapas MAM-822 a MAM-831, cadena serial nativa, 31 bloqueos funcionales; estados e historial conservados. Readback en linear-readback.json.

## Verificaciones ejecutadas

Intérprete: `.venv-win/Scripts/python.exe` (Python 3.13.7, Django 5.2.18). Los comandos Django usaron `DJANGO_SETTINGS_MODULE=basis_trainning_app.test_settings` y `DATABASE_URL=sqlite:///:memory:`. La base original no se modificó.

| Estado | Comprobación | Resultado |
| --- | --- | --- |
| VERIFIED | `python scripts/architecture_check.py` | Fronteras estáticas e inventario sin errores |
| VERIFIED | `python -m unittest discover -s tests_architecture` | 15 pruebas aprobadas; incluye núcleo con `-I -S` y controles negativos mypy |
| VERIFIED | `python -m mypy --config-file mypy-core.ini` | 36 archivos, cero errores, sin plugin Django |
| VERIFIED | `python -m mypy --config-file mypy-django.ini` | 41 archivos, cero errores, plugin django-stubs/test_settings |
| VERIFIED | `.venv-win/Scripts/lint-imports.exe --no-cache` | Ocho contratos cumplidos, ninguno roto |
| VERIFIED | `.venv-win/Scripts/ruff.exe check .` | Sin errores |
| VERIFIED | `.venv-win/Scripts/ruff.exe format --check basis scripts/architecture_check.py tests_architecture` | Formato del código nuevo |
| VERIFIED | `python manage.py check` | Cero incidencias |
| VERIFIED | `python manage.py makemigrations --check --dry-run` | No changes detected |
| VERIFIED | `python manage.py test training.tests --noinput` | 111 descubiertas, 108 aprobadas y tres omitidas por PostgreSQL; igual baseline antes/después |
| VERIFIED | Diff de archivos propios / `git diff --check` acotado | Sin errores de whitespace; seed.py conserva diff previo 168 adiciones/56 eliminaciones; manage.py conserva solo el cambio de modo |
| VERIFIED | Readback de Linear | 35 funcionales, cuatro Done, 31 abiertos con bloqueo; estados conservados; diez hijos con cadena serial |
| FAILED | `git fetch origin` | Permission denied al abrir `.git/FETCH_HEAD`, también tras solicitar ejecución ampliada |
| FAILED | `git switch -c arch/01-contracts` | Cannot lock ref / unable to create directory, también con ejecución ampliada |
| NOT RUN | Commit e integración ARCH-01 en main | Impedidos por escritura denegada en .git |
| NOT RUN | Carreras PostgreSQL / CI remoto | Las tres pruebas omitidas no quedan certificadas por SQLite; CI incorporado pero no publicado/ejecutado |
| NOT RUN | Navegador y recorridos offline, proveedores LIVE | Sin cambios funcionales en esta entrega; permanecen para las etapas correspondientes |

Un primer ensayo de la prueba negativa mypy falló por combinar `-c` con `files` de configuración. Se reprodujo el error de CLI, se conservó el resto de la configuración estricta en una configuración temporal sin `files`, y la prueba pasó verificando los códigos arg-type, explicit-any y no-any-unimported. No se omitieron errores del producto para lograr el resultado.

## Reanudación exacta

Resolver la capacidad del entorno para escribir en `.git`; no modificar ACL para eludir restricciones, ni usar reset, stash, limpieza, otra copia del repositorio o un índice alterno. Volver a comprobar `git status`, diff y origen antes de integrar. El intento actual de `git switch -c arch/01-complete` con ejecución ampliada sigue fallando por Permission denied.

Se preparó `.cache/Complete-Arch01.ps1` para ejecución por el usuario en PowerShell externo. Su sintaxis fue comprobada. Crea una rama complementaria, añade únicamente documentación y tests pendientes, comprueba que los archivos necesarios estén en el índice, confirma y fusiona por fast-forward; verifica de nuevo su presencia en HEAD. Se detiene ante errores, cambios ya preparados o archivos ajenos en el índice. No toca seed.py ni manage.py. No se ha ejecutado ese script desde Codex ni se acredita aún su commit.

Con Git operativo, crear `arch/01-contracts`. Reejecutar los controles anteriores. Añadir exclusivamente:

```powershell
git add -- .github/workflows/checks.yml requirements-dev.txt .importlinter mypy-core.ini mypy-django.ini basis scripts/architecture_check.py tests_architecture docs/ARCHITECTURE.md docs/ROADMAP.json docs/ARCHITECTURE_EXECUTION.md docs/architecture
git diff --cached --stat
git diff --cached --check
git commit -m "arch: establish hexagonal boundaries and strict typing gates"
```

Inspeccionar el diff preparado y confirmar que no contiene `seed.py` ni `manage.py`. Integrar el commit en main mediante el flujo habitual, comprobar el SHA y los controles pertinentes, actualizar evidencia/Linear y solo entonces marcar MAM-822 Done e iniciar ARCH-02/MAM-823. Conservar los cambios previos durante todo el proceso. No activar producción ni llamar proveedores cobrados.
