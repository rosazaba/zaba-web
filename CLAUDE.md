# Web de Zaba — normas del proyecto

Web estática de fotografía de surf y buceo (marca **Zaba**). Prioridades: se ve sobre todo en móvil, el SEO importa y debe ser fácil de actualizar.

## Reparto del trabajo
- **El usuario** decide el contenido y selecciona las fotos. No toca código ni hace pasos técnicos.
- **Claude** hace todo lo técnico: optimizar, generar, revisar, publicar y configurar.
- El usuario escribe en español. Claude traduce a EN y FR y le enseña los textos nuevos antes de publicar.

## Dónde se trabaja
- El proyecto vive en el ordenador del usuario, en `C:\Users\rousm\web1` (Windows).
- No hay terminal en ese equipo, solo acceso a archivos. Por eso todo se ejecuta en el espacio de trabajo de Claude:
  1. Traer los archivos con la herramienta de stage.
  2. Generar la web.
  3. Devolver los archivos cambiados con commit.
- Al usuario no se le pide instalar nada.

## Estructura
- `originales/`: fotos y logo del usuario a tamaño original. **No se modifican nunca y no se suben a GitHub** (están en `.gitignore`). Una carpeta por sección o galería:
  - `inicio/portada`, `inicio/destacadas`
  - `work/<galeria>`
  - `about`
  - `services/<servicio>`
  - `logo`
- `textos/*.yml`: todo el texto visible. Cada clave lleva `en`, `es` y `fr`.
- `motor/`:
  - `build.py`: generador.
  - `revisar.py`: tests de SEO y enlaces.
  - `plantillas/`: plantillas Jinja.
  - `assets/`: CSS y JS.
- `docs/`: web generada, que es lo que publica GitHub Pages. **No se edita a mano**; se regenera siempre con `build.py`.

## Reglas técnicas
- `python motor/build.py` genera la web y ejecuta la revisión. **Solo se publica con 0 errores.** Los avisos se le cuentan al usuario.
- `--preview` genera enlaces terminados en `index.html`. Es solo para la vista previa en un artifact. **Nunca se despliega una build con `--preview`.**
- Fotos:
  - Siempre pasan por `optimizar()`: WebP a 640, 1280 y 2000 px, sin EXIF ni GPS.
  - Se ordenan por nombre de archivo (`01-`, `02-`…).
  - Si un original mide menos de 1600 px de lado, se avisa al usuario.
- Logo: cualquier formato en `originales/logo/`.
  - Si no tiene transparencia, se le quita el fondo liso automáticamente.
  - La versión blanca se genera con un filtro CSS, salvo que exista `logo-claro`.
  - El favicon sale de `icono` o, si no hay, del propio logo.
- Galería nueva: basta con crear `originales/work/<carpeta>`. El título y la URL se definen en `textos/work.yml` → `galerias`.
- Idiomas: inglés por defecto en la raíz, español en `/es/` y francés en `/fr/`. Las URLs son iguales en los tres idiomas.
- Cada función nueva que afecte al SEO o a los enlaces debe llevar su comprobación en `revisar.py`.
- Diseño:
  - Solo tema claro. Paleta: arena, tierra/marrón, ocre, amanecer, amarillo suave, azul verdoso y un toque de gris. Tokens en `:root` de `estilos.css`.
  - Tipografías: Cormorant Garamond y Jost.
- Contacto:
  - Primero los botones de WhatsApp y Llamar.
  - Después el formulario, que solo tiene nombre, "me interesa" (surf o buceo, en `textos/contact.yml` → `intereses`) y mensaje.
  - Sin `web3forms_clave`, el formulario abre el correo del visitante (mailto). Con clave, envía por Web3Forms y muestra un campo de email.
  - El botón flotante de WhatsApp no aparece en la página de contacto.

## Despliegue
- Repositorio **rosazaba/zaba-web**: público (lo exige GitHub Pages gratis), con el proyecto entero sin `originales/`.
- GitHub Pages publica desde la rama `main`, carpeta `/docs`.
- Claude hace el push desde su espacio de trabajo con la conexión de GitHub de claude.ai. El usuario no usa cliente de git.
- Mientras no haya dominio, `dominio` vale `https://rosazaba.github.io/zaba-web` y `publicar_dominio: false`. Los enlaces internos son relativos, así que la web funciona en esa subruta y en el dominio sin cambios.
- Dominio .com:
  1. Poner `dominio` y `publicar_dominio: true` en `textos/general.yml`. El build crea `docs/CNAME`.
  2. En el DNS del dominio, registros A del dominio raíz a `185.199.108.153`, `185.199.109.153`, `185.199.110.153` y `185.199.111.153`, y CNAME de `www` a `rosazaba.github.io`.
  3. Verificar el dominio en la cuenta (GitHub → Settings → Pages → Verified domains, con un registro TXT) para evitar que otros lo usen.
  4. Activar "Enforce HTTPS" en la configuración de Pages.
- `dominio` también se usa para canonical, hreflang, sitemap y og:image. Tiene que coincidir con la dirección real de publicación.

## Cómo se actualiza
1. El usuario deja fotos en su carpeta de `originales/` o pide un cambio de texto.
2. Claude trae `originales/`, `textos/` y `motor/` desde `web1`.
3. Ejecuta `build.py` y revisa el resultado en móvil y escritorio con capturas.
4. Devuelve a `web1` los archivos cambiados, `docs/` incluido.
5. Hace commit y push al repositorio, y confirma la publicación.

## Pendiente
- Datos del usuario:
  - Email público, Instagram y clave de Web3Forms (en `textos/general.yml`).
  - Logo, en `originales/logo/`.
  - Fotos reales: ahora mismo no hay ninguna.
- Por confirmar con el usuario: precios de los servicios, ubicación ("Spain") y el dominio (`zaba.com` está puesto provisionalmente).
- Publicación: confirmar que existe `rosazaba/zaba-web` y que GitHub está conectado en claude.ai. Después, primer push y activar Pages.
