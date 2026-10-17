# Contrato de variables deportivas

`training/domain.py` es la definición ejecutable de unidades, variables admitidas y validaciones; los formularios web y offline derivan del mismo diccionario. Un campo sin datos significa desconocido. Cero solo representa un cero registrado.

| Área | Variables principales |
|---|---|
| Perfil | Edad adulta, experiencia por disciplina, objetivos fechados y con unidades, disponibilidad semanal, minutos por sesión, equipo y limitaciones declaradas. |
| Fuerza | Ejercicio, variante, patrón, músculos, equipo, orden, tipo de serie, carga externa/corporal/asistida, repeticiones fijas o rango, objetivo/real, % RM medido con referencia fechada, RPE/RIR, descansos, tempo, ROM, lado, isometría y circuito/superserie. |
| Cardio/running | Duración, distancia, ritmo derivado, tipo, superficie, intervalos, repeticiones y descanso; ascenso/descenso y FC/cadencia opcionales en running. |
| Ciclismo | Interior/exterior, duración, distancia, desnivel, intervalos, potencia W y cadencia rpm medidas, FC y umbral con unidad/fecha/método. No se calcula potencia a partir de velocidad. |
| Natación | Duración, distancia, ritmo por 100 m, estilo, longitud de piscina, largos, repeticiones, descansos, técnica y brazadas opcionales. |
| Hiking | Distancia m, tiempo transcurrido/activo/pausas s, ascenso y descenso acumulados por separado, altitudes inicial/máxima/final m, terreno, dificultad declarada con escala/grado/fuente, mochila kg decimal y equipo. |
| Trekking | Agrupación de sesiones de hiking por etapa ordenada y fechada; mochila en sus bloques, altitud de pernocta y recuperación entre jornadas. |
| Bienestar | Sueño h/calidad, fatiga, estrés, dolor muscular, disposición percibida, regiones/intensidad de dolor y notas; FC reposo/HRV medidas opcionales con método. |

Las restricciones validan, entre otras cosas, que movimiento más pausas no exceda duración, que la altitud máxima incluya inicio/final, que las referencias RM no sean ajenas/futuras y que no se inserten resultados reales en una prescripción.

## Métricas

- Volumen externo de fuerza: kg externos × repeticiones reales por serie. Las cargas corporales/asistidas no se suman como si fueran equivalentes.
- 1RM estimado: Epley únicamente para series de trabajo externas con 1–10 repeticiones y esfuerzo máximo declarado; se identifica como estimación, con redondeo decimal explícito. No se infiere RPE desde un porcentaje RM.
- Ritmo: duración/distancia, por km en running y por 100 m en natación; sin distancia positiva y duración conocida no hay ritmo.
- Carga interna: minutos × RPE real de sesión, en unidades arbitrarias. Solo se compara el mismo protocolo de duración. No es una equivalencia fisiológica exacta ni una predicción de lesiones.
- Los totales del bloque son autoritativos: no se suman además sus intervalos. Trekking agrega bloques de hiking de etapas completadas; ni pernoctas ni la entidad del viaje generan otra carga.
- La adherencia compara sesiones programadas hasta hoy con ejecuciones completadas; las versiones no duplican sesiones ya ejecutadas.

No hay ACWR como predictor de lesiones, porcentaje universal de mochila segura, grado de dificultad inferido ni datos de sensores inventados. Esta entrega registra datos manuales y no implementa GPS ni wearables.

## Referencias de alcance

[Foster: método session-RPE](https://pubmed.ncbi.nlm.nih.gov/11708692/), [consenso sobre seguimiento de cargas](https://pubmed.ncbi.nlm.nih.gov/28463642/) y [limitaciones de interpretar ACWR](https://pubmed.ncbi.nlm.nih.gov/32502973/) orientan la separación de datos observados y estimaciones. La [clasificación SAC](https://www.sac-cas.ch/en/ausbildung-und-sicherheit/tourenplanung/grading-systems/) es un ejemplo de escala declarada con fuente; la app no asigna sus grados automáticamente. Las recomendaciones de [UIAA Mountain Medicine](https://www.theuiaa.org/mountain-medicine/medical-advice/) no se sustituyen por una puntuación automática.
