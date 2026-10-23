# BASIS · Mapa de recorridos portables

MAM-626 · [Abrir el HTML local](prototipo/index.html) · [Guía y verificación](STYLE_GUIDE.md). Complemento del [contrato del producto](../UX_CONTRACT.md), no reemplazo de las rutas Django. Todos los ejemplos son ficticios, sin servidor ni proveedor IA. **Recargar o cerrar borra los cambios.**

## Referencia actual · R2 + onboarding · 23 de octubre de 2026

Esta sección reemplaza las decisiones de presentación iniciales, no la evidencia histórica que se conserva más abajo. **R2: gates, contraste medido, teclado automatizado y nuevas capturas NOT RUN en esta asignación. Auditor R2 pendiente de asignación separada; revisión independiente BT2 PENDING; revisor externo, aprobación humana, lector de pantalla y dispositivo físico NOT RUN.** La evidencia anterior no acredita este candidato.

### Navegación y jerarquía

Se mantienen las cinco rutas originales y los cuatro destinos Hoy / Plan / Progreso / Entrenador. La barra móvil fija tiene iconos decorativos `aria-hidden` y texto; espacio inferior, safe-area y scroll-margin permiten desplazar controles por encima de ella. La navegación por hash mueve foco a `#main`. El tema solo cambia tokens.

La insignia «Demo ficticia» siempre está visible. `#demo-tools` es un details nativo, cerrado inicialmente; su resumen abre la advertencia completa de datos ficticios y memoria, el selector de siete estados y `#onboarding-link` hacia `#bienvenida`. La región global `#announcement` conserva aria-live cortés, visualmente oculta para priorizar la sesión.

| Recorrido R2 | Pasos | Resultado y límites |
| --- | --- | --- |
| Hoy | Abrir → `#today-session` → `#start-training` «Comenzar» | Una sesión A, una acción dominante de ancho completo. Prescripción A y cardio estimado separados del próximo plan futuro. Resumen semanal compacto debajo. Objetivo 390×844: sesión y CTA sobre la barra; pendiente de captura y medición. |
| Entrenamiento A | Comenzar → tabla `#sets-table` serie/kg/reps/RPE/check → completar observaciones → `#check-N` | Inputs inicialmente vacíos. Texto «Anterior ficticio» separado, nunca autocompletado. Para marcar se exigen kg/reps/RPE válidos; cero es observado, vacío es ausente. RIR real opcional y prescripción accesibles en details por serie. |
| Serie y descanso | Marcar → «Realizada», aria-pressed=true → descanso ilustrativo de 90 s | Marca solo tras validar la fila. Sus inputs quedan bloqueados hasta desmarcar explícitamente. Un deadline y como máximo un intervalo en memoria sobreviven a navegación. Solo cambia texto del reloj: no rerender de inputs mientras se escribe. Anuncia inicio/fin, no cada segundo. Omitir solo termina descanso; nunca completa ni envía series/sesión. |
| Conservar registro | Introducir cardio medido → Conservar en memoria demo | Resumen «No enviado». No exige completar todas las series, no inventa valores ni sincroniza. Prescrito 20 min separado de duración/distancia medidas. |
| Plan | Tira `#week-strip` → Reprogramar → fecha → Aplicar o Cancelar | Siete días ficticios, lunes 19 a domingo 25 de octubre de 2026; viernes 23 es hoy ficticio fijo. `#reschedule-details` cerrado al entrar, `#show-reschedule` lo abre. La nueva fecha solo se aplica al enviar. Cancelar restaura el borrador y cierra sin aplicar; navegar sin enviar tampoco aplica. Fechas fuera de la tira no se presentan como hoy ni se desplaza la semana silenciosamente. |
| Progreso | Historial fijo → registro de pestaña | No mezcla conteos ilustrativos con observaciones actuales; mantiene Sin datos distinto de 0. |
| Entrenador | Comparar → consultar/rechazar/aceptar → restaurar | Solo aceptación explícita cambia el futuro plan B; ni consultar ni rechazar modifican el plan. Restaurar recupera A. La sesión de hoy y el registro A nunca se convierten en B. `data-plan-name` y `data-plan-date` identifican el próximo plan en Hoy/Plan; Entrenador conserva `data-plan-name`. |
| Bienvenida | Herramientas demo → `#onboarding-link` → `#bienvenida` → `#open-registration` | Explica intención y límites, permite seguir a Hoy sin registro. No exige cuenta para los recorridos originales. |
| Registro | `#registro` → `#signup-form` → nombre/email/contraseña ficticios + select de mayoría de edad → `#signup-submit` | Labels explícitos, required, email nativo, nombre mínimo 2 y contraseña ficticia mínimo 8 caracteres. Validación cliente nativa: corrige el campo indicado y reintenta; fallo no crea resultado ni borra los demás campos. No uses credenciales reales. |
| Resultado de alta demo | Envío válido → `#signup-result` → Volver a Hoy | Texto explícito: NO cuenta creada, NO correo enviado, NO sincronización de servidor; solo resultado en memoria. Se resetea el formulario y se borra contraseña. El objeto demo solo registra un booleano, nunca nombre/email/contraseña; no los refleja ni registra en informes. Navegar elimina los inputs y limpia contraseña. Recargar elimina todo. |

