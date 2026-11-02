# Plan de paralelización BASIS Training — 2026-11-02

## 1. Goal

Completar los tickets existentes por frentes aislados, con subagentes OpenAI y coordinación única de contratos, Git e integración. Esta entrega analiza y planifica: no implementa correcciones, modifica estados, crea tickets, publica PR ni activa servicios.

## 2. Context

Repositorio revisado en main, HEAD `d3501a78b37050cfc352af175b898a5aa9a4f11b`. Es un monolito modular hexagonal Django/PostgreSQL: accounts, athletes, catalog, training, billing, coach y sync; dominio/aplicación/adaptadores y contratos públicos, compuestos en `basis/bootstrap/`. Interfaz Django Templates + Cotton UI + HTMX/Alpine; PWA e IndexedDB. Mantener esta arquitectura.

[Readback actual de Linear](LINEAR_READBACK_2026-11-02.json): **51 tickets = 37 Done + 12 In Progress + 1 Todo + 1 Backlog**; una página completa, hasNextPage=false. Se consultaron descripciones y relaciones de los 14 abiertos. No se revisaron todos los comentarios/adjuntos, ni tickets ajenos a P-MAM-12.

[PENDIENTES.md](PENDIENTES.md), README y ROADMAP conservan cortes anteriores. MAM-624/625/819/1009/1010 están Done en Linear; no rehacer ni reabrir automáticamente su implementación. Los tres códigos LOCAL-PERF-01/02 y LOCAL-ARCH-01 son propuestas locales sin ID remoto, fuera del conteo 51.

### Hallazgo actual que antecede a las tandas

- VERIFIED: Python 3.13.7, Django 5.2.18.
- VERIFIED: `.venv-win/Scripts/python.exe -m unittest discover -s tests_architecture`: **229 pruebas, OK**, 2.662 s.
- FAILED: `.venv-win/Scripts/python.exe scripts/architecture_check.py`, exit 1:
  `Python file outside strict scope and legacy inventory: docs/tickets/evidence/probes_2026_11_02.py`.
- Causa identificada por lectura: el probe está rastreado desde 0d17abb; el checker inventaría también ese Python y su ruta no figura entre los scopes de mypy ni en el legado permitido. La auditoría anterior se ejecutó sobre otra composición de archivos.
- Propuesta de reparación bajo MAM-1008/1012: incluir el probe en el alcance estricto apropiado o trasladarlo a una ubicación de pruebas ya cubierta, actualizar referencias y comprobar tipos/checker. No ampliar exclusiones globales ni añadir código nuevo al legado inmutable. Elegir tras ejecutar mypy focal. **Corrección no realizada aquí.**

## 3. Constraints

- Trabajar sobre tickets existentes. No crear sucesores ni publicar LOCAL-* automáticamente. Sus ampliaciones necesitan conciliación con el alcance de los tickets relacionados.
- Un responsable por archivo compartido. Coordinación controla cambios de `public.py`, bootstrap, migraciones, workflow, lockfiles e integración.
- Conservar ownership, historial, versiones, ausencia frente a cero, idempotencia, UoW y orden de locks.
- Conservar `seed.py`, `manage.py`, bases locales, evidencia y archivos ajenos. No reset/clean/stash/force-push ni limpieza pendiente implícita.
- Tres documentos ajenos untracked: HANDOFF_PRESENTATION_2026-10-19.md, RELEASE_REVIEW_2026-11-01.md y HANDOFF_2026-11-01_MAM625_DONE_MAM820_WIP.md.
- Worktree MAM-820: reutilizar `.cache/worktrees/mam820-completion`; base d0e76d3, 11 modificados + 3 nuevos. Un checkout nuevo NO copia esos cambios. Preservar/registrar su manifiesto, revisar y crear commit acotado antes de incorporar main.
- Worktree MAM-624: conservar `../basis-wt/MAM-624`; aunque el ticket está Done, quedan diferencias locales que requieren conciliación antes de retirar la copia.
- Sin producción, pagos reales ni llamadas IA de pago. Sandbox, dispositivos y operación requieren sus accesos concretos; no son ejecuciones acreditadas por este plan.
- No disparar CI remoto ni hacer pushes como parte de la planificación. Antes de una ejecución futura, resolver autorización de consumo de Actions.
- Sin fechas prometidas ni capacidad de 1.000 usuarios declarada: falta medir carga, memoria, latencia y servicios externos.

