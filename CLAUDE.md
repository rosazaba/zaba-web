# Web de Zaba — normas del proyecto

Web estática de fotografía de surf y buceo (marca **Zaba**). Prioridades: se ve sobre todo en móvil, el SEO importa y debe ser fácil de actualizar.

## Reparto del trabajo
- **Cambios en `originales/` o `motor/` (estructura de carpetas, portadas, fotos nuevas, páginas nuevas): ANTES de tocar nada en `web1`, explicar a la usuaria exactamente qué carpetas se crean, qué se mueve y qué se quita, y pedirle permiso.** Claude mantiene él mismo la estructura: crea las carpetas nuevas y quita las antiguas cuando su contenido ya no se usa, siempre avisando y con permiso.
- Cuando la usuaria mande el nombre de una foto de portada, Claude la coloca en su carpeta `portada/` (preguntando antes).
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
- `originales/`: fotos y logo del usuario a tamaño original. **No se modifican nunca y no se suben a GitHub** (están en `.gitignore`). Carpetas en el orden del menú (constantes `C_*` en `build.py`):
  - Cada sección y cada galería tiene su subcarpeta `portada/` con UNA foto (la usuaria las quiere así para encontrarlas rápido): `1-trabajos/portada/` (la grande, ya girada), `1-trabajos/<galería>/portada/` (recuadros) y `3-sobre-mi/portada/`. Tienen prioridad sobre `textos/inicio.yml` y `work.yml`. Las fotos de una subcarpeta `portada/` no cuentan como fotos de la galería.
  - `1-servicio/` (así la llamó la usuaria; antes `1-trabajos/`. El motor acepta `1-servicio`, `1-servicios` y `1-trabajos`; página «Servicios / My services»): `portada/`, `seleccion/` (tira, opcional) y una carpeta por galería (`buceo/`, `surf/`, `dron/`).
  - `2-tarifa/` (antes `2-servicios/`; página «Tarifa / Rates»): `portada/` y `<servicio>/`
  - El motor acepta los dos nombres (`_primera()` en `build.py`) y `en_orig()` traduce rutas antiguas escritas en los `.yml`. La usuaria renombra ella las carpetas en su Explorador.
  - `4-contacto/`: `portada/` (foto del fondo-mural de Contacto)
  - `5-tienda/` (acepta también `5-print-store/`): fotos a la venta (opcional; vacía → se eligen de las galerías) y `estancias/` (habitaciones de ejemplo y las fotos que la usuaria eligió para colgar en ellas). `portada/` no se usa.
  - `6-encuentra-tus-fotos/`: `portada/` (opcional, cabecera) y `<playa>/<AAAA-MM-DD>/` con las fotos de cada sesión. Las playas se definen en `textos/encuentra.yml` → `localizaciones` (carpeta, código, nombre, lugar).
  - `simulacros/`: capturas de diseños que le gustan a la usuaria, como referencia. No se publican.
  - `3-sobre-mi/`: `portada/` (foto apaisada con la cita) y `retrato-…` (bloque «¡Hola! Soy Rosa»). El resto de fotos de la carpeta de momento no se usan. Sin fotos propias usa `textos/about.yml` → `provisional`.
  - `logo/`
  - Las rutas de las imágenes publicadas no cambian (`img/work/...`, `img/inicio/...`, `img/about/...`, `img/services/...`).
- `textos/*.yml`: todo el texto visible. Cada clave lleva `en`, `es` y `fr`.
- `motor/`:
  - `build.py`: generador.
  - `revisar.py`: tests de SEO y enlaces.
  - `plantillas/`: plantillas Jinja.
  - `assets/`: CSS y JS.
- `docs/`: web generada, que es lo que publica GitHub Pages. **No se edita a mano**; se regenera siempre con `build.py`.
- `vista-previa/`: copia para ver en local con doble clic. No se publica.

## Reglas técnicas
- `python motor/build.py` genera la web y ejecuta la revisión. **Solo se publica con 0 errores.** Los avisos se le cuentan al usuario.
- `--preview` genera `vista-previa/` (ignorada por git) con enlaces terminados en `index.html`. Sirve para que el usuario la abra con doble clic en `web1\vista-previa\index.html`. **No publicar ni actualizar artifacts de vista previa por iniciativa propia**: el usuario revisa en su ordenador. Solo se publica una vista previa online cuando el usuario la pide explícitamente (por ejemplo, si está en el móvil). Tras cada cambio se regeneran `docs/` y `vista-previa/` y las dos se copian a `web1`.
- Fotos:
  - Siempre pasan por `optimizar()`: WebP a 640, 1280 y 2000 px, sin EXIF ni GPS.
  - Se ordenan por nombre de archivo (`01-`, `02-`…).
  - Si un original mide menos de 1600 px de lado, se avisa al usuario.
