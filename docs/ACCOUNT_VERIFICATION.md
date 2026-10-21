# MAM-810 / BASIS-025 — cuentas privadas y correo verificable

## Alcance y aceptación

La fuente viva de Luna del 2026-10-21 exige alta de adultos, verificación
caducable, recuperación sin enumeración, límites de intentos, perfil privado,
aislamiento entre dos cuentas y no vincular perfiles heredados por coincidencias
no verificadas. Exige pruebas de verificación, recuperación, expiración y CSRF.
SMTP real se documenta separadamente y **no es gate de aceptación de MAM-810**.
La aceptación técnica local por sí sola no equivale a integración ni cierre. **Readback actual: MAM-810 Done**, `completedAt=2026-10-21T04:35:13.492Z`, conservado por Luna. Se integró en [PR #6](https://github.com/Mamut1195/django_basis_trainning_app/pull/6), merge `58cbb0ea2e7421a696629391cb8a5eebf2df76fe`; [CI postmerge 39544853138](https://github.com/Mamut1195/django_basis_trainning_app/actions/runs/39544853138) SUCCESS:318PG/174puras, mypy113/335 y ocho contratos. El [cierre de cadena](DEVELOPMENT_2026-10-21.md#cierre-de-la-cadena-mam-810--620--622--623) distingue esta evidencia integrada de los registros locales siguientes y no atribuye una nueva transición a Luna.

## Ciclo de vida

`basis_accounts.EmailVerification` distingue `pending`, `verified` y `disabled`.
Sólo el caso de registro explícito crea una autorización pendiente, en la misma
transacción que cuenta inactiva, atleta, preferencias y billing vacío. No inicia
sesión, no activa una suscripción y no vincula perfiles anteriores.

El enlace firmado conserva `/accounts/verify/<token>/` y caduca a las 24 horas.
GET sólo presenta la confirmación. POST exige CSRF, bloquea primero la cuenta
con `SELECT FOR UPDATE`, admite únicamente estado pendiente y consume esa
autorización junto con la activación y verificación del atleta. Reutilizarlo o
reenviar a una cuenta verificada/deshabilitada no permite activarla otra vez.
Desactivar mediante un guardado normal de auth revoca también el estado pendiente;
la administración y verificación toman los bloqueos en el mismo orden.

La migración conserva cuentas, contraseñas, perfiles e historial. Las cuentas
inactivas anteriores no contienen información suficiente para distinguir alta
pendiente de desactivación administrativa: quedan `disabled`, sin autorización
implícita para autoactivarse. Sus enlaces antiguos dejan de autorizar activación.
Un operador debe revisar esos casos y autorizar explícitamente la activación y
verificación mediante la administración existente. No inferir permiso por correo,
PK, ausencia de login o perfil no verificado. SQL/bulk updates no ejecutan señales:
una operación administrativa de bajo nivel sobre una cuenta pendiente debe
revocar su estado dentro de la misma transacción; no usar un `UPDATE is_active=false`
sobre una fila que ya era inactiva como sustituto de esa operación.

## Recuperación, fallos y privacidad

Se preserva el generador de reset de Django y su caducidad configurada por Django,
la selección de cuentas activas con contraseña usable y la invalidación tras
cambiar la contraseña. Cambiarla invalida sesiones existentes. Confirmación y
logout conservan los controles CSRF del framework.

La confirmación usa una extensión mínima de la vista y formulario de Django.
Después de la validación inicial del formulario, abre una transacción en el alias
de la instancia cargada, bloquea y vuelve a leer la cuenta. Requiere cuenta activa,
contraseña usable, lifecycle `verified` y token todavía válido contra esa fila
fresca. La validación sensible a atributos de usuario también se repite sobre la
fila fresca. Sólo entonces guarda `password`, nunca `is_active`, privilegios ni
otros campos de una instantánea anterior. Una desactivación completada antes del
lock prevalece; dos POST simultáneos con el mismo token sólo permiten un consumo.

Se conserva el dispatch de Django: el enlace original se guarda en la sesión
`_password_reset_token` y redirige a `set-password` sin exponer el secreto en el
Referer. GET no cambia credenciales ni activa cuentas. El éxito conserva el destino
de Django y limpia el token de sesión sin login automático; una autorización que
ya no es válida muestra el estado inválido de la misma plantilla y elimina su
token de sesión. No se reemplaza el generador ni su caducidad y no se amplía la
autoridad de otras APIs de auth. La activación administrativa explícita es una
operación distinta: un guardado automático de contraseña nunca puede realizarla
ni sustituye la revisión de un lifecycle deshabilitado.

Alta duplicada/colisión con perfil heredado no crea ni vincula filas; devuelve el
mismo aviso recuperable. Un fallo de transporte durante el alta revierte todas
sus filas. El aviso no afirma que la cuenta fue creada ni que SMTP aceptó el
mensaje: permite volver a intentar registro, verificación o recuperación.
Reenvío y recuperación mantienen respuesta pública equivalente para dirección
conocida/desconocida también ante errores de transporte esperados.

Los errores son observables como eventos contables:
`account event=verification_delivery_failed` y
`account event=password_recovery_delivery_failed`. No registran destinatarios,
IDs de cuenta, contraseñas, tokens, request ni diagnósticos del proveedor. Se
protege `django.contrib.auth` además del logging HTTP/Gunicorn ya existente.
No se afirma igualdad temporal exacta: el transporte síncrono puede afectar
latencias. No se introducen colas, reintentos automáticos ni garantía de entrega
exactamente una vez. SMTP aceptado seguido de fallo de commit puede dejar un
mensaje ambiguo con enlace que no autoriza nada.

## Cuotas y proxy

Se conservan las cuotas existentes por dirección y acción en ventanas de 15
minutos: login 10; signup, reset y reenvío 5. `RateWindow` persiste en PostgreSQL y
serializa la creación/incremento entre conexiones y workers. No usa estado mutable
global ni caché local de proceso para decidir intentos.

Por defecto se usa `REMOTE_ADDR`, ignorando X-Forwarded-For.
`BASIS_TRUSTED_PROXY_CIDRS` permite optar explícitamente por los peers CIDR de un
proxy controlado. Se recorre XFF de derecha a izquierda, retirando sólo proxies
confiables y deteniéndose en el primer salto no confiable. Valores inválidos o
cadenas excesivas conservan el peer como identidad conservadora.

Compose transmite esta opción, vacía por defecto. Para Caddy, usar su comportamiento
upstream de reemplazar cabeceras de clientes no confiables; restringir el listener
web a la red privada del proxy y configurar sólo su CIDR conocido, nunca todos los
clientes/redes. La red/identidad concreta depende del despliegue autorizado; no se
crea infraestructura ni se presume una subred Docker universal. `TRUST_PROXY`
conserva su función separada de esquema HTTPS y exige frontera de red controlada.

## Transporte SMTP real: documentación separada

**SMTP LIVE/proveedor y entrega a buzón real: NOT RUN. Producción: NOT RUN.**
Sin proveedor ni remitente autorizados no se activa envío externo. Para operación
futura, inyectar `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL` desde el entorno del
servicio. No registrar valores ni exportar su entorno. El backend SMTP usa timeout
de 15 segundos. El modo soportado de producción es STARTTLS según la configuración;
no se presume soporte a una API o modo SSL implícito de un proveedor no elegido.

`PUBLIC_URL` determina los enlaces de verificación; reset usa host y esquema de
la petición Django. Comprobar dominio HTTPS autorizado, `ALLOWED_HOSTS`, proxy y
`CSRF_TRUSTED_ORIGINS` coherentes. SPF/DKIM/DMARC, credenciales, TLS del proveedor,
aceptación y recepción real requieren autorización y evidencia operativa propia.
Aceptación SMTP no demuestra llegada al inbox ni lectura.

La referencia local usa el backend SMTP real de Django contra un sink exclusivo
en loopback sin relay externo. Su excepción `EMAIL_USE_TLS=False` pertenece sólo
al fixture aislado y no cambia el default TLS del producto. Los mensajes se
observan en memoria con aliases ALIAS-A/ALIAS-B y enlaces secretos no publicados.
Esto acredita transporte SMTP local y flujo funcional; no acredita proveedor LIVE.

## Verificación y fronteras de entrega

`tests/regression/test_accounts.py` cubre: alta adulta/contraseña, no sesión
pendiente, replay, deshabilitación, reenvío, fallos de correo/logging, migración
conservadora, CSRF, reset caducado/reutilizado, sesiones/logout, cuotas y proxy.
Incluye carreras PostgreSQL de alta duplicada, confirmación, desactivación y
cuota inicial, además de transporte SMTP local observable.

La matriz privada existente se vuelve a ejecutar desde
`tests/regression/test_private_access.py`; no se modifica la política comercial.
`AthleteEnrollment.enroll(account, name, email, started_on)` y
`verify_email(account)` permanecen estables. Los ajustes compartidos son la
preparación explícita del fixture pendiente en
`basis/bootstrap/tests/test_identity.py` y el inventario de modelos de cuentas en
`basis/bootstrap/tests/test_installation.py`. El usuario decidió onboarding
personal gratuito en MAM-620 para cuenta activa/vinculada/verificada; ese carril
se integró posteriormente en PR #7 con `EmailVerification`, según el [readback de perfil](PROFILE_VERIFICATION.md#readback-de-integracion-y-cierre-2026-10-21). MAM-810 no
modifica sus guardas ni los permisos comerciales de entrenamiento/IA.

Registro del ejecutor original, anterior a integración (sus resultados no se reasignan al cierre): los recibos frescos, versiones, comandos, fallos históricos, resultados de navegador
y binding de fuentes/config/tests están en `.cache/MAM810_IMPLEMENTATION_REPORT.md`
del worktree de esta entrega. Los números de CI anteriores no son evidencia del
candidato nuevo. Sin commit/push/PR ni integración realizada por este ejecutor.

La revisión independiente del candidato anterior encontró F1 (reset obsoleto
revierte una desactivación) y F2 (doble consumo concurrente). Su dictamen BLOCK se
conserva como histórico; las regresiones de revisión están ahora en
`AccountResetConcurrencyTests` y `AccountResetProtocolTests`. El reporte actualizado
es `.cache/MAM810_REVISION_REPORT.md`, con binding propio: el gate anterior no
demostraba esos dos casos y no se presenta como evidencia de su corrección.
