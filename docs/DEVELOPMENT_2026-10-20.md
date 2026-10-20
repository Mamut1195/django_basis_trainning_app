# Goal

Reconcile and accept the published architecture, then complete BASIS-004/MAM-617 data integrity and advance BASIS-012/MAM-626 with a reviewable UX contract.

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

Estado actual: código aprobado en la revisión independiente final; [readback y
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

# Risks

Windows sandbox TEMP/browser subprocess restrictions can prevent local execution; retain failed attempts and distinguish environment failures from product defects. Normalizing previously unvalidated ORM writes may expose invalid fixture inputs or uniqueness collisions. Do not delete or silently deduplicate old records. A viewport test does not replace a screen-reader or human UX review.
