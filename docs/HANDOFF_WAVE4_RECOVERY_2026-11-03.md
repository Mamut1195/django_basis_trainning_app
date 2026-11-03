# Handoff Wave4 — recuperación local verificada, 2026-11-03

El avance local autorizado quedó implementado, revisado e integrado en `codex/basis-wave3-20261102`. Árbol fuente probado: **`efa9c4c1fad4c9038ea6d6d736daed860251cbe9`**; código636 final `3a3c0cd`, equivalente en contenido Git al candidato aprobado `a676e37`. El commit documental de este handoff solo actualiza documentación. No se publicó ni se cerraron tickets.

## Resultado por frente

| Requisito de la goal | Evidencia autoritativa actual |
| --- | --- |
| Recuperar las tareas canceladas preservando trabajo | Readback en WAVE4_PLAN; nuevas R4/R2/R6/R7 con ownership y bases separadas; fallos originales conservados |
| Integrar y validar MAM-635 | `f2aeb68` + `6df2c4d`; revisión independiente APPROVE;113 focales; navegador T3; suite previa1074 y final1095 |
| Terminar las correcciones636 y revisarlas antes de integrar | R1–R6 en `c07becc`; nuevo R5-N1 en `3a3c0cd`; R7APPROVE para `a676e37`,21 focales y20 controles propios;89 hashes verificados; incorporación posterior al dictamen |
| Completar y revisar auditoría638 | Informe `8806f70`,26 hashes verificados y advisory contrastado con fuentes primarias; sin actualizar paquetes |
| Validar la combinación final | Suite1095 y checks finales sobre HEAD estable efa9c4c; mapa364 fuentes y equivalencia LF/CRLF comprobados |
| Evidencia fiel y handoff | Recibos versionados; manifiesto103 artefactos; este archivo y readback Git del commit documental |
| Preservar límites y trabajo ajeno | Rama congelada f42b861 intacta; tres documentos ajenos untracked; sin publicación, Actions, producción ni cambios remotos de estado |

La auditoría638 confirma un advisory único crítico en certifi2026.7.22, duplicado en las salidas del scanner. **Su remediación sigue pendiente**: el alcance aprobado fue auditar y proponer, sin actualizar paquetes. Detalles, rangos, fuentes y límites en [MAM638_DEPENDENCY_AUDIT_2026-11-03.md](tickets/MAM638_DEPENDENCY_AUDIT_2026-11-03.md). npm reportó cero hallazgos solo para su lockfile de un paquete.

## Validación final y límites

**VERIFIED:**1095 casos en468.546s,1085 satisfactorios,10 omisiones optativas,0 fallos/errores;exit0. Mypy135/441 fuentes;Ruff/formato452 archivos;arquitectura;8 contratos de imports;Django check y migraciones sin cambios. Las diez omisiones son navegadores optativos: hiking, cuatro casos offline632, multisport632, PWA, running, swimming y trekking. Se preservan como omisiones, sin sumarlas a aprobadas.

Navegador635 se ejecutó en T3 con servidor/fixtures propios: login, pending→cancelada mediante POST real, recarga persistente, costo0,sin formulario/polling ni overflow;1280×800 y390×844. El código de producto/templates/assets es idéntico al actual según Git. Móvil es viewport de escritorio, no dispositivo físico. El conflicto409 se repitió con cliente Django. DjLint,Prettier,collectstatic y benchmark de consultas también pasaron dentro de esta recuperación; conservan su atribución en el recibo.

Harness636: SIMULATED,5/17 casos ejecutados;7/34 expectativas técnicas PASS,3INCONCLUSIVE,24NOT_RUN;89 observaciones PASS,3INCONCLUSIVE,0FAIL. **0 casos aceptados deportivamente**. Human/sport PENDING,rúbrica PROPOSED_NOT_APPROVED,LIVE/final acceptance NOT_RUN. El GREEN de los tests mutados acredita detección de contradicciones, no defectos del producto intacto ni calidad del modelo.

**NOT RUN / fuera del cierre local:**push/PR/Actions/CI remoto, Docker/imagen/operaciones, remediación y reauditoría certifi, Polar sandbox pospuesto por el usuario, dispositivo físico/lector de pantalla, EV001–012,LIVE/REPLAY/calidad deportiva o revisión humana y cierre de tickets. Docker Desktop Linux engine no estaba disponible. Estas ausencias no son PASS ni permiten declarar preparación de producción.

