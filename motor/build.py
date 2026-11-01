#!/usr/bin/env python3
"""
Generador de la web de Zaba.

  python motor/build.py            -> genera la web en docs/ (lo que se publica en GitHub Pages)
  python motor/build.py --preview  -> genera vista-previa/ con enlaces .../index.html, para abrirla con doble clic

Lee:
  originales/   fotos originales (no se suben a GitHub)
  textos/       textos en en/es/fr
  motor/        plantillas, estilos y scripts
Escribe:
  docs/         web final: HTML + fotos optimizadas en WebP
"""
import json, os, re, shutil, sys, unicodedata
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
ORIG = RAIZ / "originales"
TEXTOS = RAIZ / "textos"
MOTOR = RAIZ / "motor"
SALIDA = RAIZ / "docs"

IDIOMAS = ["en", "es", "fr"]        # el primero es el idioma por defecto (sin prefijo en la URL)
NOMBRE_IDIOMA = {"en": "EN", "es": "ES", "fr": "FR"}
EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
ANCHOS = [640, 1280, 2000]           # tamaños generados para cada foto
CALIDAD = 80
MIN_LADO = 1600                       # avisa si una foto original es más pequeña que esto

PREVIEW = "--preview" in sys.argv
if PREVIEW:
    # La vista previa local va a otra carpeta: nunca se mezcla con la web publicable (docs/)
    SALIDA = RAIZ / "vista-previa"
avisos = []
generadas = set()


# ── utilidades ──────────────────────────────────────────────
def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "foto"


def leer(nombre):
    with open(TEXTOS / f"{nombre}.yml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fotos_de(carpeta):
    c = ORIG / carpeta
    if not c.exists():
        return []
    return sorted(p for p in c.iterdir() if p.suffix.lower() in EXT and not p.name.startswith("."))


def optimizar(src: Path, destino_rel: str):
    """Genera versiones WebP en varios anchos. Devuelve datos para <img srcset>."""
    base = slug(src.stem)
    carpeta = SALIDA / "img" / destino_rel
    carpeta.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)          # respeta la orientación de la cámara
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w0, h0 = im.size
        if max(w0, h0) < MIN_LADO:
            avisos.append(f"Foto pequeña ({w0}x{h0}px), puede verse borrosa en pantallas grandes: {src.relative_to(RAIZ)}")
        anchos = [w for w in ANCHOS if w < w0] + [min(w0, ANCHOS[-1])]
        anchos = sorted(set(anchos))
        versiones = []
        for w in anchos:
            h = round(h0 * w / w0)
            nombre = f"{base}-{w}.webp"
            out = carpeta / nombre
            generadas.add(out)
            if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
                # Al guardar sin "exif=" se eliminan los metadatos (incluida la ubicación GPS)
                im.resize((w, h), Image.LANCZOS).save(out, "WEBP", quality=CALIDAD, method=5)
            versiones.append((w, f"img/{destino_rel}/{nombre}"))
        # Versión JPG para la vista previa al compartir en WhatsApp/redes (solo portada)
        if destino_rel == "inicio/portada":
            og = SALIDA / "img" / "compartir.jpg"
            generadas.add(og)
            c = im.copy(); c.thumbnail((1200, 1200))
            c.save(og, "JPEG", quality=82, optimize=True, progressive=True)
    return {
        "srcset": versiones,
        "src": versiones[min(1, len(versiones) - 1)][1],
        "ancho": w0, "alto": h0,
        "ratio": round(w0 / h0, 4),
    }


# ── logo ────────────────────────────────────────────────────
def _quitar_fondo(im):
    """Si el logo no tiene transparencia y su fondo es liso, lo vuelve transparente."""
    import numpy as np
    im = im.convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    if a[..., 3].min() < 250:                      # ya tiene transparencia
        return im
    rgb = a[..., :3]
    h, w = rgb.shape[:2]
    esquinas = np.array([rgb[0, 0], rgb[0, w - 1], rgb[h - 1, 0], rgb[h - 1, w - 1]])
    if np.ptp(esquinas, axis=0).max() > 24:        # fondo no uniforme: no se toca
        avisos.append("El logo no tiene fondo transparente ni liso; se usa tal cual (mejor PNG transparente o SVG).")
        return im
    fondo = esquinas.mean(axis=0)
    dist = np.sqrt(((rgb - fondo) ** 2).sum(axis=2))
    alfa = np.clip((dist - 12) / 60, 0, 1)
    # recupera el color real en los bordes suavizados (sin halo blanco)
    seguro = np.maximum(alfa, 1e-3)[..., None]
    color = np.clip((rgb - fondo * (1 - seguro)) / seguro, 0, 255)
    salida = np.dstack([color, alfa * 255]).astype(np.uint8)
    return Image.fromarray(salida, "RGBA")


