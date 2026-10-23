# BASIS · Mapa de recorridos portables

MAM-626 · [Abrir el HTML local](prototipo/index.html) · [Guía y verificación](STYLE_GUIDE.md). Complemento del [contrato del producto](../UX_CONTRACT.md), no reemplazo de las rutas Django. Todos los ejemplos son ficticios, sin servidor ni proveedor IA. **Recargar o cerrar borra los cambios.**

## Navegación estable

`Hoy (#hoy) → Plan (#plan) → Progreso (#progreso) → Entrenador (#entrenador)` conserva orden y marca actual. Entrenamiento (`#entrenamiento`) pertenece a Hoy. Los enlaces usan hashes locales; al cambiar de vista, el foco llega a `main`. El primer Tab ofrece «Saltar al contenido». Cambiar tema o estado no navega ni mueve inesperadamente el foco.

## Cinco recorridos mínimos

| Flujo | Pasos y control de decisión | Resultado local observable |
| --- | --- | --- |
| 1 · Inicio | Abrir `index.html` → Hoy → leer aviso y siguiente sesión → Comenzar demo | Acceso sin cuenta a un fixture explícito. No simula alta, verificación de correo ni autorización. |
| 2 · Entrenamiento | Hoy → Comenzar demo → tres fieldsets de sentadilla → introducir rep/carga/RPE/RIR reales por serie → cardio medido → Conservar en memoria demo | Prescrito visible separado. Resumen «No enviado». Vacío sigue siendo Sin datos; escribir 0 produce cero. Las observaciones se conservan en la pestaña, no se completan automáticamente. |
| 3 · Reprogramación | Hoy → Reprogramar (Plan) → nueva fecha → Aplicar fecha solo en demo → Hoy | Misma fecha en Plan/Hoy, sin POST ni revisión remota real. Cancelar no aplica la fecha sin enviar. No altera observaciones. |
| 4 · Progreso | Navegación → Progreso → distinguir historial fijo y registro de esta pestaña → Volver al registro | Conteos ficticios sin cálculo, estimado/medido y 0 m/Sin datos visibles. No sumar historial fijo con la sesión de la pestaña. |
| 5 · Propuesta IA | Entrenador → comparar plan original/propuesta → consultar Plan sin aceptar → volver → Rechazar o Aceptar cambio en plan demo | La consulta y el rechazo no alteran el plan. Solo Aceptar cambia el futuro plan ficticio a B. Registro A congelado intacto. Restaurar permite volver al original; no existe generación IA ni éxito de servidor. |

En entrenamiento, los inputs se mantienen como borrador válido en memoria al navegar. La acción explícita muestra el resumen de registro; no constituye guardado duradero. Una fecha nueva solo se aplica al enviar su formulario. La aceptación se aplica únicamente mediante su botón. Restaurar propuesta conserva las observaciones de la sesión A. Recargar restablece todo (datos, fecha, propuesta y tema).

```text
Abrir file://
  └─ Hoy ── Comenzar demo ── Entrenamiento A ── conservar memoria (no enviado)
       ├─ Reprogramar ── Plan ── aplicar fecha demo ── Hoy
       ├─ Progreso ── historial fijo / registro de pestaña
       └─ Entrenador ── revisar propuesta ficticia
                         ├─ consultar / rechazar ── plan sin cambio
                         └─ aceptar explícitamente ── plan futuro B en memoria
                                                      └─ restaurar ── plan A
```

## Selector de estados · transversal a las cinco vistas

El selector no consulta ni detecta la red; es un control de revisión. Navegación, tema y selector siguen disponibles para salir del estado. Ningún timer produce una transición automática a éxito.

| Valor | Presentación | Acciones y salida |
| --- | --- | --- |
| Normal | Contenido ficticio y aviso persistente | Recorrer los flujos; sigue sin persistencia ni envío. |
| Vacío | Explicación sin datos/porcentajes/recomendaciones; contenido oculto | Volver a Normal para recuperar el ejemplo, no «crear» datos de servidor. |
| Cargando | Ejemplo detenido, `aria-busy=true` en el contenedor y contenido oculto | Selector → Normal; no peticiones ni éxito automático. |
| Error | Mensaje explícito; entradas en memoria conservadas | Acciones de escritura bloqueadas. Volver a Normal restablece exploración, no reintenta red. |
| Sin conexión | Estado ilustrativo y advertencia de pérdida | Se permite ensayar memoria. No almacenamiento duradero, descarga, envío ni confirmación. |
| Sincronización pendiente | Explica que el producto esperaría un recibo de servidor | No cola ni sincronizador. Normal no confirma ni elimina una operación remota. |
| Conflicto | Copia local ficticia y copia remota ilustrativa con fechas/revisiones distintas | Bloquea acciones de escritura; no elige copia por defecto ni sobrescribe. Volver a Normal solo abandona la ilustración. Resolución de conflicto real fuera de alcance. |

Cada cambio anuncia texto en `role=status`, `aria-live=polite`, `aria-atomic=true`. El error del selector no es una validación de campos de servidor. La validación del formulario es nativa HTML, con etiquetas explícitas y límites ilustrativos; no sustituye las reglas deportivas del dominio.

## Comprobación a cargo del coordinador

La CLI documentada en STYLE_GUIDE recorre los cinco flujos, comprueba aceptación explícita/rechazo, fecha, observaciones por serie, pérdida al recargar y estados. Audita todas las vistas/estados a 390/1440 px en claro/oscuro como registros DOM acotados; genera únicamente las cuatro capturas de Hoy requeridas. No usa recursos externos y aborta solicitudes inesperadas. El informe registra fallos reales, no convierte limitaciones ni estados incompletos en PASS.

Estado al entregar fuentes: **automatización NOT RUN; revisión independiente PENDING; aprobación humana PENDING; lector de pantalla NOT RUN; dispositivo físico NOT RUN**. El coordinador debe comprobar informe, fuentes exactas y PNG antes de solicitar revisión. La revisión humana debe incluir comprensión de datos ausentes, separación de sesión A/plan futuro B, pérdida en memoria, error/conflicto, orden Tab y barra inferior móvil. No cerrar el ticket a partir de este documento o de un eventual PASS de screening.

## Evidencia posterior a la entrega inicial

El coordinador ejecutó los cinco recorridos, los siete estados y las 140 combinaciones: preparación **VERIFIED**, con cuatro capturas y pruebas negativas del auditor. Véase [VERIFICATION.md](VERIFICATION.md) para comandos, hashes, alcance y limitaciones. Esto actualiza el NOT RUN histórico anterior, no constituye aceptación humana ni sincronización de servidor. Aprobación del propietario **PENDING**; lector de pantalla y dispositivo físico **NOT RUN**.
