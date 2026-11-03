# MAM-1008: conciliación de la épica de estabilización

## Ámbito

La épica agrupa cuatro correcciones acotadas: aislamiento de pruebas Polar, finales de línea Windows, protección de main y conciliación documental/retirada segura de worktrees. Sus descripciones conservan apartados históricos superados. La aceptación integral permanece en MAM-638 y el sandbox real en MAM-816; no se amplía la épica para duplicarlos.

## Readback actual

Linear devolvió exactamente cuatro hijos, sin más páginas. Los cuatro están **Done**:

| Hijo | Evidencia de integración y cierre |
| --- | --- |
| MAM-1009 | Aislamiento del mock y guard de red; PR26 integrada en `b1882dab6b4856185cb06bf8d37f28488e75f9e5`; CI de PR y posterior completos según su recibo. |
| MAM-1010 | Reglas LF acotadas, formato real y tipado; mismo lote PR26 y main. |
| MAM-1012 | Snapshot/README/ROADMAP/PENDIENTES por PR33; archivo y retirada de siete worktrees originales acreditados en su recibo. Los worktrees nuevos y el trabajo pendiente se preservan; no se repiten borrados. |
| MAM-1011 | Política PR/checks, cero aprobaciones externas; rechazo real de candidato fallido e integración normal de candidato válido por PR35, `ca87ebebea43c2fde990110e92e11c8aaba56884`. |

Se leyeron las cuatro descripciones completas y la lista de comentarios de la épica (vacía, sin más páginas). No se modificaron ni volvieron a ejecutar sus implementaciones.

## Comprobaciones independientes actuales

- `git rev-parse main`, `git rev-parse origin/main` y `git ls-remote origin refs/heads/main`: mismo `ca87ebebea43c2fde990110e92e11c8aaba56884`.
- GET GitHub `commits/ca87ebebea43c2fde990110e92e11c8aaba56884/check-runs`: `postgres` y `operations`, ambos `completed/success`, mismo SHA. Ejecución existente `41565972061`; no se disparó ni repitió CI remoto.
- GET `branches/main/protection`: `strict=true`, checks `postgres`/`operations` de app15368, aprobaciones0, enforce_admins activo, conversaciones resueltas requeridas, force-push y borrado desactivados.
- El log de main contiene las integraciones PR26, PR33 y PR35; el cierre usa evidencia ya recibida en main, no el lote IA local posterior.

## Dictamen

**VERIFIED: alcance de los cuatro subtickets completado y recibido en main.** No se identificó trabajo técnico propio adicional de esta épica en su alcance registrado. Procede conciliar su estado preservando íntegro el historial. El cambio del tracker debe dejar explícitos los gates externos de MAM-638/816 y la publicación congelada de633/634.

**NOT RUN en esta conciliación:** pruebas de implementación repetidas, CI nuevo, producción, pagos/IA LIVE, nueva limpieza de worktrees o aceptación integral. Las pruebas de los hijos y el CI histórico se atribuyen a sus recibos; aquí solo se releyeron estado, SHA, checks y política.

Los tres documentos ajenos untracked se mantienen intactos. La rama633/634 sigue en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`; esta conciliación no publica ese código ni cierra los tickets funcionales que aún requieren aceptación.

## Cierre remoto confirmado

Se antepuso el recibo de conciliación a la descripción de MAM-1008, conservando todo el historial, y se cambió únicamente su estado a **Done**. GET posterior independiente confirmó Done y `completedAt=2026-11-03T05:51:17.381Z`. Los dos enlaces de evidencia de main se comprobaron también con `git cat-file -e`: `docs/CORRECTIONS_2026-11-01.md` y `docs/tickets/PR35_ORDERING_VERIFICATION_2026-11-02.md`. La referencia inicial a un recibo posterior al merge se corrigió antes del readback final; no se presenta ese documento local como contenido de main.

Readback completo del proyecto, sin más páginas: **51 tickets, 43 Done, siete In Progress y uno Backlog; ocho abiertos**. No se cerró ningún otro ticket ni se modificaron dependencias, identidades o fechas de los subtickets.
