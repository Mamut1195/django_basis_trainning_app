# Goal
Migrar BASIS por etapas a arquitectura hexagonal con tipado estricto, conservando datos y comportamiento. Primera entrega: ARCH-01; ARCH-02 comienza solo después de integrar y verificar ARCH-01.

# Context
Base local: main 08dcd02. Baseline ejecutado el 2026-10-19: 111 pruebas, 108 pasan en SQLite temporal en memoria; tres carreras requieren PostgreSQL. No hay AGENTS.md adicional en el repositorio. Las reglas globales proporcionadas por el usuario aplican.

# Constraints
Preservar seed.py y el modo de manage.py. Conservar tablas, app labels, migraciones, HTTP/JSON, propietario, CSRF y colas. Sin producción, cobros ni catálogo de programas. No cambiar reglas funcionales durante ARCH-01.

# Affected areas
Nuevo paquete basis; controles en scripts/architecture_check.py, tests_architecture, mypy-core.ini, mypy-django.ini y .importlinter. CI, dependencias de desarrollo, documentación y ROADMAP. Los modelos actuales siguen registrados en sus aplicaciones Django.

# Implementation steps
1. Crear épica y diez etapas seriales en Linear; añadir bloqueo a los 31 funcionales abiertos, conservando estados y dependencias.
2. Registrar ADR, mapa, contratos, inventario explícito de legado y baseline.
3. Incorporar controles estáticos y ejecutables (incluido TYPE_CHECKING), mypy estricto separado y CI.
4. Ejecutar regresión, Ruff, Django y comprobación de migraciones. Integrar commit de ARCH-01 en main antes de iniciar ARCH-02.
5. ARCH-02 migrará inicio, lectura, resultados y finalización con puertos, UoW explícita y adaptador Django; probar rollback y compatibilidad web/offline.

# Required skills
task-planning, safe-git-workflow, verify-before-complete.

# Validation
Núcleo sin Django/plugin/configuración, mypy con django-stubs para infraestructura; Import Linter más AST para importaciones de tipos y contratos públicos. Pruebas negativas de controles; suite existente en base temporal, Ruff, check y makemigrations --check --dry-run. Etiquetar VERIFIED / FAILED / NOT RUN por entrega.

# Risks
El entorno deniega escritura en .git incluso tras pedir ejecución ampliada: no modificar ACL ni eludir permisos. Sin integración comprobada, no cerrar ARCH-01 ni comenzar ARCH-02. PostgreSQL y CI remoto requieren ejecución independiente; SQLite no demuestra bloqueos.
