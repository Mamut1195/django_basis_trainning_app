# MAM-638 — Auditoría local de dependencias, 2026-11-03

## Resultado y límites

Auditoría local recuperada para revisión de coordinación; **MAM-638 no se cierra**. Base `3ddb0e9b6ee893714dd0e81cf30647230b9d10eb`, rama `t3/mam638-dependency-audit`. El proyecto es un monolito modular Django con PostgreSQL; los requisitos Python y el lockfile npm son entradas separadas. No se cambiaron paquetes ni fuentes. La evidencia es una fotografía de los catálogos y resoluciones en las horas indicadas, no una garantía atemporal ni una evaluación de explotabilidad de la aplicación.

Los tres resultados Python reportan `certifi==2026.7.22` con dos objetos `PYSEC-2026-4320` cada uno. Tras deduplicar por identificador hay **un advisory**, no dos vulnerabilidades independientes. El exit 1 es hallazgo, respaldado por JSON y stderr, no un error de consulta. El reintento npm exit 0 reporta cero vulnerabilidades para su lockfile de un paquete de dependencia. El fallo TLS histórico **no se reprodujo en estas ejecuciones**; no se determinó su causa original. El primer intento npm falló antes de resolver configuración y no constituye un escaneo limpio.

## Contraste oficial del hallazgo