def _cuadrado(im, lado, fondo=None, margen=0.12):
    lienzo = Image.new("RGBA", (lado, lado), fondo or (0, 0, 0, 0))
    c = im.copy(); interior = int(lado * (1 - 2 * margen))
    c.thumbnail((interior, interior), Image.LANCZOS)
    lienzo.alpha_composite(c, ((lado - c.width) // 2, (lado - c.height) // 2))
    return lienzo


def procesar_logo():
    """Busca en originales/logo/: logo (o logo-oscuro), logo-claro (opcional) e icono (opcional)."""
    carpeta = ORIG / "logo"
    if not carpeta.exists():
        return None
    archivos = [p for p in carpeta.iterdir() if p.suffix.lower() in EXT | {".svg"} and not p.name.startswith(".")]
    if not archivos:
        return None
    def buscar(*claves):
        for clave in claves:
            for p in sorted(archivos):
                if clave in slug(p.stem):
                    return p
        return None
    claro = buscar("claro", "light", "blanco", "white")
    icono = buscar("icono", "icon", "simbolo", "symbol")
    principal = buscar("oscuro", "dark") or next((p for p in sorted(archivos) if p not in (claro, icono)), None) or claro
    destino = SALIDA / "img" / "logo"
    destino.mkdir(parents=True, exist_ok=True)

    def preparar(src, nombre):
        if src.suffix.lower() == ".svg":
            out = destino / f"{nombre}.svg"; generadas.add(out)
            shutil.copyfile(src, out)
            return {"src": f"img/logo/{nombre}.svg", "ancho": 0, "alto": 0}, None
        with Image.open(src) as im:
            im = _quitar_fondo(ImageOps.exif_transpose(im))
            caja = im.getchannel("A").getbbox()        # recorta márgenes vacíos
            if caja: im = im.crop(caja)
            if im.width < 400:
                avisos.append(f"Logo pequeño ({im.width}px de ancho): mejor un original más grande o en SVG.")
            alto = 160                                  # 2x para pantallas retina (se muestra a ~40 px de alto)
            r = im.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS) if im.height > alto else im
            out = destino / f"{nombre}.webp"; generadas.add(out)
            r.save(out, "WEBP", quality=90, method=6)
            return {"src": f"img/logo/{nombre}.webp", "ancho": r.width, "alto": r.height}, im

    datos, img_principal = preparar(principal, "logo")
    if claro and claro != principal:
        datos["claro"] = preparar(claro, "logo-claro")[0]["src"]

    # Iconos (pestaña del navegador, acceso directo en el móvil)
    fuente_icono = None
    if icono and icono.suffix.lower() != ".svg":
        with Image.open(icono) as im:
            fuente_icono = _quitar_fondo(ImageOps.exif_transpose(im))
            caja = fuente_icono.getchannel("A").getbbox()
            if caja: fuente_icono = fuente_icono.crop(caja)
    elif img_principal is not None:
        fuente_icono = img_principal
    if fuente_icono is not None:
        for nombre, lado, fondo, margen in [("favicon-32.png", 32, None, 0.02), ("favicon-192.png", 192, (246, 240, 230, 255), 0.12),
                                            ("apple-touch-icon.png", 180, (246, 240, 230, 255), 0.12)]:
            out = destino / nombre; generadas.add(out)
            _cuadrado(fuente_icono, lado, fondo, margen).save(out, "PNG", optimize=True)
        datos["iconos"] = True
    return datos


def limpiar_imagenes_viejas():
    carpeta = SALIDA / "img"
    if not carpeta.exists():
        return
    for p in carpeta.rglob("*"):
        if p.is_file() and p not in generadas:
            p.unlink()
    for p in sorted(carpeta.rglob("*"), reverse=True):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()


# ── construcción ────────────────────────────────────────────
def main():
    g = leer("general")
    inicio = leer("inicio")
    work = leer("work")
    services = leer("services")
    about = leer("about")
    contact = leer("contact")

    # Fotos
    fotos_portada = fotos_de("inicio/portada")[:1]
    if not fotos_portada and inicio.get("portada_foto"):
        # Sin foto en la carpeta de portada: usa la indicada en textos/inicio.yml (sin duplicar el archivo)
        candidata = ORIG / inicio["portada_foto"]
        if candidata.exists():
            fotos_portada = [candidata]
        else:
            avisos.append(f"No existe la foto de portada indicada en textos/inicio.yml: originales/{inicio['portada_foto']}")
    portada = [optimizar(p, "inicio/portada") for p in fotos_portada]
    destacadas = [optimizar(p, "inicio/destacadas") for p in fotos_de("inicio/destacadas")]
    foto_about = [optimizar(p, "about") for p in fotos_de("about")[:1]]
    logo = procesar_logo()

    galerias = []
    conf = work.get("galerias", {}) or {}
    carpetas = sorted(d.name for d in (ORIG / "work").iterdir() if d.is_dir()) if (ORIG / "work").exists() else []
    for carpeta in carpetas:
        c = conf.get(carpeta, {}) or {}
        nombre = carpeta.replace("-", " ").capitalize()
        fotos = [optimizar(p, f"work/{carpeta}") for p in fotos_de(f"work/{carpeta}")]
        if not fotos:
            avisos.append(f"La galería '{carpeta}' está vacía y no se publica.")
            continue
        galerias.append({
            "id": carpeta,
            "url": slug(c.get("url", carpeta)),
            "orden": c.get("orden", 99),
            "titulo": c.get("titulo", {i: nombre for i in IDIOMAS}),
            "resumen": c.get("resumen", {i: "" for i in IDIOMAS}),
            "texto": c.get("texto", {i: "" for i in IDIOMAS}),
            "fotos": fotos,
            "portada": fotos[0],
        })
    galerias.sort(key=lambda x: (x["orden"], x["id"]))
    if not destacadas:
        # Sin selección propia: se muestran fotos de las galerías (hasta 9, repartidas entre ellas)
        filas = [gal["fotos"] for gal in galerias]
        destacadas = [f for grupo in zip(*filas) for f in grupo][:9] if len(filas) > 1 else (filas[0][:9] if filas else [])
        if len(filas) > 1 and len(destacadas) < 9:
            usadas = {id(f) for f in destacadas}
            destacadas += [f for grupo in filas for f in grupo if id(f) not in usadas][:9 - len(destacadas)]

    lista_servicios = []
    for s in services.get("lista", []):
        f = fotos_de(f"services/{s['carpeta']}")[:1]
        lista_servicios.append({**s, "foto": optimizar(f[0], f"services/{s['carpeta']}") if f else None})

    # Páginas: (id, ruta sin idioma, plantilla, datos extra)
    paginas = [("inicio", "", "inicio.html", {}),
               ("work", "work/", "work.html", {}),
               ("services", "services/", "services.html", {}),
               ("about", "about/", "about.html", {}),
               ("contact", "contact/", "contact.html", {})]
    for gal in galerias:
        paginas.append((f"galeria-{gal['id']}", f"work/{gal['url']}/", "galeria.html", {"galeria": gal}))

    env = Environment(loader=FileSystemLoader(MOTOR / "plantillas"), autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)

    for lang in IDIOMAS:
        prefijo = "" if lang == IDIOMAS[0] else f"{lang}/"

        def T(valor, lang=lang):
            """Devuelve el texto en el idioma actual (o en inglés si falta)."""
            if isinstance(valor, dict):
                return valor.get(lang) or valor.get(IDIOMAS[0]) or ""
            return valor or ""

        for pid, ruta, plantilla, extra in paginas:
            ruta_completa = prefijo + ruta
            profundidad = ruta_completa.count("/")
            rel = "../" * profundidad

            def url(destino, lang_destino=lang, rel=rel):
                """Enlace relativo a otra página. destino = ruta sin idioma, p. ej. 'work/'."""
                pre = "" if lang_destino == IDIOMAS[0] else f"{lang_destino}/"
                r = rel + pre + destino
                if PREVIEW:
                    return r + "index.html"
                return r or "./"

            def asset(path, rel=rel):
                return rel + path

            def srcset(foto, rel=rel):
                return ", ".join(f"{rel}{p} {w}w" for w, p in foto["srcset"])

            def foto(f, sizes="100vw", clase="", carga="lazy", alt="", rel=rel):
                alt = alt or f"{g['marca']} — {T(g['lema'])}"
                extra = ' fetchpriority="high"' if carga == "eager" else ""
                return Markup(
                    f'<img class="{escape(clase)}" src="{rel}{f["src"]}" srcset="{srcset(f)}" sizes="{sizes}" '
                    f'width="{f["ancho"]}" height="{f["alto"]}" alt="{escape(alt)}" '
                    f'loading="{carga}" decoding="async"{extra}>')

            otros_idiomas = [{"code": l, "label": NOMBRE_IDIOMA[l], "href": url(ruta, l), "actual": l == lang}
                             for l in IDIOMAS]
            alternos = [{"code": l, "href": g["dominio"].rstrip("/") + "/" + ("" if l == IDIOMAS[0] else f"{l}/") + ruta}
                        for l in IDIOMAS]

            # Datos estructurados (schema.org) para Google
            dom = g["dominio"].rstrip("/")
            negocio = {"@type": "ProfessionalService", "@id": dom + "/#negocio", "name": g["marca"],
                       "description": T(g["descripcion_google"]), "url": dom + "/" + prefijo,
                       "knowsLanguage": IDIOMAS}
            if portada: negocio["image"] = dom + "/img/compartir.jpg"
            if logo and logo["src"].endswith((".webp", ".svg")): negocio["logo"] = dom + "/" + logo["src"]
            if g["contacto"].get("email"): negocio["email"] = g["contacto"]["email"]
            if g["contacto"].get("telefono"): negocio["telephone"] = g["contacto"]["telefono"].replace(" ", "")
            if g["contacto"].get("instagram"): negocio["sameAs"] = ["https://instagram.com/" + g["contacto"]["instagram"]]
            grafo = [negocio]
            if ruta:
                migas = [("inicio", "")] + ([("work", "work/")] if pid.startswith("galeria") else [])
                elementos = [{"@type": "ListItem", "position": n + 1, "name": T(g["menu"][k]), "item": dom + "/" + prefijo + r}
                             for n, (k, r) in enumerate(migas)]
                nombre_actual = T(extra["galeria"]["titulo"]) if "galeria" in extra else T(g["menu"].get(pid, {}))
                elementos.append({"@type": "ListItem", "position": len(elementos) + 1, "name": nombre_actual,
                                  "item": dom + "/" + ruta_completa})
                grafo.append({"@type": "BreadcrumbList", "itemListElement": elementos})
            json_ld = Markup(json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False)
                             .replace("</", "<\\/"))

            html = env.get_template(plantilla).render(json_ld=json_ld,
                lang=lang, pid=pid, T=T, url=url, asset=asset, srcset=srcset, foto=foto,
                g=g, inicio=inicio, work=work, services=services, about=about, contact=contact,
                portada=portada[0] if portada else None, destacadas=destacadas,
                foto_about=foto_about[0] if foto_about else None,
                galerias=galerias, lista_servicios=lista_servicios,
                idiomas=otros_idiomas, alternos=alternos,
                canonical=g["dominio"].rstrip("/") + "/" + ruta_completa,
                tiene_compartir=bool(portada), logo=logo,
                **extra,
            )
            out = SALIDA / ruta_completa / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")

    # Estilos y scripts
    destino_assets = SALIDA / "assets"
    if destino_assets.exists():
        shutil.rmtree(destino_assets)
    shutil.copytree(MOTOR / "assets", destino_assets)

    # Ficheros para GitHub Pages
    (SALIDA / ".nojekyll").write_text("")
    dominio = g["dominio"].replace("https://", "").replace("http://", "").strip("/")
    cname = SALIDA / "CNAME"
    if g.get("publicar_dominio"):
        cname.write_text(dominio + "\n")
    elif cname.exists():
        cname.unlink()
    (SALIDA / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {g['dominio'].rstrip('/')}/sitemap.xml\n")
    urls = [g["dominio"].rstrip("/") + "/" + ("" if l == IDIOMAS[0] else f"{l}/") + r
            for l in IDIOMAS for _, r, _, _ in paginas]
    (SALIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")

    limpiar_imagenes_viejas()

    # Resumen
    total = sum(f.stat().st_size for f in (SALIDA / "img").rglob("*") if f.is_file()) if (SALIDA / "img").exists() else 0
    n_fotos = len(destacadas) + len(portada) + len(foto_about) + sum(len(x["fotos"]) for x in galerias)
    print(f"✓ Web generada en {SALIDA.name}/  ·  {len(paginas) * len(IDIOMAS)} páginas  ·  {n_fotos} fotos  ·  {total/1e6:.1f} MB de imágenes"
          + ("  ·  modo vista previa" if PREVIEW else ""))
    for a in avisos:
        print("⚠", a)


if __name__ == "__main__":
    main()
    import revisar
    revisar.DOCS = SALIDA
    sys.exit(revisar.main())