- Logo: cualquier formato en `originales/logo/`. Si hay SVG y PNG con el mismo nombre, se usa el SVG.
  - Archivos actuales: `logo-oscuro.svg`, `logo-claro.svg` e `icono.svg` (la última A), redibujados en vector por Claude a partir de la imagen de WhatsApp. Los `.png` del mismo nombre son copias en alta resolución; `icono.png` genera los favicons.
  - Si no tiene transparencia, se le quita el fondo liso automáticamente.
  - La versión blanca se genera con un filtro CSS, salvo que exista `logo-claro`.
  - El favicon sale de `icono` o, si no hay, del propio logo.
- Menú (orden y rutas en `RUTAS` de `build.py`; nombres en `general.yml` → `menu`): Servicios/My services/Mes services (raíz) · Tarifa/Rates/Tarifs (`/rates/`) · Tienda/Print Store/Boutique (`/print-store/`) · Encuentra tus fotos/Find your photos/Trouvez vos photos (`/find-your-photos/`) · Sobre mí (`/about/`) · Contacto (`/contact/`). Con 6 apartados, por debajo de 1180 px el menú se abre con la hamburguesa.
- Portada = página «Servicios» (antes «Trabajo»; solo cambió el nombre, NO el estilo): foto de portada baja con la frase encima y, debajo, una foto por galería en fila de tres (también en móvil) con enlace a `work/<url>/`, la tira «Selección» y el resumen de la Tarifa.
- Galerías: buceo (`diving`), surf y dron (`drone`), en ese orden (`orden` en `textos/work.yml`). La foto de cada recuadro es la primera de la galería por nombre (`01-`). Una galería definida en `work.yml` sin fotos sale como «Próximamente» con el color de `color`.
- Galería nueva: crear `originales/1-trabajos/<carpeta>` y su bloque en `textos/work.yml` → `galerias`.
- Tira «Selección» de la portada (debajo de las tres galerías): si `1-trabajos/seleccion/` está vacía, coge las `TIRA_POR_GALERIA` (10) mejores fotos de cada galería (nitidez + contraste + color, sin ráfagas casi iguales), las entremezcla sin repetir galería seguida y con el color más parecido a la anterior. Fotos cuadradas, veladas (opacidad .55, algo desaturadas) para no quitar protagonismo a las tres galerías; se mueve sola.
- Fotos de bancos de imágenes (nombre con unsplash, pexels, pixabay…): `fotos_de()` nunca las publica y avisa. Las de Unsplash que descargó la usuaria están en `1-trabajos/fotos-banco-imagenes/` (en `NO_SON_GALERIAS`, no es galería).
- Fotos repetidas: `quitar_repetidas()` en `build.py` no publica la misma imagen dos veces (huella visual) ni dos versiones de la misma toma (DSC05033 y DSC05033-2). Se queda la `portada:` de `work.yml` si es una de ellas; si no, la primera por nombre. Se avisa en el build.
- Portadas: se cambian sustituyendo la foto de la carpeta `portada/` de cada sección o galería. Respaldo: `textos/inicio.yml` → `portada_foto` (+ `portada_girar`) y `textos/work.yml` → `portada:`.
- Sobre mí (`about.html`): SIN foto de arriba (`mostrar_portada: false` en `about.yml`; la cita sigue guardada). Empieza con el bloque «¡Hola! Soy Rosa» en banda de color `--topo`: foto a la izquierda (si es horizontal sale 4/3, si es vertical 5/6), y a la derecha título, subtítulo, historia y botón «Escríbeme» (inspirado en el ejemplo de `originales/simulacros/`). Retrato = archivo `retrato-…` o `provisional.retrato` (ahora la misma foto de `3-sobre-mi/portada/`). Después «Mi propósito» con 3 objetivos y datos. Sin cuadrícula ni tira de fotos. Textos provisionales.
- Tarifa: SIN cabecera con foto (la foto de `2-tarifa/portada/` ya no se usa): arriba título y texto de introducción (`services.yml` → `titulo` / `intro`, provisional). El servicio «Copias artísticas» enlaza a la Tienda.
- Tarifa: cada servicio es una banda a todo el ancho, foto + bloque de color alternando el lado (colores alternos `--topo` y `--arena-2`); dentro, texto, «Incluye», «Desde» + precio y botón. Foto de `2-servicios/<carpeta>/` o, si está vacía, `foto_provisional` en `services.yml`. Debajo, «Próximos pasos / Cómo funciona» con números grandes 01, 02, 03 (ejemplo en `originales/simulacros/`).
- Encuadre de las fotos de arriba: `portada_encuadre` ("x% y%") en `services.yml`, `contact.yml` y `about.yml`; `portada_lado` (izquierda/derecha) en `services.yml` para el texto; `retrato_encuadre` en `about.yml` para la foto de «¡Hola! Soy Rosa».
- Fotos: WebP con calidad adaptable (baja hasta que pesan menos de `PESO_MAX`). Siempre se guardan en `docs/img`; `vista-previa/` no tiene imágenes propias, las enlaza desde `../docs/img`.
- `build.py` borra las páginas generadas que ya no existen (pero en `web1` no se pueden borrar desde aquí: pedírselo al usuario).
- Idiomas: inglés por defecto en la raíz, español en `/es/` y francés en `/fr/`. Las URLs son iguales en los tres idiomas.
- Cada función nueva que afecte al SEO o a los enlaces debe llevar su comprobación en `revisar.py`.
- Diseño:
  - Nada de marrón oscuro en bloques de contenido ni degradados de atardecer (no le gustan a la usuaria). Para bloques de color se usa `--topo` (#D9CCB8, marrón claro neutro) alternado con `--arena-2`. El bloque final «Salgamos a hacer fotos» (`_cierre.html`) es `--topo` plano. El único bloque oscuro es el pie.
  - Solo tema claro. Paleta: arena, tierra/marrón, ocre, amanecer, amarillo suave, azul verdoso y un toque de gris. Tokens en `:root` de `estilos.css`.
  - Tipografía: solo Jost (sin remates). Títulos en Jost Light (300), textos y menú en Jost 400. El token `--serif` del CSS se llama así por historia pero apunta a Jost.
- Pie (bloque marrón): solo el logo y la frase `pie.frase` de `general.yml`, centrados, igual en todas las páginas (sin menú, teléfono, WhatsApp, Instagram ni idiomas; lo pidió la usuaria). WhatsApp ya está en el botón flotante e Instagram va en Contacto.
- Contacto:
  - Sin foto de cabecera ni botón «Llamar». Fondo tipo mural a toda la página: foto de `4-contacto/portada/` en transparencia (`mural_opacidad`) sobre un color sólido (`mural_color`, en `contact.yml`).
  - A la izquierda título, entradilla, WhatsApp e Instagram; a la derecha el formulario en una tarjeta recta, sin sombra.
  - Campos: Nombre, Apellidos, «Asunto a tratar» (desplegable: surf, buceo, dron, en `contact.yml` → `intereses`) y Mensaje (la usuaria quiso mantenerlo).
  - Destino de los mensajes: `contacto.email_formulario` (rouszaba@gmail.com). No se muestra en la web; va codificado en `data-destino` (base64 invertido) para evitar robots. `contacto.email` es el email visible y está vacío a propósito.
  - Sin `web3forms_clave`, el formulario abre el correo del visitante (mailto). Con clave, envía por Web3Forms y muestra un campo de email.
  - El botón flotante de WhatsApp no aparece en la página de contacto.

- Cabecera exclusiva de Encuentra tus fotos (`_cabecera_nueva.html`): banda `--arena-2`, etiqueta, título grande y foto CUADRADA. Sin amarillo, sin olas ni líneas curvas o torcidas (la usuaria no los quiere). Foto: `6-encuentra-tus-fotos/portada/`; si no hay, una foto horizontal de acción de surf (no la del surfista en el agua). La Tienda ya no usa esta cabecera.
- **Estilo de fotos en toda la web: rectas, sin arcos, sin marcos, sin sombras y sin movimiento** (la usuaria rechazó arcos, sombras y fotos torcidas). Esquinas con `--radio`. (Los cuadros dentro de las estancias de la Tienda sí llevan marco: son una simulación.)
- Tienda (Print Store), organizada como la de Laurita Polvorilla (ejemplo que eligió la usuaria): título centrado + estancia grande (salón), 3 pasos (01 Elige tu foto · 02 Elige tamaño y material · 03 Haz tu pedido), «Así queda en tu pared» (dormitorio y estudio), «Elige tu foto» con pestañas Surf/Buceo/Dron (las `FOTOS_TIENDA_POR_GALERIA` = 12 mejores de cada galería; si `5-tienda/` tiene fotos, se usan esas), «Materiales» + «Tamaños y precios» y formulario de pedido (nombre, apellidos, foto elegida, material, tamaño, país, mensaje) que abre WhatsApp con el pedido escrito. Al tocar una foto, su código (`SURF-03`, según su orden en la galería) se apunta en el formulario. Textos, materiales, tamaños y precios en `print-store.yml` (provisionales).
- Estancias de la Tienda: fotos de habitaciones REALES de Unsplash en `5-tienda/estancias/` (`salon-unsplash.jpg` de @dada_design, `dormitorio-unsplash.jpg` de @naiyaru, `estudio-unsplash.jpg` de @steveungermann). La usuaria eligió qué foto suya va en cada una (`print-store.yml` → `estancias_reales.<tipo>.foto`): salón = la ola (DSC04838), dormitorio = la tortuga (_MG_7611) y estudio = la playa de dron (IMG_20260907_09544991); tortuga y dron en horizontal (`girar: 90`). Tres formas de colocar la foto: `centro_x/centro_y/ancho` (cuadro nuevo con marco fino de roble y paspartú), `hueco` (rectángulo en %, sustituye el lienzo de un cuadro que ya está en la foto) o `esquinas` (4 puntos en %, para un cuadro en perspectiva). A la usuaria NO le gustan las habitaciones de render 3D ni que el cuadro quede descentrado o sobre otro mueble: mejor fotos reales con un cuadro ya colgado y sustituir su lienzo.
- Encuentra tus fotos, organizada como la de Zavaglio (ejemplo de la usuaria): fichas por playa + buscador (playa, pueblo, fecha) y una cuadrícula de tarjetas, una por sesión («PLAYA DE PATOS · 01.11», pueblo y nº de fotos). Cada tarjeta abre su página `find-your-photos/<carpeta-playa>-<AAAA-MM-DD>/` (plantilla `encuentra-sesion.html`, en el sitemap) con las fotos. Playas sin sesiones salen como tarjeta «próximamente» color `--topo`. Debajo, aviso de cuándo se suben las fotos y nota de privacidad (`encuentra.yml`). Las fotos se publican SOLO con `con_marca()`: 960 px, logo repetido en diagonal y banda con el código `<CÓDIGO>-<AAAAMMDD>-<nnn>`. «Comprar · 15 €» abre WhatsApp con el código. La usuaria cobra y envía el original (no hay pago ni descarga automáticos: lo decidió ella). Precio en `encuentra.yml` → `precio_foto`.
- `revisar.py` comprueba además: mismo menú en todas las páginas, códigos únicos con botón de compra en Encuentra, que cada página de sesión tenga fotos, al menos 2 estancias con foto en la Tienda, fotos para elegir con códigos únicos y WhatsApp válido en el pedido.

## Despliegue
- Repositorio **rosazaba/zaba-web**: público (lo exige GitHub Pages gratis), con el proyecto entero sin `originales/`.
- GitHub Pages publica desde la rama `main`, carpeta `/docs`.
- Claude hace el push desde su espacio de trabajo mediante la app de Claude para GitHub (instalada solo en `zaba-web`). El usuario no usa cliente de git.
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
5. Hace commit y push al repositorio, y confirma la publicación. **La usuaria quiere que cada cambio se suba a GitHub en cuanto esté listo** (sin preguntar), salvo pruebas que ella aún tiene que decidir.

## Pendiente
- Datos del usuario:
  - Clave de Web3Forms (en `textos/general.yml`), creada con rouszaba@gmail.com.
  - Fotos: faltan las de Sobre mí (portada, retrato, cuadrícula), las de servicios y los originales de dron con más resolución.
  - Textos de Sobre mí (historia, propósito, objetivos, frases): los actuales son provisionales.
- Por confirmar con el usuario: precios de los servicios, ubicación ("Spain") y el dominio (`zaba.com` está puesto provisionalmente).
- Tienda: fotos propias en `5-tienda/`, precios de tamaños y marcos por confirmar.
- Encuentra tus fotos: aún sin sesiones (carpetas de Patos y Berria vacías).
- La usuaria renombrará `1-servicio` → `1-servicios` (el motor acepta ambos).
- Publicación: activar GitHub Pages (lo hace el usuario: Settings → Pages → `main` /docs; la app de Claude no tiene permiso de administración) cuando haya fotos reales y textos revisados.