### Siete estados, seguridad y recuperación

Normal, vacío, cargando, error, sin conexión, sincronización pendiente y conflicto siguen siendo ilustraciones seleccionables, nunca detección real de red. Vacío/cargando ocultan contenido; error/conflicto bloquean edición y acciones, incluidos checks y alta demo. Volver a Normal no convierte nada en éxito remoto ni cambia una serie marcada. Inputs de series realizadas permanecen protegidos al cambiar de estado. Offline/pendiente permiten memoria sin prometer durabilidad. El descanso puede terminar mientras se mira otra ruta/estado, pero su fin no modifica observaciones ni marca ni envía nada. Selector/tema/navegación siguen permitiendo recuperación.

### Contrato para la siguiente asignación de auditoría

Conservar verificaciones previas y ampliar recorridos, sin rebajar umbrales: details global cerrado, badge visible; Hoy/CTA arriba de barra a 390×844; tabla real y campos inicialmente vacíos; fila inválida no marcada, recuperación, check >=48×48, texto pendiente/realizada, RIR independiente; edición bloqueada y protección de filas realizadas en siete estados; deadline que sobrevive a navegación, un intervalo máximo y sin autoenvío; semana correcta y cancelación sin aplicar; bienvenida/registro con errores corregibles, no exfiltración/almacenamiento/reflejo de credenciales, contraseña vacía tras envío/navegación y pérdida al recargar; propuesta/rechazo/restauración y separación A/B intactas. Medir texto >=4.5:1 incluso pequeño >=14 px, controles y foco, overflow/oclusión y teclado en ambos temas. Regenerar Hoy 390/1440 y añadir Plan/bienvenida/registro a 390 en claro/oscuro en un destino de evidencia nuevo, sin sobrescribir PNG históricos. No registrar valores de credenciales en informes. Ninguna de estas pruebas se ejecutó aquí.

## Historia preservada · entrega inicial anterior a R2

Las descripciones siguientes son históricas: Comenzar demo, fieldsets y formulario de fecha expuesto se sustituyen por las decisiones R2 anteriores.

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

El coordinador ejecutó los cinco recorridos, los siete estados y las 140 combinaciones: preparación **VERIFIED**, con cuatro capturas y pruebas negativas del auditor. Véase [VERIFICATION.md](VERIFICATION.md) para comandos, hashes, alcance y limitaciones. Esto actualiza el NOT RUN histórico anterior, no constituye aceptación humana ni sincronización de servidor. Aprobación del propietario **PENDING**; lector de pantalla y dispositivo físico **NOT RUN**. Esta evidencia es anterior a R2 y no acredita los cambios actuales.
