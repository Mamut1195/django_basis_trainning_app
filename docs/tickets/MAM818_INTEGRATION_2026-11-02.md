# MAM-818: integración local de coordinación

## 1. Goal

Integrar la serie MAM-818 aprobada en el conjunto local con MAM-633/634/635 y comprobar su compatibilidad. No cerrar tickets ni publicar.

## 2. Context

Coordinación parte de `eca958b`; el candidato fuente es `361bd3ad7698f58a2f53ecc283e54463e785f133`, posterior a las correcciones R1–R4. La revisión independiente R7 aprobó la serie sin P1/P2, ejecutando 84 pruebas PostgreSQL sin omisiones y cuatro pruebas propias. Esas ejecuciones pertenecen al revisor.

## 3. Constraints

La decisión del usuario mantiene la tanda MAM-633/634 congelada en `codex/basis-context-proposals-20261102`, `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`. No push, PR, Actions, LIVE, pagos, producción ni conciliación de datos existentes. Preservar los tres documentos untracked ajenos. PostgreSQL compartido no se detiene ni reinicia.

## 4. Affected areas

Solo los commits propios de la serie MAM-818 desde `fb9c17e`: jobs, proveedor, persistencia, migraciones coach 0002/0003, CLI de conciliación y sus pruebas/recibos. Las fuentes de contexto/propuestas y la interfaz MAM-635 se conservan como base de la integración.

## 5. Implementation steps

1. Incorporar los doce commits fuente en orden, conservando procedencia y la reproducción roja seguida de su corrección.
2. Revisar el diff y ejecutar primero focales coach/propuestas/aceptación en PostgreSQL exclusivo; resolver cualquier incompatibilidad antes de ampliar a la suite completa.
3. Ejecutar tipos, pruebas puras, arquitectura, imports, lint y comprobaciones Django/migraciones sobre el candidato estable.
4. Completar este recibo con SHA, comandos, resultados, fallos y límites; confirmar que la rama congelada y los archivos ajenos siguen intactos.

## 6. Required skills

`task-planning`, `safe-git-workflow`, `verify-before-complete`; `systematic-debugging` si aparece un fallo de causa desconocida.

## 7. Validation

Python `.venv-win`, PostgreSQL 18.4 local puerto 55482, solo `basis_wave3_integration` y su base temporal de pruebas. Settings y cuentas sintéticas, AI deshabilitada salvo fixtures, proveedores mediante MockTransport y HTTP externo bloqueado por el runner. Registrar por separado las ejecuciones del implementador, revisor y coordinación.

## 8. Risks

La barrera abierta conserva indefinidamente la reserva si el worker nunca retorna; es la política autorizada. Un despliegue futuro exige detener y cercar workers anteriores antes de migrar. No se ejecuta ese despliegue aquí. La cancelación de jobs MAM-635 sigue pendiente y no forma parte de esta integración. Las pruebas de bloqueo acreditan intercalados concretos, no todos los posibles.

## 9. Procedencia y resolución de integración

Los doce commits se incorporaron en orden en `codex/basis-wave3-20261102`:

| Fuente MAM-818 | Integración |
| --- | --- |
| `8db5360` | `b3f1e77` |
| `bef2654` | `73a1f1f` |
| `4fc0e81` | `49139fe` |
| `a2b596f` | `177834f` |
| `216d54f` | `c9160c2` |
| `cd9fa88` | `77f8b94` |
| `129ff4c` | `1e4ff0f` |
| `1639fd6` | `0384561` |
| `fa4f2ef` | `dceaae6` |
| `12ab729` | `8cefb23` |
| `463dc93` | `6e20beb` |
| `361bd3a` | `635bd9d` |

Hubo un conflicto en `provider.py` al aplicar `216d54f`: se conservaron tanto la validación de la política/modelo congelados de MAM-818 como la procedencia de instrucciones de MAM-633. Comparando los archivos propios de la serie con `361bd3a`, solo difiere ese archivo por el guard de instrucciones ya presente en coordinación. No se copió código de contexto/propuestas desde la rama fuente de MAM-818.

El commit propio `cecea65419dd5e9782805b39e6b317a207a0107c` adapta nueve llamadas antiguas de las regresiones MAM-633 al parámetro obligatorio `pricing`. La política del fixture permite explícitamente su modelo sintético. La prueba comprueba en el mismo contexto v2 rechazo de modelo no permitido, instrucciones obsoletas y exceso de presupuesto antes de HTTP. No se debilitó el contrato para aceptar llamadas sin snapshot.

## 10. Revisión independiente