## 4. Affected areas

### Inventario vivo y asignación propuesta

| Ticket | Estado vivo | Dependencia abierta relevante | Responsable/modelo propuesto | Resultado pendiente |
| --- | --- | --- | --- | --- |
| MAM-820 | In Progress | Ninguna | Terra 6.1 high; revisión Sol | Terminar candidato conservado, carrera PostgreSQL, revisión móvil e integración. |
| MAM-815 | In Progress | MAM-820 | Sol 6.1 high | Aceptación multideporte, recuperación/consecutivas y no doble conteo. |
| MAM-630 | In Progress | Ninguna | Terra 6.1 high; Sol si cambia proyección | UX de progreso, accesibilidad, fuentes/períodos y privacidad. |
| MAM-632 | In Progress | Ninguna | Terra 6.1 high; Sol para fallos transaccionales | Continuidad offline, conflictos, dos clientes, logout y SW. |
| MAM-816 | In Progress | Ninguna | Terra 6.1 high para recorrido; Sol para locks/conciliación | Circuito sandbox por la app y frescura operativa. |
| MAM-633 | In Progress | MAM-815 | Sol 6.1 high | Contexto autorizado con procedencia, límites y faltantes. |
| MAM-634 | In Progress | MAM-633 | Sol 6.1 high | Propuestas/edición/rechazo/aceptación versionadas y atómicas. |
| MAM-818 | In Progress | MAM-633 | Sol 6.1 high | Contabilidad, tarifas/modelo, conciliación y concurrencia. |
| MAM-635 | In Progress | MAM-818,633,634 | Sol 6.1 high; Terra para UI acotada | Worker robusto y adaptación visible, sin reintentar costos ambiguos. |
| MAM-636 | Backlog | MAM-633,634,635 | Terra prepara fixtures; Sol revisa evaluación | Evaluación versionada, resultados por caso y revisión deportiva humana. |
| MAM-1011 | Todo | Ninguna | Coordinación Sol | Política PR/checks, sin aprobaciones humanas de otra cuenta; readback real. |
| MAM-1012 | In Progress | Ninguna | Terra 6.1 medium | Conciliar snapshot/documentos y preservar trabajo/evidencia. |
| MAM-1008 | In Progress | Hijos 1011/1012 y estabilización | Coordinación Sol | Cierre de estabilización sobre candidato final. |
| MAM-638 | In Progress | 1008,818,815,816,820,632,630,636 | Coordinación Sol + Terra de aceptación | Matriz integral sobre un SHA final, operación y gates externos. |

Las dependencias son las relaciones leídas en Linear. MAM-1008 es una épica: sus hijos constituyen trabajo de cierre aunque no aparezcan como blockedBy. Los IDs Done relacionados siguen en el snapshot, no en la lista de bloqueos abiertos.

### Selección de modelo

Catálogo T3 consultado: proveedor `codex`, modelos `gpt-6.1-sol` y `gpt-6.1-terra` disponibles para hijos. Las asignaciones son juicio de coordinación, no un benchmark comparativo ejecutado.