Consulta de fuentes primarias el 2026-11-03, aproximadamente 14:12 UTC: [PyPA PYSEC-2026-4320](https://github.com/pypa/advisory-database/blob/main/vulns/certifi/PYSEC-2026-4320.yaml), [advisory del proyecto certifi GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2) y [OSV](https://osv.dev/vulnerability/PYSEC-2026-4320). PyPA identifica GHSA como alias, introduce el rango en `2019.03.09` y lo corrige en `2026.10.18` exclusiva; incluye explícitamente `2026.7.22`. El proyecto clasifica la severidad como **crítica**; OSV muestra CVSS v4 **9.1**, vector `CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N`. Las claves comprometidas de CA intermediarias pueden facilitar interceptación TLS si el atacante está en el camino y el cliente confía en el bundle afectado. No se verificó que una ruta concreta de la aplicación sea explotable.

El mínimo corregido en el rango oficial y en el escáner es `2026.10.18`. PyPA y OSV recomiendan `2026.10.19` o posterior, que restaura raíces emSign no afectadas. Para un cambio posterior, evaluar esa recomendación, resolver y probar los requisitos y volver a auditar los artefactos/entornos realmente distribuidos; si se usan imágenes que incluyan certifi, reconstruirlas. **No se aplicó ni probó actualización alguna**. El advisory es de certifi, no una recomendación de cambiar Django o psycopg: en esta tarea no se evaluó compatibilidad de una actualización con ellos ni se acredita una versión alternativa de esos paquetes.

## Ejecuciones recuperadas

Todas son del agente anterior, no repetidas durante la recuperación. `pip-audit 2.10.1`, auditor aislado `.cache/dependency-audit-wave4/auditor`, servicio de vulnerabilidades PyPI, índice explícito `https://pypi.org/simple`, `PIP_CONFIG_FILE=NUL`; no se auditó el entorno del auditor como aplicación. La instalación real examinada fue `C:/Users/Jonnathan/Mamut system/django-basis-trainning-app/.venv-win/Lib/site-packages` (Python de aplicación 3.13.7). El runner filtra variables `PIP_`/`PIP_AUDIT_` o `NPM_CONFIG_`, sin leer configuración privada; usa cachés propias. Sus argv completos, cwd, inicio, fin y códigos están en los archivos `.meta.json` identificados por el manifiesto. Los comandos no contienen desactivación de validación TLS. La resolución de requisitos puede utilizar caché; éxito no explica retrospectivamente el error histórico.

| Alcance | UTC 2026-11-03 | Comando relevante | Resultado |
| --- | --- | --- | --- |
| Runtime declarado resuelto | 06:29:31–06:30:05 | `python -m pip_audit -r requirements.txt --index-url https://pypi.org/simple --vulnerability-service pypi --format json --progress-spinner off --cache-dir <audit-cache>` | exit 1; 23 paquetes; un ID único en certifi, duplicado en respuesta |
| Dev declarado resuelto, incluye runtime | 06:30:05–06:30:44 | igual con `-r requirements-dev.txt` | exit 1; 49 paquetes; mismo ID único duplicado |
| Instalación real | 06:31:15–06:31:17 | `python -m pip_audit --path <site-packages-app> --vulnerability-service pypi --format json --progress-spinner off --cache-dir <audit-cache>` | exit 1; 49 paquetes; mismo ID único duplicado |
| npm inicial | 06:30:44–06:30:45 | `npm audit --json --registry=https://registry.npmjs.org/ --include=dev` | exit 1; stdout vacío; error de doble carga del mismo `NUL` como configuración user/global. Sin resultado de auditoría |
| npm reintento | 06:31:02–06:31:15 | mismo argv, en copia aislada `npm-project` | exit 0; cero vulnerabilidades reportadas; metadata total 1, dev 1, prod 1 (categorías no sumables) |

Python y npm usaron catálogos públicos y configuración de herramienta aislada, sin `--fix`; npm reintentó con dos archivos de configuración vacíos distintos. Node `v22.19.0`, npm `10.9.3`, verificados durante recuperación. No se repitieron consultas de escaneo: los artefactos recuperados y el contraste oficial bastaron para este corte. `runtime.stderr` y `dev.stderr` además contienen avisos de ruta temporal de venv; `installed.stderr` no los contiene.

## Alcances, integridad y procedencia

**VERIFIED en recuperación**: el SHA256 del manifiesto es `082efa3cd0ad2cb90ee8d55580f24ad3a823789076d89810b12d55e67af5bfdb`; se recalcularon sus **26 entradas**, todas presentes y coincidentes. Es un índice de integridad local, no una firma ni prueba independiente de ejecución. Incluye los JSON, stderr y metadata de cada escaneo, inventario, binarios del auditor y logs de instalación/descarga. Conservados en `.cache/dependency-audit-wave4/`, ignorada por Git, junto a `run.py`, `retry.py` y salida del intento npm fallido. Los hashes concretos de cada log están en `manifest.json` para readback; no se sobrescribieron.

| Entrada | SHA256 |
| --- | --- |
| `requirements.txt` | `7e42388d5f31b384de924e4bf8f8a1a2ad1f43e2c6e0700b5335cbfda8a298a1` |
| `requirements-dev.txt` | `2d3d6f3c9b11cdeba0db21f248d509f9fcc424a3a800c7c62485d745f868b8f7` |
| `package.json` | `7ab43cb2bcd720467e0fc4b815a61c08f97544c3c12fa734b8d7c23a41a77c4b` |
| `package-lock.json` | `ad93ae9596bc938066a49100b1130180c149a1849b4da9377b74f37952df9de3` |
| wheel `pip_audit-2.10.1-py3-none-any.whl` | `99ef3f600a317c1945f1e89e227ef26e1c2d618429b8bd3fa6f4f7c440c4611a` |

La copia de ambos archivos npm usados para el reintento coincide byte a byte por SHA256 con las entradas anteriores. El lockfile v3 contiene `prettier==3.9.10` como única dependencia dev; la metadata del audit refleja un paquete total, y no prueba el estado de otros ecosistemas. Los JSON Python conservan la lista completa de nombres/versiones realmente consultados; no contienen un grafo de aristas de dependencia. Las 23 versiones runtime son las declaradas fijadas; dev incorpora runtime y seis herramientas declaradas, además de transitivas resueltas. La comparación normalizada de sus 49 nombres/versiones frente al JSON instalado encontró exactamente dos diferencias: `grimp` 3.18 resuelto frente a 3.17 instalado, y `types-pyyaml` 6.0.12.20261030 frente a 6.0.12.20260906; los otros 47 pares coinciden. No se atribuye identidad completa a ambos alcances. El inventario previo `app-inventory.json` tiene 49 pares y coincide con `installed.json`. La primera lectura exploratoria falló por tratar su BOM UTF-8 como JSON sin `utf-8-sig`; la lectura corregida y comparación se ejecutaron satisfactoriamente sin alterar el archivo.

## Estado de verificación

- **VERIFIED**: rama/SHA iniciales y árbol Git limpio; hashes de 26 entradas, identidad de copias npm, contenido y comparación de listas, salidas/códigos y contraste oficial indicados. Este readback verifica artefactos recuperados; no afirma haber ejecutado nuevamente los escaneos.
- **FAILED histórico preservado**: primer npm por configuración; no es hallazgo ni resultado cero. **FAILED en recuperación**: primera lectura exploratoria del inventario por BOM; luego resuelta mediante decodificación correcta.
- **NOT RUN**: actualización/remediación, prueba de compatibilidad tras actualización, repetición de escaneos, reproducción de la causa TLS histórica, pruebas de aplicación, suite, lint, typecheck, build, DB, Docker, servicios privados/proveedores IA/Polar, producción, CI/Actions, push/PR y escritura/cierre en Linear. Las pruebas de producto no se requieren para este cambio documental. Ninguna de estas ausencias constituye pase.
- **Pendiente**: revisión independiente de coordinación, decisión y ejecución separada de remediación, y validación del entorno/artefacto que corresponda. El resultado local no acredita integración ni cierre del ticket.
