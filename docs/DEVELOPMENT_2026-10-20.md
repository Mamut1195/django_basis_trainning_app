# Goal

Reconcile and accept the published architecture, then complete BASIS-004/MAM-617 data integrity and advance BASIS-012/MAM-626 with a reviewable UX contract.

Estado actual al readback del 2026-10-21: **MAM-617, MAM-621 y MAM-637 Done**.
El [cierre de catálogo y operaciones](#cierre-del-lote-mam-621-y-mam-637-2026-10-21)
registra integración, fuente de Luna y bloqueos que siguen abiertos. MAM-621/MAM-637
ya estaban Done antes de esa revisión; no se atribuye a Luna un cambio de estado.
Los apartados del lote anterior, incluido su [cierre de integridad](#cierre-operativo-del-lote),
conservan el contexto de sus capturas: las referencias a integración pendiente,
31 o 30 abiertos y fallos intermedios son históricas, no el estado actual.

# Context

Baseline main is `24484b7c8c5a4c0beb89ee1dc854c91581d7293a`. GitHub main, local HEAD and tracking ref match. The existing untracked `HANDOFF_PRESENTATION_2026-10-19.md` is preserved separately. Linear owns operational state; no accessible BASIS Notion page was found.

# Constraints

Keep strict typed hexagonal boundaries, account isolation and existing URLs/history. Use generated fixtures and disposable databases only. Preserve unrelated changes. No live providers, paid services, SMTP or deployment. Only close tickets with complete criteria, verification and integration in main.

# Affected areas

Catalog/profile validation, demo fixture idempotence and integrity regression tests; UX contract, component documentation and demonstrated presentation defects. Orchestrator owns aggregate gates, source evidence, backup/restore validation, Git and tracker coordination. Luna owns Notion/Linear; two implementers own disjoint areas.

# Implementation steps

1. Verify published SHA, actual CI steps/logs and the 348-file browser source manifest against working bytes and HEAD blobs.
2. Reconcile ARCH-09, ARCH-10 and architecture epic in Linear in dependency order, preserving functional states and dependencies.
3. Reproduce and repair ORM normalization and repeated demo seed duplication; prove archive/history and deletion safeguards without schema drift.
4. Produce a current navigable UX contract, responsive/state inventory and browser evidence. Retain any human or assistive-technology acceptance gate that remains unexecuted.
5. Run strict/lint/import/schema, pure and PostgreSQL regression, disposable migration/backup/restore and applicable browser checks. Review scoped diffs, integrate verified changes in main and read back tracker updates.

# Required skills

task-planning, safe-git-workflow, verify-before-complete; systematic-debugging for reproduced failures. Browser interaction uses the existing Playwright Chromium/Edge tooling.

# Validation

Baseline independently read back: CI Django run `39367822734`, PostgreSQL job `118448585157`, 246 tests without skips, 174 pure tests, mypy 113 core/318 runtime files. All 348 manifest sources match working files and HEAD (LF/CRLF normalization only for text); aggregate `f4806664064c1ef3c1c9f73cff68c61d7098c77e29ee110a633f497f8fabc391`. A fresh local pure-suite rerun passed 174 tests after sandbox TEMP permission errors were resolved by the normal escalated runner. New delivery results are recorded separately after implementation.

## Integridad BASIS-004 / MAM-617: validación delegada nueva

Estado de la revisión previa a PR #1: código aprobado; [readback y
matriz de aceptación](HISTORY_INTEGRITY.md#readback-actual-tras-revisión-independiente-y-luna-2026-10-20).
Los párrafos de ejecuciones siguientes se conservan como historial, con sus
propios hashes y fallos. La integración y CI del candidato siguen pendientes.

El ejecutor revisó la implementación existente y las 14 pruebas de integridad;
no encontró un defecto adicional que requiriese cambiar código. Sus cambios de
entrega se limitan a esta sección y al recibo documental de
[HISTORY_INTEGRITY.md](HISTORY_INTEGRITY.md). Se preservaron los 24 archivos de
trabajo previo, con copias iniciales en el directorio aislado de evidencia.

Ejecutado en esta delegación:
`.venv-win/Scripts/python.exe -B .cache/integrity_delegate_gate_20261020.py`.
Recibo nuevo: `.cache/integrity-delegate-0a7fed2f46234775ac62b4435cc45976/result.json`.
VERIFIED: PostgreSQL 18.4, 29 pruebas focalizadas (14 de integridad), 260 de
regresión sin omisiones, 174 puras, mypy 113/320, ocho contratos de imports,
arquitectura, Ruff/djLint/Prettier, check/esquema/estáticos, seed repetido,
migración repetida sin cambios de filas ni historial y respaldo/restauración
en otra base nueva. El navegador nuevo completó 21 comprobaciones con
Chromium 153.0.8010.12 sobre el mismo runtime; servidor, navegador y cluster
PostgreSQL quedaron detenidos. No se abrió la base original ni se llamaron
proveedores/SMTP.

Runtime probado: 349 archivos, hash
`5c456d64dbd6fa33847bdf5ac73c621de4bee8fc3b0a006471541e60db1980cb`.
Manifiesto ampliado (incluye tests, seed, CI, configuración y docs; excluye
entornos/bases/logs/dumps):
`cd047aa9cc6d1ac5d042d032d1b7520e501a504686c0291d7ca3187ee83a1026`.
Ambos estables durante la corrida. Estos dos documentos se actualizan después;
su diff y verificación de preservación se registran en `delivery.patch` y
`delivery.json`, separados del recibo de pruebas.

Recomendación: criterios técnicos locales verificados, mantener el ticket
abierto hasta integración revisada en main, CI del candidato y confirmación
operativa por Luna. Commit/push y Linear/Notion NOT RUN por este ejecutor. Esta
validación de integridad no cierra los gates propios de UX.

Seguimiento concurrente: después del gate estable, otro ejecutor cambió
`app.css` y `scripts/ux_acceptance.py`. El readback detectó esa diferencia; el
recibo PostgreSQL no se reasigna al runtime posterior. Complemento nuevo en
`.cache/integrity-delegate-0a7fed2f46234775ac62b4435cc45976/supplement-bd0aef8835bf4aaa9cbc37096ab0a5e3/result.json`:
navegador 21/21, Ruff y Prettier VERIFIED con hash runtime estable
`9f41b01e3fe11a0d8d8e8d0d11039fb24d72a040ff873940939341c72f8caaec`;
mypy Django FAILED por siete errores `object`/iteración/`len` en el script UX.
El ejecutor de integridad no modificó ese archivo. El intento complementario
anterior conserva su fallo de formato en `supplement/`. Resolver el tipado por
su propietario y repetir los controles afectados antes de integración/cierre.
Detalle y límites en HISTORY_INTEGRITY; estado global del complemento FAILED.

## Readback actual y corrección documental R1/R2

Registro anterior a PR #1 y al cierre operativo de las 23:01Z, conservado como historial.

La revisión independiente posterior verificó el código y las comprobaciones en
`.cache/independent-review-a5614455b6c040438616780d94269822/result.json`:
mypy Django 320/núcleo 113, Ruff lint/formato, djLint, Prettier, arquitectura y
ocho contratos, 174 pruebas puras, check/esquema y navegador 21/21. Runtime final
`d3ecd68ddced4c3d4bcc3de23c94be869ebdbf1847f7456d93b3fe251dc09533`, estable.
Es readback de evidencia independiente, no una nueva ejecución por quien edita
estos documentos. El complemento histórico conserva FAILED, mientras la nueva
revisión acredita tipos/formato sobre otros bytes finales. PostgreSQL no se
repitió en esa revisión; su recibo anterior de 260 pruebas permanece separado.

Luna (`opencode-go/gpt-6-luna`, sesión `ses_ea48bb89affe113OniCrTc83lt`) confirmó
MAM-821 Done, 31 funcionales abiertos sin bloqueo de arquitectura y
MAM-617/626/627 In Progress. Fuente local leída, sin invocar trackers:
`C:/Users/JONNAT~1/AppData/Local/Temp/opencode/luna-linear-20261020-ses_ea48bb89.md`.
HISTORY_INTEGRITY mapea los cuatro criterios vivos; la prueba de archivado
consulta efectivamente la sesión y el RM, además de comprobar PROTECT.

Correcciones de esta entrega, sólo documentales:

- R1: `ROADMAP.json` expresa las mismas dependencias actuales por ID/código,
  conserva las funcionales y los estados, y referencia el snapshot Git anterior
  de arquitectura como histórico satisfecho, no bloqueo actual.
- R2: README/ARCHITECTURE muestran ARCH-01..10/épica Done con aceptación en
  main/24484b7; la reapertura y sus resultados originales siguen en registros
  históricos. README documenta el rechazo temprano de seed.py y las rutas reales
  `basis/adapters/web/static/basis/brand/identity.json` y
  `basis/adapters/web/static/basis/css/tokens.css`.
- `docs/HANDOFF_PRESENTATION_2026-10-19.md` permanece untracked e intacto, fuera
  de esta entrega; no se modifica código ni snapshots de Linear.

El paquete documental queda preparado para la revisión de integración tras los
controles JSON/DAG/formato/diff. No se afirma commit, merge o CI futuro; MAM-617
permanece In Progress hasta la integración y su readback autorizado.

## Cierre operativo del lote

Registro histórico del lote de integridad del 2026-10-20; sus conteos y siguientes
tareas describen aquel momento. El estado posterior se registra por separado abajo.

Fuente: transcript local proporcionado de Luna, modelo `opencode-go/gpt-6-luna`,
agente `build`, sesión `ses_ea475a80dffeVXF8os2txyd0Cv`. No se consultaron
Linear/Notion en esta conciliación. [MAM-617](https://linear.app/mamutsystems/issue/MAM-617)
quedó Done el `2026-10-20T23:01:47.767Z` y Luna lo releyó a las
`23:01:57.740Z`; comentario `aee03067-082c-4e94-b8f6-8a7216d311db`.

El código se integró mediante [PR #1](https://github.com/Mamut1195/django_basis_trainning_app/pull/1),
merge `6c44307f81fe2bbd3f62f0742263bcf5ea1acd0a`. El
[CI post-merge 39511340583](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39511340583)
terminó success en ese mismo SHA: 260 PostgreSQL sin omisiones, 174 puras,
mypy 113/320 y ocho contratos, con formato/lint, Django/esquema/estáticos verdes.
Esta evidencia acredita la entrega de código de PR #1; no se atribuye a un
commit futuro de conciliación documental.

Estado del proyecto: **46 tickets = 16 Done, 29 In Progress, uno Backlog**.
Funcionales: **35 = cinco Done, 29 In Progress, uno Backlog** (30 abiertos).
Arquitectura: 11 Done. MAM-626/MAM-627 siguen In Progress: lector de pantalla
NOT RUN, aceptación humana PENDING. MAM-637 (High; depende de MAM-615/616/617)
y MAM-621 (Medium; depende de MAM-617/618) tienen sus dependencias satisfechas;
continúan In Progress y su alcance no se declara completado. No se cambian
dependencias ni se inicia su implementación en esta conciliación.

La [nota de cierre de integridad](HISTORY_INTEGRITY.md#cierre-operativo-mam-617-2026-10-20)
conserva fuente y detalles. `ROADMAP.json` refleja el nuevo estado;
`docs/architecture/linear-readback.json` permanece como snapshot anterior al
cierre. El CI propio de esta conciliación se verificará y reportará después de
su integración, sin prometer su resultado en estos documentos.

## Cierre del lote MAM-621 y MAM-637 (2026-10-21)

Conciliación documental a partir de los exports locales suministrados de Luna
REAL, modelo `opencode-go/gpt-6-luna`, agente `build`, sesión
`ses_ea3e2209dffehoFNLoBgWy77bW`:
`luna-closure-mam621-mam637-20261021-0139.final-readbacks.json` y
`luna-closure-mam621-mam637-20261021-0139.report.sanitized.md`, bajo Temp/opencode.
Este ejecutor documental no accede a Linear/Notion ni ejecuta cambios de estado.

**Ambos tickets ya estaban Done al llegar Luna.** Verificó los cuatro criterios
de cada uno y conservó sus estados y `completedAt`; corrigió dos comentarios de
preparación y dejó dos comentarios de cierre, con lectura posterior exacta.

| Ticket | Estado conservado / completedAt | Corrección del comentario inicial | Comentario de cierre |
| --- | --- | --- | --- |
| MAM-621 | Done / `2026-10-21T00:53:58.059Z` | `058dc6d7-ae69-4f6f-b208-fdb36255aa78`, actualizado `2026-10-21T01:47:28.436Z` | `14757265-2b57-44e4-b382-07cbca44b6c9`, creado `2026-10-21T01:47:28.696Z` |
| MAM-637 | Done / `2026-10-21T01:30:50.347Z` | `7c01152f-50a9-4dec-9ad3-d72cd3913570`, actualizado `2026-10-21T01:47:28.763Z` | `12f9062f-656f-4d04-b883-4098dca61bb8`, creado `2026-10-21T01:47:28.645Z` |

Las ramas realmente integradas son `feature/mam-621-catalog` y
`feature/mam-637-operations`. Los nombres `exec/*` de la preparación eran previstos,
no ramas creadas; los comentarios corregidos conservan esa previsión histórica.

### Integración y CI de código existentes

- **Catálogo / PR #3:** commit `e733e2c54eeb00092af9efd7fc1b19271c4b4841`,
  merge `158235c035dc442e008fe4e423442c8c955aba9b`;
  [CI postmerge 39524085686](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39524085686)
  SUCCESS en ese SHA: **276 PostgreSQL, 174 puras, mypy 113/323 y ocho contratos**.
  [Matriz de catálogo y readback](CATALOG_VERIFICATION.md#readback-de-integración-y-cierre-2026-10-21).
- **Operaciones / PR #4:** commit `55c10f2015ad88702a9ee8d9a1ffaf3d71648114`,
  integración conjunta `6bd14ea1539ebd671075562854a81f3ab852a5ac`,
  merge `5edf6bd515ed56289b76da3339c9acaa4a7d4680`;
  [CI postmerge 39527756424](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424)
  SUCCESS en ese SHA exacto, jobs `postgres` y `operations`: **288 PostgreSQL sin
  omisiones, 174 puras, mypy 113/330 y ocho contratos**. El
  [artefacto 12314030203](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39527756424/artifacts/12314030203)
  contiene once checks VERIFIED, incluido backup/restore de tablas/secuencias,
  migrate repetido y rollback de datos. [Detalle operativo](OPERATIONS_VERIFICATION.md#readback-de-integración-y-cierre-2026-10-21).

El APPROVE del flujo de implementación corresponde a revisión independiente de
agentes, no a un review formal de GitHub. La API de reviews de PR #3 y PR #4
devolvió **cero registros**; Luna no lo presentó como aprobación GitHub verificada.
Esta conciliación revisa evidencia existente, no reejecuta las pruebas de código
citadas. El CI propio del PR documental se comprobará y reportará por separado;
los resultados anteriores no se atribuyen a un commit documental futuro.

### Estado actual y siguiente cadena, sin iniciar otro lote

Fuente completa de Luna, sin página siguiente: **46 = 18 Done, 27 In Progress,
uno Backlog**; **35 funcionales = siete Done y 28 abiertos**; arquitectura **11 Done**.
`ROADMAP.json.current_readback` registra esta lectura y preserva `postmerge_readback`
de MAM-617 y los snapshots de arquitectura con sus estados/cantidades anteriores.

- MAM-626/MAM-627 continúan In Progress: lector de pantalla **NOT RUN**, aceptación
  del propietario **PENDING**.
- MAM-622 sigue bloqueado por **MAM-620**, que depende de **MAM-810**. MAM-623 espera
  **MAM-622**; cerrar MAM-621 no los desbloquea por completo.
- MAM-638 sigue bloqueado por **MAM-625, MAM-628, MAM-629, MAM-630, MAM-632,
  MAM-636, MAM-815, MAM-816, MAM-817, MAM-818 y MAM-820**: once pendientes;
  MAM-636 está Backlog. MAM-637 Done satisface sólo una de sus dependencias.
- Siguiente cadena High: **MAM-810 → MAM-620 → MAM-622 → MAM-623**. Es una
  recomendación de orden, no un inicio de implementación o cambio de estados.

Producción, proveedores LIVE y rollback entre releases con esquema incompatible
siguen **NOT RUN**. La carga de referencia no demuestra capacidad de 1.000 usuarios;
se conservan las mediciones anteriores con sus entornos y recibos propios.

# Risks

Windows sandbox TEMP/browser subprocess restrictions can prevent local execution; retain failed attempts and distinguish environment failures from product defects. Normalizing previously unvalidated ORM writes may expose invalid fixture inputs or uniqueness collisions. Do not delete or silently deduplicate old records. A viewport test does not replace a screen-reader or human UX review.