[OpenAI Docs — selección de modelos](https://developers.openai.com/api/docs/guides/model-selection) sitúa Sol en trabajo complejo y Terra en tareas visuales y correcciones acotadas. Por eso propongo **Sol high** para contratos, contabilidad, concurrencia y proyecciones; **Terra high** para el candidato 820 ya definido, recorridos visuales y pruebas delimitadas; **Terra medium** para conciliación documental. La instrucción actual permite ambos: el antecedente de implementación Terra high se mantiene en 820, sin convertirlo en una regla que impida usar Sol en los nuevos frentes.

Escalar Terra a Sol cuando aparezcan decisiones nuevas de dominio, semántica de versiones, transacciones entre módulos o cambios amplios de contratos. Mantener revisión independiente y criterios iguales para ambos. No inferir costos de sesión a partir de tarifas API.

### Archivos que impiden ejecución simultánea

- **MAM-818 + MAM-635:** `coach/domain/jobs.py`, `coach/application/jobs.py`, `coach/adapters/jobs.py`, `coach/adapters/models.py`, migraciones y `basis/bootstrap/coach.py`. Un dueño Sol integra reservas, liquidación y errores; Terra puede preparar fixtures/UI fuera de esos archivos.
- **MAM-820 + MAM-815 + MAM-630:** `training/adapters/progress.py`, `training/application/progress.py`, modelos de ejecución, formularios/URLs y contratos públicos. Integrar 820 antes de liberar escritura compartida. Se puede revisar UX/fixtures en paralelo.
- **MAM-632 + MAM-820:** el adaptador sync puede delegar al recorder de training. Mientras 820 escribe ese flujo, 632 limita cambios a cliente offline y pruebas; cualquier corrección del recorder se asigna al dueño 820.
- **MAM-633 + MAM-634 + MAM-818:** snapshots de contexto, modelos de coach, public y composición. Congelar el contrato tras 633; 634 y 818 pueden avanzar en partes disjuntas, con migraciones/ediciones compartidas serializadas por coordinación.
- **LOCAL-PERF-01/02:** calendar y progreso se cruzan con 630/815/820. La parte de exportación es más independiente, pero streaming/snapshot exige diseño y pruebas; no asignarla como simple formateo.
- **LOCAL-ARCH-01:** posponer segregación de Jobs/Progress hasta estabilizar comportamiento y contabilidad. Evitar refactorizar los mismos contratos durante los fixes.

## 5. Implementation steps

### Tanda 0 — base y propiedad

1. Coordinación relee main/remoto y manifiestos de ambos worktrees; no se ha hecho fetch ni readback remoto de Git en esta entrega.
2. Un parche acotado corrige la cobertura estricta del probe, bajo estabilización existente; pasar checker, mypy pertinente y arquitectura.
3. El dueño documental concilia README/ROADMAP/PENDIENTES desde el snapshot vivo, conservando historia. No cambiar 14 estados a Done por reconciliar documentos.
4. Congelar ownership por archivo, ramas, bases sintéticas y carpetas de evidencia antes de dar permiso de escritura a los ejecutores.

### Tanda 1 — cuatro frentes como máximo, más coordinación

- **A / Terra high:** recuperar y completar MAM-820 en su worktree existente. Sin migración arquitectónica.
- **B / Sol high:** reproducir y corregir de forma acotada F01/F02 de MAM-635, junto con las invariantes de MAM-818 que afecten a la misma liquidación. Preparar política de tarifas/modelo y conciliación. Estas correcciones de código pueden adelantarse; los tickets completos siguen abiertos por sus dependencias MAM-633/634.
- **C / Terra high:** matriz y aceptación MAM-632, en checkout aislado para cualquier cambio. Evitar recorder/progress mientras A los posee. Si hay fallo transaccional, coordinar su dueño antes de editar.
- **D / Terra medium:** MAM-1012 y evidencia de MAM-1011; luego preparar recorrido Polar sandbox. Configuración administrativa de GitHub queda con coordinación. No activar protección ni pagos durante esta planificación.

### Tanda 2 — liberar analítica y contexto

1. Integrado 820, A pasa a aceptación MAM-815 con Sol high.
2. Terra puede trabajar UX MAM-630 en plantillas y evidencia; si necesita application/progress o proyecciones, serializar con 815.
3. C pasa a MAM-816: preparar local y ejecutar sandbox únicamente cuando haya entorno/acceso autorizado; registrar cada gate real por separado.
4. Con 815 aceptado, Sol completa MAM-633 y congela snapshot/contexto. En paralelo se preparan fixtures y umbrales de 636, sin afirmar evaluación completa.
5. Las mejoras LOCAL-PERF-01 se planifican como ampliación explícita de 630/638 si caben en su alcance: N+1 histórico primero, proyección acotada después. Mantenerlas identificadas como propuestas si la conciliación no está resuelta; no abrir un ticket nuevo.

### Tanda 3 — propuestas, cuotas y entrenador

1. Tras 633, Sol A completa 634; Sol B completa 818. Compartir contrato congelado; migraciones y bootstrap pasan por un solo integrador.
2. Tras ambos, un dueño Sol completa 635. Terra resuelve UI/evidencia sin tocar contabilidad compartida.
3. Ejecutar 636 cuando 633/634/635 permitan evaluar la versión final: criterios previos, dataset versionado, seguridad, calidad deportiva humana y mediciones. Las llamadas pagadas no están autorizadas por este plan.
4. LOCAL-PERF-02 y LOCAL-ARCH-01 quedan después de los fixes críticos, en lotes medidos y con alcance conciliado. Streaming y snapshot requieren Sol; retirar un prefetch innecesario con prueba de paridad puede ser Terra.
5. Cerrar MAM-1008 y MAM-638 solo al satisfacer sus criterios completos. No recortar silenciosamente la entrega a beta manual ni llamar completa a la IA deshabilitada.

### Ruta de aceptación

`820 → 815 → 633 → (634 + 818) → 635 → 636 → 638`.

En paralelo: `632 → 638`, `816 → 638`, `630 → 638`, `1011 + 1012 → 1008 → 638`.
Es el camino de dependencias; sin duraciones medidas no se afirma un camino crítico temporal.

## 6. Required skills

- `task-planning` e `implementation-handoff`: contratos y secuencia.
- `safe-git-workflow`: antes de commits, integración o acciones sobre worktrees con cambios.
- `systematic-debugging`: reproducir cada defecto, una hipótesis y una corrección verificable.
- `verify-before-complete`: recibo por SHA con VERIFIED / FAILED / NOT RUN.
- `openai-docs`: criterio de elección de modelo, contrastado con catálogo vivo.
- Un ejecutor no necesita todas las skills: solo las que correspondan a su lote.

### Contrato común para cada delegado

**Goal:** nombrar ticket existente, criterio pendiente y resultado esperado. **Required skills:** las aplicables al lote. **Likely affected areas:** lista exacta de archivos y dueño. **Constraints:** preservar contratos/propiedad y dependencias anteriores. **Do not change:** archivos de otros dueños, seed/manage, DB locales, evidencias privadas, tarifas sin fuente ni activación de servicios. **Implementation steps:** reproducir, implementar el menor lote, validar y entregar diff. **Acceptance criteria:** comportamiento observable por ticket. **Validation:** comandos, versiones, SHA y límites del entorno.

El prompt debe incluir esta información y el brief original del ticket; no depender del contexto de otro hilo. Para nuevas revisiones T3, incluir hallazgos/respuestas/objeciones en una delegación nueva y conservar su taskId/clientRequestId. Nuevos checkouts usan aislamiento worktree; el candidato sucio de 820 necesita su checkout existente. Se han utilizado únicamente dos subagentes de lectura para este plan, ambos finalizados.

## 7. Validation

### Por paquete

- **820:** dominio, dos cuentas, sync/web, rollback y carrera PostgreSQL de fechas incompatibles: un éxito, un rechazo, un recibo. Revisar capturas finales 390×844 y smoke opt-in del candidato combinado con main.
- **818/635:** fake y ORM coinciden para JSON no objeto/content null; worker procesa el siguiente job; costo/uso se conserva; no retry ambiguo. Congelar tarifa/modelo al reservar; modelo inesperado no pasa como éxito contable; conciliación uncertain idempotente y auditada. PostgreSQL para locks, carreras, rollback y no doble liberación.
- **815/633/634:** unidades/procedencia/faltantes y privacidad; no equivalencias entre deportes ni doble conteo. Propuestas inválidas no cambian historial; aceptación repetida y versión sustituida no dejan planes parciales.
- **632:** pérdida de respuesta, POST interrumpido, reapertura, dos clientes/dispositivos, conflicto revisable, logout/cambio de cuenta y actualización SW. CI actual no activa los navegadores opt-in.
- **630:** móvil/escritorio, teclado/foco, alternativa accesible, vacío/parcial/ausente/cero, períodos, enlaces y cuenta ajena. Preservar cálculos ya integrados en625.
- **816:** recorrido por adaptador de app, checkout/portal, webhook y conciliación sandbox; cancelación/impago/reembolso según alcance. Medir reconciliación y HTTP bajo lock. Mocks no sustituyen proveedor real.
- **PERF:** consultas 10/100/1.000 y linajes raíz/copia antes de filtrar; filas/RSS/tiempo/EXPLAIN PostgreSQL. Exportación 1k/10k/100k con paridad v1, privacidad, snapshot e interrupciones; cifras por medir.
- **1011:** readback independiente de protección y checks exactos postgres/operations, cero aprobación externa obligatoria y ruta de recuperación. Estado administrativo actual no releído aquí.
- **638/636:** SHA final único, matriz por criterio, pruebas operativas, carga/SLO acordados y gates humanos/externos. Cada cambio de modelo/prompt/herramientas exige evaluación pertinente.

### Comandos base propuestos para el ejecutor

Desde su worktree, usando un intérprete verificado y **DB de prueba desechable propia**. Fijar config.test_settings, secreto sintético, AI_ENABLED=0 y proveedor falso/barrera de red; nunca usar DB o credenciales productivas. Las carreras requieren PostgreSQL real. Ver `.github/workflows/checks.yml` para la selección completa de pruebas e imagen/operación.

```powershell
.venv-win/Scripts/python.exe -m unittest discover -s tests_architecture
.venv-win/Scripts/python.exe scripts/architecture_check.py
.venv-win/Scripts/python.exe -m mypy --config-file mypy-core.ini --no-incremental
.venv-win/Scripts/python.exe -m mypy --config-file mypy-django.ini --no-incremental
.venv-win/Scripts/lint-imports.exe
.venv-win/Scripts/ruff.exe check .
.venv-win/Scripts/python.exe manage.py check
.venv-win/Scripts/python.exe manage.py makemigrations --check --dry-run
npm.cmd run format:check
git diff --check
```

Añadir suite focal, Ruff format y djLint según archivos cambiados. No copiar rutas de un entorno inexistente en el checkout delegado. Promover a suite completa al integrar el lote final; no repetir todos los checks ante cambios puramente documentales. Las pruebas opt-in y los dispositivos se registran aparte. Publicar/CI remoto es una fase futura y no se ejecutó aquí.

## 8. Risks

- Cierre prematuro por CI histórico: el código funcional integrado es69eeb04; los commits documentales posteriores incorporaron el probe que hoy falla el checker. No heredar verde a d3501a7.
- Pérdida de cambios al crear checkout nuevo para820 o retirar624 por estar Done. Preservar manifiestos y comparar contenido.
- Carreras por múltiples autores en Jobs/Progress, o migraciones paralelas. Ownership explícito y revisión del árbol combinado.
- Dependencias de aceptación confundidas con imposibilidad de corregir un defecto aislado: se puede reparar F01/F02 antes, manteniendo635/818 abiertos.
- Acceso sandbox, endpoint HTTPS, dispositivos y revisión deportiva/operativa pueden bloquear aceptación; más agentes no sustituyen esas evidencias.
- MAM-817 sigue Done aunque816 haya sido reabierto; conservar su estado y volver a comprobar los flujos de permisos en aceptación final.
- No se ha demostrado rentabilidad, tarifas reales actuales del proveedor ni capacidad objetivo. El plan no hace afirmaciones financieras o deportivas nuevas.

### Recibo de esta entrega

VERIFIED documental: JSON legible, 51 IDs únicos, conteos 37/12/1/1, cobertura de los 14 abiertos en la matriz, grafo abierto sin ciclos, enlaces locales válidos y ausencia de espacios finales. Visual del reparto inspeccionada a 728 y 390 px, sin errores de consola. Git diff --check sin errores; dos documentos nuevos propios y tres documentos ajenos preservados, sin cambios rastreados.

VERIFIED: inventario vivo 51/37/14; catálogo OpenAI en T3; arquitectura/código revisados; Git/worktrees leídos; versiones Python/Django; 229 pruebas puras. FAILED: checker por probe fuera de scope. NOT RUN: reparación, suite Django completa, PostgreSQL/concurrencia, mypy/lint/formato completos, navegador, sandbox, proveedor IA, CI remoto nuevo, protección GitHub, carga y operación. No se tocaron fuentes productivas, tickets ni worktrees.