## Evidencia y procedencia

Registro completo de comandos, revisiones, commits, hashes, fallos y correcciones: [WAVE4_RECOVERY_INTEGRATION_2026-11-03.md](tickets/WAVE4_RECOVERY_INTEGRATION_2026-11-03.md). Contrato y evolución: [WAVE4_PLAN_2026-11-03.md](tickets/WAVE4_PLAN_2026-11-03.md).

Evidencia propia ignorada en `.cache/wave4-recovery-20261103/`:

- `full-final636.log`:SHA256 `1a8afa0d6c036e5599093219c0622944c59c71c56483fce0c849d3cc33033e83`;metadata JSON conserva mismo HEAD antes/después.
- `artifact-manifest-final.json`:103 entradas,SHA256 **`9100236ead1f7fba8531a4324888228168676a3a3227f72cb0371573c1bf0b4c`**. Incluye reportes baseline/negativos,logs,metadata,scripts y fallos; excluye cachés mypy y log vivo PostgreSQL, con snapshot propio incluido.
- `scope-audit.json`:auditoría ejecutada antes de escribir este handoff; comprueba integración,checks,conteos,origen de fuentes,revisión89 entradas y preservación. Deja el handoff pendiente del readback Git posterior; no se usa como prueba circular de este archivo.
- `source-provenance.json`:364 fuentes comparadas,43 diferencias solo por LF/CRLF,0 diferencias adicionales. Se conservan ambos hashes crudos; no se reescribieron fuentes/reportes. Git normaliza con core.autocrlf=true.

Revisión R7 en `C:/Users/Jonnathan/.t3/worktrees/django-basis-trainning-app/t3-b2aa5a24/.cache/mam636-review-r7/`:REVIEW SHA256 `043dba2e13d92416ab608d2cf92c429eb7cf9fd13f249d655da4ee05f6908eb1`;manifiesto89 entradas `ccbb1b750f97d009953d9803f70d9281f9417e22660b5dd0c789f3f6f9ac076a`. R5 rechazado y todos sus controles se conservan en `t3-19a75c82/.cache/mam636-review-r5/`. No borrar esos worktrees/cachés. Los artefactos ignorados y capturas T3 no estarán en un clon nuevo.

## Estado preservado y continuación

PostgreSQL18.4 compartido sigue en127.0.0.1:55482, usuario sintético basis_wave0. Coordinación usa solo `basis_wave3_integration`/`test_basis_wave3_integration`; la test DB se destruyó en el teardown normal de la suite. Se conserva la base principal con fixtures sintéticas. El servidor web propio8767 se detuvo. Los runners de autores/revisores conservan otras DB exclusivas; para coordinación se usa su runner propio, sin acceder a aquellas.

Rama congelada `codex/basis-context-proposals-20261102` en **`f42b86160c0afe3a545488fd07f0e5dd8a61a15f`**. Se preservan ajenos y sin stage: `docs/HANDOFF_2026-11-01_MAM625_DONE_MAM820_WIP.md`, `docs/HANDOFF_PRESENTATION_2026-10-19.md`, `docs/RELEASE_REVIEW_2026-11-01.md`. No reset/clean/stash/force-push ni reescritura de historia.

Para una repetición local autorizada desde esta raíz, usar destinos nuevos para no sobrescribir evidencia:

```powershell
$py=(Resolve-Path .venv-win/Scripts/python.exe).Path
$runTag=Get-Date -Format 'yyyyMMddTHHmmss'
$env:MAM636_ATTEMPT='rerun-'+$runTag
$env:MAM636_REPORT='.cache/wave4-recovery-20261103/rerun-'+$runTag+'.json'
$env:MAM636_FIX_EVIDENCE='.cache/wave4-recovery-20261103/rerun-mutants-'+$runTag
& $py -X utf8 -B .cache/wave4-recovery-20261103/capture.py ('rerun-'+$runTag) $py -X utf8 -B .cache/wave4-recovery-20261103/run_guarded.py manage test --noinput -v 2
```

Los siguientes trabajos requieren conservar sus propios alcances: remediar/re-auditar certifi con compatibilidad verificada; preparar Polar sandbox cuando el usuario lo disponga; ejecutar aceptación operativa/humana/dispositivos y gates remotos antes de publicación o cierre. No se inicia ninguno de ellos como parte de este handoff.
