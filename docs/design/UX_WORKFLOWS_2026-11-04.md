# Flujos de revisión UX — 2026-11-04

Recorridos para probar la propuesta y la app, y decidir si cada flujo está bien o mal.
Cada flujo tiene un objetivo, pasos, resultado esperado y **señales de fallo**.

- Prototipo: [mockup/propuesta.html](mockup/propuesta.html)
- Propuesta: [UI_UX_PROPOSAL_2026-11-04.md](UI_UX_PROPOSAL_2026-11-04.md)
- App real: `https://app.basisasesoria.fitness`

## Cómo se revisa

1. Haz el flujo completo sin ayuda. Si necesitas adivinar, ya falló.
2. Anota: qué esperabas, qué viste, captura y severidad (bloquea / molesta / cosmético).
3. Un flujo está **bien** si puedes completarlo sin pensar y la app confirma cada paso.
4. Está **mal** si:
   - no sabes qué sesión estás viendo o qué hay que llenar;
   - al tocar un botón no pasa nada visible;
   - la app cambia de pantalla sin explicar por qué;
   - pierdes datos o no sabes si se guardaron;
   - un dato faltante se muestra como cero o se inventa;
   - tienes que volver atrás para corregir un error de validación.

## A. Hoy y registro

### H1 · Entender qué toca hoy

- **Precondición:** hay una sesión en curso.
- **Pasos:** abrir Hoy; mirar la tarjeta principal.
- **Esperado:** deporte, nombre, objetivo y estado visibles; una sola acción primaria
  (“Registrar”).
- **Fallo:** solo hay un título azul; no se sabe si es running, fuerza o hiking; hay dos
  listas con la misma sesión.

### H2 · Registrar una sesión completa

- **Pasos:** Registrar → “Usar objetivo” → escribir RPE → “Guardar y completar”.
- **Esperado:** confirmación inmediata, cifras (duración, RPE, carga) y estado “Completada”.
- **Fallo:** el editor abre vacío sin decir qué sesión es; guardar no muestra nada; la
  pantalla vuelve a la lista sin confirmación.

### H3 · Registrar sin conexión y reabrir

- **Pasos:** descargar la sesión; modo avión; abrir “Sesiones guardadas”; registrar;
  guardar; cerrar la app; reabrirla sin red.
- **Esperado:** “Guardado en este dispositivo. Se enviará al volver la conexión”; los
  valores siguen ahí al reabrir.
- **Fallo:** los campos se vacían; aparece otra pantalla; el mensaje no dice si quedó
  guardado.

### H4 · Sincronizar al volver la red

- **Pasos:** quitar modo avión; esperar; abrir la lista.
- **Esperado:** la tarjeta pasa a “Sincronizada”; el recibo existe; no se duplica.
- **Fallo:** sigue “Pendiente” sin explicación; se crean dos registros; el botón
  “Reintentar envío” no hace nada visible.

## B. Plan

### P1 · Revisar la semana

- **Pasos:** Plan → cambiar de semana con ← / → → volver con “Hoy” → tocar un día.
- **Esperado:** “Cargando semana…” y luego la semana; el día seleccionado muestra sus
  sesiones; el estado dice qué día estás viendo.
- **Fallo:** la página recarga entera; no se sabe qué semana es; el día no responde.

### P2 · Añadir una sesión

- **Pasos:** “Añadir sesión” → nombre, disciplina, minutos, día → Guardar.
- **Esperado:** la sesión aparece en el día; confirmación; si falta el nombre o los minutos,
  el aviso está en el campo.
- **Fallo:** guarda sin avisar; el error aparece lejos del campo; la sesión no aparece.

### P3 · Mover u omitir una sesión (app real)

- **Pasos:** abrir una sesión programada → editar / reprogramar / omitir o sustituir.
- **Esperado:** el cambio pide motivo, crea versión nueva y no altera lo ejecutado.
- **Fallo:** el cambio borra historial o no explica qué pasó.

### P4 · Comparar versiones

- **Pasos:** Plan → Versiones → “Comparar con v2”.
- **Esperado:** antes/después legible y “Comparación calculada”.
- **Fallo:** solo lista versiones sin diferencias.

## C. Progreso

### G1 · Cambiar el período

- **Pasos:** Progreso → 30 días / Semana / Rango / Todo.
- **Esperado:** “Actualizando…” y luego la línea del período; las cifras corresponden.
- **Fallo:** recarga sin aviso; el período mostrado no coincide con los datos.

### G2 · Leer datos faltantes sin engaños

- **Pasos:** revisar una disciplina sin volumen o sin RPE.
- **Esperado:** “Sin datos” o “sin volumen todavía”, nunca 0; cobertura explicada.
- **Fallo:** muestra 0 como si hubiera medido; suma deportes distintos.

### G3 · Exportar

- **Pasos:** “Exportar mis datos”.
- **Esperado:** botón “Preparando…”, luego archivo o aviso claro.
- **Fallo:** nada visible; descarga sin nombre.

## D. Entrenador

### E1 · Consultar (con IA habilitada)

- **Pasos:** escribir → “Consultar entrenador”.
- **Esperado:** deshabilitado sin texto; “Enviando…”; tarjeta pendiente con segundos.
- **Fallo:** botón activo con texto vacío; doble envío; no hay estado pendiente.

### E2 · Consulta pendiente y cancelación

- **Pasos:** enviar → cancelar antes de que empiece.
- **Esperado:** “Cancelada · reserva recuperada”; la consulta sigue en la lista con estado.
- **Fallo:** cancelar deja la reserva; no se puede cancelar aunque no haya empezado.

### E3 · Revisar una propuesta

- **Pasos:** abrir una consulta de tipo plan → “Revisar”.
- **Esperado:** diff claro y acciones aceptar / editar / descartar; nada se aplica solo.
- **Fallo:** la propuesta entra al calendario sin aceptación.

## E. Transversal

### T1 · Estados vacíos

- **Pasos:** cuenta nueva: Hoy, Plan, Progreso, Entrenador, Sin conexión.
- **Esperado:** cada pantalla dice qué hacer para empezar.
- **Fallo:** pantallas en blanco o textos técnicos.

### T2 · Validación

- **Pasos:** guardar con nombre vacío, duración 0, rango con fecha inicial mayor, consulta
  vacía.
- **Esperado:** mensaje junto al campo y foco en el campo.
- **Fallo:** error genérico arriba; no se sabe qué corregir.

### T3 · Navegación y actualización

- **Pasos:** moverse entre las cinco secciones con y sin conexión.
- **Esperado:** la sección activa se marca; no hay recargas completas; al volver a la app
  no aparecen pantallas anteriores.
- **Fallo:** se pierde el contexto; la app “salta” a otra pantalla; el botón Atrás del
  teléfono sale de la app.

## Matriz de cobertura

| Flujo | Prototipo | App real |
| --- | --- | --- |
| H1, H2 | Hoy, Registrar | `/` y `/sessions/<id>/` |
| H3, H4 | Sin conexión | `/offline/` |
| P1, P2, P4 | Plan | `/plans/`, `/plans/<pk>/calendar/` |
| P3 | — | `/scheduled/<pk>/editor/<action>/` |
| G1–G3 | Progreso | `/progress/` |
| E1–E3 | Entrenador | `/coach/` |
| T1–T3 | Todas | Todas |

## Registro de revisión

| Flujo | Esperado | Observado | Severidad | Captura |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

Severidad: **bloquea** (no puedo terminar), **molesta** (lo hago con esfuerzo),
**cosmético** (no impide).
