# MAM-638 — remediación de certifi, 2026-11-03

Sustituye el pin vulnerable `certifi==2026.7.22` por `certifi==2026.10.23` en `requirements.txt`. `2026.10.23` es posterior a `2026.10.19`, la versión que PyPA y OSV recomiendan para [PYSEC-2026-4320](https://osv.dev/vulnerability/PYSEC-2026-4320) / [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2). No cambia Django, psycopg ni el resto de pines. MAM-638 sigue abierto: esto no es aceptación operativa ni cierre del ticket.

## Reauditoría

`pip-audit` 2.10.1, servicio de vulnerabilidades PyPI, índice `https://pypi.org/simple`, sin `--fix`. Auditor aislado en `.cache/certifi-reaudit-20261103/`. El intérprete de la app quedó en `certifi` 2026.10.23.

| Alcance | Paquetes | certifi | Hallazgos | Código |
| --- | --- | --- | --- | --- |
| `requirements.txt` | 23 | 2026.10.23 | 0 | 0 |
| `requirements-dev.txt` | 49 | 2026.10.23 | 0 | 0 |
| `.venv-win` instalado | 49 | 2026.10.23 | 0 | 0 |

Salidas JSON, SHA-256: runtime `2af69a10463b65869abb17cbe78010723c4171a7c1180d303e1ac1d2927eb470`; desarrollo `b5a1f225d8feae9b7d894f9a8f570343e444df2c5b32841a8d7427f236de7d19`; instalación `57ad174bf952ede7b802bc00bb12a441b04d3761b82033913991eb98c0afc0d9`.

La suite conjunta de 1.095 casos sigue atribuida a `efa9c4c`, antes de este pin. El gate remoto de esta versión es el CI del PR. Polar sandbox, aceptación humana/deportiva, dispositivos y cierre de tickets no forman parte de este cambio.
