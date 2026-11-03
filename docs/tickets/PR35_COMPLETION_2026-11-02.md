# PR35 — integración y conciliación de aceptación

[PR35](https://github.com/Mamut1195/django_basis_trainning_app/pull/35) se integró normalmente, con head fijado a8d0ebcce8f91ab7639bd35862762fac5f6954ca6, sin admin/auto/bypass. Merge en main: **ca87ebebea43c2fde990110e92e11c8aaba56884**, 2026-11-03 02:24:56 UTC (2026-11-02 en Guayaquil). Las dos ejecuciones push41564430891 y pull_request41564437021 tenían postgres y operations SUCCESS; estado CLEAN/MERGEABLE y cero conversaciones pendientes.

[CI posterior en main41565972061](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/41565972061): **SUCCESS** sobre ese SHA, postgres/operations,639 pruebas PostgreSQL OK con9 omisiones opt-in, tipos, arquitectura, formato, benchmark, collectstatic, build y arranque de imagen de referencia contra base desechable. Se consultaron estado, pasos y líneas de log de la suite. No acredita producción ni proveedor LIVE. Main local, origin/main y refs/heads/main remoto coincidieron en ca87ebe; el árbol funcional de la rama de continuación no difiere de main en este corte (solo documentación adicional).

Se preservó el fallo de la primera ejecución pull_request41562700397 sobre c9646c2 y su reproducción/corrección en PR35_ORDERING_VERIFICATION_2026-11-02.md; el aviso automático de checks aprobados no bastó para integrarlo. El ensayo negativo de MAM-1011 rechazó la integración normal de ese candidato fallido antes del arreglo; no se omitió la política.

## Readback de Linear

MAM-815, MAM-630 y MAM-1011 se actualizaron a **Done** con recibos enlazados a este SHA de main y se releyeron los tres estados. Se preservaron los apartados históricos; el cierre vigente los distingue explícitamente.

- MAM-815: servicios multideporte, procedencia, métodos, faltantes, fechas observadas y presentación verificados sin equivalencias ni doble conteo. Su alcance es manual; no se afirma GPS, wearables o proveedor LIVE.
- MAM-630: fuentes y alternativas textuales, valores ausentes distintos de cero, gráficos separados y legibles en móvil emulado, teclado probado, filtros/vacío/error, ajustes y exportación privada. Se mantienen NOT RUN lector de pantalla real, dispositivo físico y auditoría exhaustiva/capacidad; no se presentan como esas ejecuciones las pruebas de viewport/texto.
- MAM-1011: política activa releída, rechazo concreto del flujo normal por CLI y aceptación propia después de checks correctos, sin otra cuenta ni bypass. El rechazo no se presenta como una mutación REST HTTP405 enviada directamente.

MAM-632 sigue abierto: las pruebas locales ampliadas, incluido TCP antes del commit, no sustituyen todos los dispositivos/escenarios de su aceptación. MAM-633/634/818 conservan objeciones en corrección/revisión; MAM-635/636/816/1008/638 mantienen sus criterios restantes. Ningún cierre parcial de IA ni activación comercial/producción se deriva de esta PR.

## Continuación

633 reprodujo PostgreSQL40P01 en el orden inverso de sport_insert/profile_archive; corrige orden cuenta→perfil y fecha del propietario antes de nueva revisión. 634 conserva ef6e5ee y a4254d6 (rechazo RM no consultadas) y atiende NaN/estado oculto en comparación; aún falta nueva fuente633 e integración. La segunda revisión818 cerró transporte congelado y aritmética inicial, pero reprodujo pérdida de observación de tokens enormes y comparación de tipos en downgrade; se solicitaron nuevos fixes antes de integrarlo. Estos cambios no están en ca87ebe ni heredan su CI.
