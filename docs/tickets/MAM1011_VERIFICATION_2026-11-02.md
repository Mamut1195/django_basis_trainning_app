# MAM-1011 — política activa de main, 2026-11-02

La política acordada para un desarrollador único se aplicó por la API de GitHub y se verificó mediante GET independiente. El repositorio es público y la cuenta conectada tiene permiso administrativo; no se crearon credenciales ni se concedieron accesos.

## Política verificada

- `main.protected=true`.
- Pull request requerida, cero aprobaciones obligatorias.
- Sin CODEOWNERS obligatorio ni aprobación del último push por otra cuenta.
- Checks `postgres` y `operations`, ambos de GitHub Actions (app_id 15368).
- `strict=true`: el candidato debe estar actualizado respecto de main.
- Conversaciones resueltas antes de integrar.
- Force push y borrado de main deshabilitados.
- `enforce_admins=true`: coordinación sigue el mismo flujo PR/checks.
- Rama no bloqueada; sin requisito nuevo de historial lineal.

La recuperación administrativa conserva el acceso ya existente de administración a la API de protección. Si un incidente exige cambiar la política, registrar motivo, valores anteriores/nuevos y restablecimiento; esta vía no es el flujo normal de integración. No se añadió bypass permanente ni otra identidad.

## Evidencia real

Antes: GET de main sobre `d3501a78b37050cfc352af175b898a5aa9a4f11b` devolvió protected=false; listado de rulesets vacío. El CI existente [41544841064](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/41544841064) tenía operations success y postgres failure en architecture_check. No se disparó un CI nuevo para estas consultas.

PUT `repos/Mamut1195/django_basis_trainning_app/branches/main/protection` terminó correctamente después de corregir dos errores de transporte/forma: HTTP422 al enviar contexts y checks juntos, y HTTP400 por BOM UTF-8 generado por PowerShell. Ninguno se reportó como éxito. La petición final usa solo checks; archivo UTF-8 sin BOM.

GET independiente de protección y GET de main confirmaron todos los valores anteriores. Petición/respuesta/readback locales en `.cache/wave0-20261102/main-protection-*.json`. Esos archivos no contienen tokens ni se incluyeron en Git. Esquema consultado en [GitHub Docs](https://docs.github.com/en/rest/branches/branch-protection#update-branch-protection).

**VERIFIED:** política activa y lectura independiente, nombres/app exactos, cero revisión externa obligatoria y restricciones indicadas. No se reescribió main ni se publicaron commits como parte de este cambio.

**NOT RUN:** intento de integrar una PR con check fallido y aceptación de PR propia válida bajo la política nueva. Esas pruebas deben usar candidatos existentes, sin forzar un fallo destructivo, gastar CI sin autorización ni omitir protecciones. MAM-1011 no se declara Done todavía; la protección activa no sustituye ese criterio de aceptación. Tampoco cierra MAM-1008/638.