R7: `node:delegated-task:command%3Amcp%3A15931406-e044-4eca-b54e-e427b8e0839b%3Adelegate-task%3Abasis-wave3-818-r4-fence-independent-review-20261102-r7`. Dictamen **APPROVE**, sin P1/P2 en el ámbito revisado, sobre el SHA fuente completo. Sol ejecutó 84 focales PostgreSQL y cuatro pruebas propias en su base exclusiva; no son ejecuciones de coordinación.

Recibo local: `C:/Users/Jonnathan/.t3/worktrees/django-basis-trainning-app/t3-8cf5fdb3/.cache/mam818-review-r7/REVIEW.md`. Coordinación comprobó los hashes del recibo para `focal.log` (`38B30AA6419D9D0BD7BB408BA71B4B59F12853A583FA7C5C2204B3F6F86E23C3`) y `own-tests.log` (`BF41CCFBB22035B4E8F271978B2BD0CFFF12CDE8494B067FD3FC2A928EEAB32D`). R7 no repitió la suite completa, tipos o lint global del ejecutor.

## 11. Verificación de coordinación

El candidato funcional final es **`cecea65419dd5e9782805b39e6b317a207a0107c`**. No hubo cambios en el código durante las ejecuciones completas. Este recibo y sus referencias se completaron después; sus cambios son documentales.

| Comprobación ejecutada | Resultado |
| --- | --- |
| Focal integrada: seis módulos de jobs/ledger, propuestas MAM-634 y aceptación MAM-635; código `635bd9d` | **VERIFIED**: 122 pruebas, cero omisiones, 60.115 s, salida 0. |
| Regresiones de contexto MAM-633, procedencia RM y revisión MAM-634; código final | **VERIFIED**: 21 pruebas, cero omisiones, 2.982 s, salida 0. |
| Suite Django completa con PostgreSQL; código final | **VERIFIED**: 1.047 casos, 1.038 satisfactorios y nueve omitidos, 689.853 s, salida 0. Incluye las focales anteriores. |
| Pruebas puras `tests_architecture` | **VERIFIED**: 278 pruebas, 7.193 s, salida 0; anteriores al cambio exclusivo de regresiones Django. No sumar estos casos a la suite como pruebas únicas adicionales. |
| Mypy core / Django | **VERIFIED**: 133 / 432 archivos sin errores. Django se repitió tras adaptar los fixtures. |
| Arquitectura / Import Linter | **VERIFIED**: límites/public/legado y ocho contratos conservados, cero rotos. |
| Ruff | **VERIFIED**: check global y formato de los 18 archivos Python afectados fuera de migraciones. |
| Django check / migraciones | **VERIFIED**: sin incidencias y `makemigrations --check --dry-run` sin cambios. Migraciones reales aplicadas y sus regresiones ejecutadas en la base temporal. |
| Guard del runner final | **VERIFIED**: HTTPX sync/entrada async, TCP externo y conexión PostgreSQL a otra base rechazados antes del transporte; PostgreSQL 18.4 confirmado. |
| Cierre de base temporal | **VERIFIED**: proceso completo terminó y `test_basis_wave3_integration` ya no existe. No se detuvo PostgreSQL ni se migraron datos existentes de la aplicación. |

Las nueve omisiones son de navegador optativo: hiking (1), MAM-632 offline (4), PWA general (1), running (1), swimming (1) y trekking (1). No hubo omisiones en las focales PostgreSQL de MAM-818.

### Fallos previos y correcciones

- **FAILED, corregido:** mypy Django inicial detectó nueve llamadas sin `pricing` en las regresiones de MAM-633; se corrigieron en `cecea65` y se repitieron tipos y pruebas.
- **FAILED de alcance del comando, sin cambio de código:** pasar rutas explícitas a Ruff format incluyó la migración 0002, excluida por la configuración del repositorio. El control final respeta esa exclusión; no se reformateó la migración revisada.
- **FAILED del runner, corregido:** primera suite completa, 1.047 casos en 392.559 s, dos fallos y nueve omisiones. El runner adaptado de R7 permitía sockets solo al puerto PostgreSQL, bloqueando `ReferenceSMTPTests.test_real_django_smtp_transport_to_owned_loopback_sink` y `OfflineTransactionDisconnectTests.test_tcp_reset_after_write_before_commit_and_idempotent_retry`. Ambas trazas terminan en el guard de sockets. Se conservó el runner inicial, se permitió únicamente loopback para servicios sintéticos y se mantuvo la restricción psycopg a las dos bases exclusivas. Los dos casos pasaron (1.534 s), el guard final pasó y la suite completa se repitió con éxito sin modificar la aplicación.

El guard protege las entradas Python indicadas; no es un cortafuegos del sistema ni una garantía de aislamiento de cualquier proceso descendiente. Los ensayos usan datos sintéticos y ningún proveedor LIVE.

