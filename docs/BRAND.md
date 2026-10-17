# Identidad BASIS

La identidad de la app procede de [BASIS Asesoría Fitness](https://basisasesoria.fitness/),
indicada por el propietario. Esta decisión sustituye la paleta verde y el símbolo
provisional de la app. OpenDesign vuelve a estar permitido si aporta valor;
su uso es opcional y no cambia la obligación de reutilizar esta identidad.

## Fuentes inspeccionadas

- Logo original: [Logo_blanco.svg](https://basisasesoria.fitness/Logo_blanco.svg).
- CSS publicado: [agente-entrenamientos.CBAHeYg6.css](https://basisasesoria.fitness/_astro/agente-entrenamientos.CBAHeYg6.css).
- Fecha de consulta: 2026-10-17. Huellas y procedencia en
  `assets/brand/sources.json`; original sin modificar en `logo-original.svg`.
- La página inspeccionada usa una pila de fuentes del sistema
  (`ui-sans-serif, system-ui, sans-serif`). Los preconnect de Google Fonts
  no prueban que exista una fuente personalizada cargada; no se añade ninguna.

| Función observada | Color |
|---|---|
| Azul principal | `#0400FF` |
| Azul más oscuro / hover | `#0300CC` |
| Superficie blanca | `#ffffff` |
| Texto oscuro | `#111827` |
| Texto secundario | `#374151` |
| Borde neutro | `#e5e7eb` |
| Fondo neutro usado en la adaptación | `#f8fafc` |

Los tonos semánticos del modo oscuro son una adaptación de interfaz para
contraste; no se presentan como un manual de marca original del sitio.

## Tokens y recursos locales

`assets/brand/identity.json` contiene los colores de identidad compartidos por
HTML y manifiesto PWA. `training/brand.py` los carga al iniciar cada proceso;
reiniciar el servidor después de cambiar ese archivo. El contexto de plantilla
expone `basis_brand`, y `base.html` define las variables `--basis-brand-*`.
`assets/css/tokens.css` adapta esa identidad a tokens semánticos y Cotton UI,
además de centralizar tipografía, espaciado, radios, foco y movimiento.

`templates/cotton/brand.html` compone el logo para cabeceras de escritorio,
móvil y autenticación. Se sirve desde la app y no depende del sitio comercial,
de CDN ni de una conexión al VPS en tiempo de uso.

`logo.svg` conserva exactamente el atributo `d`, relleno y reglas del original:
solo cambia el lienzo a `viewBox="126 124 314 198"` para quitar espacio vacío.
El logotipo ya contiene la palabra BASIS; no se reconstruye con otra tipografía.
El fondo azul mantiene legible su relleno claro en ambos temas.

Los iconos PWA usan el mismo vector, centrado en un fondo azul cuadrado. Los PNG
192/512 se renderizan desde `assets/icons/icon.svg`; al cambiar identidad o logo
se deben regenerar esos derivados. El logo visible se precarga con el shell
offline; la revisión del service worker cambia al cambiar esos recursos.

## Alcance y acceso

Se consultaron HTML, CSS y SVG públicos. No se accedió al VPS ni a credenciales;
no hay una sesión autenticada del VPS confirmada en este trabajo. Los recursos
públicos bastaron para esta adaptación. La web comercial y su despliegue no se
modifican. La identidad se aplica a la app Django.

Este cambio no cierra BASIS-012 ni BASIS-013: sus criterios de recorridos,
inventario completo de componentes, lector de pantalla y demás estados siguen
en sus respectivos tickets. La revisión de marca no certifica instalación PWA
en dispositivos físicos ni accesibilidad completa del producto.

## Validación de esta adaptación

Ocho pruebas web Django pasaron. Check, Ruff, formato Python y migraciones sin
diferencias se comprobaron localmente. En Chromium/Edge se revisaron Hoy, perfil,
suscripción, offline y login en ambos temas a 390 y 1440 px: 20 combinaciones,
sin desbordamientos, errores JavaScript ni infracciones detectadas por axe en
WCAG A/AA/2.1AA. El logo cargó también sin red en ambos temas. Son muestras
automatizadas, no certificación global de accesibilidad ni dispositivos físicos.

La revisión detectó y corrigió el contraste del CTA de Hoy: los estilos generales
de enlaces estaban fuera de las capas CSS y anulaban los colores de Cotton.
Esos valores por defecto pasan a la capa base, y el CTA usa la variante primary
del kit con tokens explícitos del panel. También se verificó el texto español
tras corregir una conversión local de codificación. Capturas e informe local en
`artifacts/brand/`, excluidos del repositorio.
