# Handoff para otro harness — 2026-11-03

Continuar desde `origin/main`. No reabrir la recuperación Wave 4 ni volver a auditar `certifi`. El trabajo de producto que sigue está abajo, en orden.

## Código vigente

| Qué | Dónde |
| --- | --- |
| Repositorio | https://github.com/Mamut1195/django_basis_trainning_app |
| `main` | `9e575e08b0edd8690b19979b17e22fcd406af392` |
| Árbol probado por CI del último producto | `b31120afc132e2d18b44a05418f4d11919ac5915`, ancestro de ese merge. `git diff b31120a 9e575e0` estaba vacío |
| Release | [v2026.11.03](https://github.com/Mamut1195/django_basis_trainning_app/releases/tag/v2026.11.03) apunta a `7ab90de2f49c148128f3fb85cf38dc0a4503bf0a` (PR 36). No incluye el PR 37 |
| PR 36 | https://github.com/Mamut1195/django_basis_trainning_app/pull/36 fusionado. Wave 4 local más `certifi==2026.10.23` |
| PR 37 | https://github.com/Mamut1195/django_basis_trainning_app/pull/37 fusionado. Decisión de la próxima semana por session-RPE |

Este documento viaja en el PR 38, rama `docs/handoff-20261103`. Todavía no está en `main`. El producto a retomar es `origin/main` en `9e575e0`. La rama `codex/coach-session-rpe-20261103` se quedó en `b31120a` y no hay que seguirla.

`AI_ENABLED` sigue en 0. No se llamó a DeepSeek. No hay etiqueta nueva después de v2026.11.03.

## Qué ya hace el entrenador

Regla determinista en `basis/modules/coach/domain/adaptation.py`. No usa proveedor ni base de datos. La carga de una sesión completada es minutos × RPE de sesión (Foster 2001; la función existente es `internal_load`).

Casos que ya pasan en `tests_architecture/test_coach_adaptation.py`:

- Hiking 10.800 s a RPE 4 = 720.00 UA. Ciclismo 3.600 s a RPE 6 = 360.00 UA. No se suman a 1.080. Se protege el hiking y hay una sola progresión de ciclismo.
- RPE ausente: pregunta y la carga es `None`, no cero.
- Tiempo total y tiempo en movimiento del hiking no se fusionan.
- Dolor: no hay propuesta; pide detenerse y valoración profesional.

La instrucción del proveedor es `basis-coach-633-v3` en `basis/modules/coach/domain/prompts.py`. Una consulta corta tiene límite de 4.000 bytes (`short_limits` en `basis/modules/coach/domain/jobs.py`). La primera redacción medía 4.056 en `test_short_preparation_accepts_a_minimal_real_projection_without_http` y se acortó en `b31120a`. No subir ese límite para hacer caber texto.

## Orden para seguir

1. **Polar sandbox (MAM-816).** El MCP de Polar no estaba conectado. Pedir al usuario que lo conecte en T3. No pedir ni pegar tokens en el chat. Alcance: checkout desde la app, tarjeta de prueba, webhook, conciliación, prueba de siete días, USD 5, cancelación, impago, reembolso y revocación. Preflight que lo dejó bloqueado: `docs/tickets/MAM816_PREFLIGHT_2026-11-03.md`. Sandbox, no producción.
2. **Aceptación de lo ya construido.** Offline en un teléfono (MAM-632), progreso en pantalla (MAM-630), carga multideporte (MAM-815) y aceptación de trekking (MAM-820; el código entró por el PR 34). Hace falta usar la app. No inventar otro backend.
3. **Salida (MAM-638).** Correo real, respaldo externo restaurado, dominio y despliegue. `certifi` ya está en 2026.10.23. Eso no cierra el ticket.
4. **Llamar al modelo.** Solo con la regla ya en `main` y comparando la respuesta contra los mismos atletas sintéticos. 0 casos aceptados deportivamente. La rúbrica humana no está aprobada. No encender IA para “ver qué dice”.

## Límites que no se negocian

- No sumar cargas de deportes distintos ni de protocolos `elapsed` y `moving`.
- No usar ACWR para predecir lesiones, no inventar zonas, vatios, citas ni resultados.
- Dolor agudo o síntomas en altura: detener y pedir valoración. No programar rehabilitación.
- Un cambio de plan es una propuesta hasta que la persona lo acepta. No reescribir lo ya ejecutado.
- No cerrar tickets de Linear solo porque el código está en `main`.
- No force-push, reset, clean ni stash. Conservar sin stage estos tres archivos ajenos: `docs/HANDOFF_2026-11-01_MAM625_DONE_MAM820_WIP.md`, `docs/HANDOFF_PRESENTATION_2026-10-19.md`, `docs/RELEASE_REVIEW_2026-11-01.md`.
- Rama congelada de contexto, si aún existe: `codex/basis-context-proposals-20261102` en `f42b86160c0afe3a545488fd07f0e5dd8a61a15f`. No moverla.
- `main` exige PR y los checks `postgres` y `operations`.

## Comprobación mínima

Desde la raíz, sin leer `.env`:

```powershell
.venv-win/Scripts/python.exe -m unittest tests_architecture.test_coach_adaptation -q
```

Eso no sustituye el CI del PR que se vaya a abrir. PostgreSQL de desarrollo, si se repite la suite, no es el servicio compartido que haya que detener.

## Lectura previa, no volver a ejecutarla

- Recuperación local anterior a la release: `docs/HANDOFF_WAVE4_RECOVERY_2026-11-03.md`. Su frase de “certifi pendiente” quedó superada por el PR 36.
- Contrato de carga: `docs/TRAINING_CONTRACT.md` y `docs/TRAINING_VARIABLES.md`.
- Roadmap y pendientes del 2026-11-02 están viejos respecto de `main`.