## 12. Comandos y artefactos locales

Ejecutar desde el checkout de coordinación, con su base exclusiva existente. `$python = './.venv-win/Scripts/python.exe'` y `$runner = '.cache/wave4-818-20261102/run_guarded.py'`:

```powershell
& $python -B $runner manage test basis.bootstrap.tests.test_coach_jobs basis.bootstrap.tests.test_coach_edges basis.bootstrap.tests.test_coach_provider_policy basis.bootstrap.tests.test_coach_reconciliation basis.bootstrap.tests.test_coach_pricing_migration basis.bootstrap.tests.test_coach_attempt_fence basis.bootstrap.tests.test_mam634_proposals basis.bootstrap.tests.test_mam635_acceptance --noinput -v 1
& $python -B $runner manage test tests.regression.test_coach_context_633 basis.bootstrap.tests.test_mam634_rm_provenance basis.bootstrap.tests.test_mam634_review_regressions --noinput -v 1
& $python -B $runner unittest discover -s tests_architecture -q
& $python -B $runner mypy --config-file mypy-core.ini
& $python -B $runner mypy --config-file mypy-django.ini
& $python scripts/architecture_check.py
& $python -B $runner script .cache/wave4-818-20261102/check_imports.py
& $python -m ruff check .
$files = @(git diff --name-only --diff-filter=ACM eca958b cecea65 -- '*.py' | Where-Object { $_ -notmatch '[/\\]migrations[/\\]' })
& $python -m ruff format --check $files
& $python -B $runner manage check
& $python -B $runner manage makemigrations --check --dry-run
& $python -B $runner script .cache/wave4-818-20261102/verify_guard.py
& $python -B $runner manage test --noinput -v 2
git diff eca958b..HEAD --check
```

Runner y logs se conservan localmente en `.cache/wave4-818-20261102/`, ignorados por Git; no estarán presentes en un clon nuevo. SHA256:

| Artefacto | SHA256 |
| --- | --- |
| `run_guarded_pg_only.py` (inicial) | `3B67DC8561037831CA7B7F0B47FC26440FBF226C23F8F883EB043D36C492C2EA` |
| `run_guarded.py` (final) | `A4CAA3E1A2410249E1AFEB60F2648C8B7FEFD468F9FCB8130EE2E7CDBDE8DC0E` |
| `verify_guard.py` | `31B8323FA7637C6069AB5F0478B348BE1FC20E0918DD75038189B6EB5E543CCA` |
| `focal.log` | `312E6ED23552B0DF681DD91A7CBE4F368D3999122021BB87E4B4410D8D7A0D2D` |
| `context-proposals.log` | `1D63E304D229A7283B353F0F6669B037DFF65AAB58F3F0B640796C69127CB816` |
| `pure.log` | `B038FD10FEE7691D04A4D1AB5B9CAADA66291D6364B145EFA6BE2A6959D5E1AA` |
| `mypy-core.log` | `677E10B795E3ED9930041CB2474A6E2C2AE35E28EFAB0C9C086D6BF04223271D` |
| `mypy-django-final.log` | `19C7B299B152965F5D14F84CE7A6A765DFA4FF9C0B653301AB88BFAD8675388A` |
| `full.log` (fallido) | `52FEB42C809E855CFC69603E23163A400CE0388BEC0C2A4B4AEB7061CF06C4CF` |
| `local-services.log` | `BC7732B31E012D36E10D48D977528E7CC25B10297AEE84D6822A451170D4AD3E` |
| `guard.log` | `F72B26D3A9152C704BAD17F6C5472BBEB6936A7667F4B1A5BADAF5C2AD2B1680` |
| `full-final.log` | `2BB6A2856820CBB9823775FC748EDAE54E46E06296EA05DFE9CAC0DFA986EDAA` |

## 13. Estado y límites de entrega

**VERIFIED LOCAL / NO PUBLICADO.** Integración y compatibilidad locales comprobadas. MAM-818 y MAM-635 siguen abiertos; la cancelación de jobs sigue pendiente. La retención indefinida de un intento sin retorno sigue siendo una limitación deliberada.

**NOT RUN:** CI remoto, push, PR, cierre o edición de tickets, IA/precios LIVE, pagos, conciliación de datos existentes, producción, despliegue con workers antiguos, suite SQLite separada, repetición de navegador sobre este conjunto integrado, lector de pantalla, dispositivo físico, modo avión y aceptación deportiva humana. No se presume que las pruebas de navegador anteriores a MAM-818 acrediten esta integración.

La rama congelada permanece exactamente en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`. Los tres documentos ajenos untracked se preservan y no se añaden al índice. Los commits fuente y de integración permanecen como historial; no se reescribió ni descartó trabajo.
