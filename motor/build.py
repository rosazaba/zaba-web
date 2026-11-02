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
# Carpetas de originales/ (siguen el orden del menú). La portada y los trabajos son la misma página.
C_TRABAJOS = "1-trabajos"            # portada/, seleccion/ y una carpeta por galería (buceo/, surf/, dron/…)
C_PORTADA = f"{C_TRABAJOS}/portada"    # la foto grande de arriba (cada galería tiene además su <galería>/portada/)
C_SELECCION = f"{C_TRABAJOS}/seleccion"
C_SERVICIOS = "2-servicios"
C_SOBRE_MI = "3-sobre-mi"
C_CONTACTO = "4-contacto"             # solo su carpeta portada/ (foto de arriba de Contacto)
BANCOS_IMAGENES = ("unsplash", "pexels", "pixabay", "shutterstock", "istock", "adobestock", "freepik")
NO_SON_GALERIAS = {"portada", "portadas", "seleccion", "fotos-banco-imagenes"}
TEXTOS = RAIZ / "textos"
MOTOR = RAIZ / "motor"
SALIDA = RAIZ / "docs"

IDIOMAS = ["en", "es", "fr"]        # el primero es el idioma por defecto (sin prefijo en la URL)
NOMBRE_IDIOMA = {"en": "EN", "es": "ES", "fr": "FR"}
EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
ANCHOS = [640, 1280, 2000]           # tamaños generados para cada foto
TIRA_POR_GALERIA = 10               # fotos de cada galería en la tira de la portada
CALIDAD = 80
PESO_MAX = 580_000                   # bytes; por encima, se recomprime (la revisión avisa a partir de PESO_MAX_FOTO)
MIN_LADO = 1600                       # avisa si una foto original es más pequeña que esto

PREVIEW = "--preview" in sys.argv
if PREVIEW:
    # La vista previa local va a otra carpeta: nunca se mezcla con la web publicable (docs/)
    SALIDA = RAIZ / "vista-previa"
# Las fotos optimizadas se guardan siempre en docs/img. La vista previa no las duplica:
# sus páginas las enlazan desde ../docs/img (las dos carpetas están juntas en web1).
IMG_DIR = RAIZ / "docs" / "img"
PREFIJO_IMG = "../docs/" if PREVIEW else ""
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
    fotos = sorted(p for p in c.iterdir() if p.suffix.lower() in EXT and not p.name.startswith("."))
    # Las fotos de bancos de imágenes no son de la fotógrafa: nunca se publican como trabajo suyo
    ajenas = [p for p in fotos if any(b in p.name.lower() for b in BANCOS_IMAGENES)]
    for p in ajenas:
        avisos.append(f"Foto de banco de imágenes, no se publica: {p.relative_to(ORIG)}")
    return [p for p in fotos if p not in ajenas]


def _color_lab(im):
    """Color medio de la foto en espacio Lab (L, a, b), ponderando los tonos con más color."""
    import numpy as np
    c = im.convert("RGB").copy(); c.thumbnail((64, 64))
    rgb = np.asarray(c, dtype=np.float32).reshape(-1, 3) / 255
    lin = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = lin @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[:, 1] - 16; a = 500 * (f[:, 0] - f[:, 1]); b = 200 * (f[:, 1] - f[:, 2])
    peso = 1 + np.hypot(a, b) / 20                 # los píxeles con color pesan más que los grises
    return tuple(round(float((v * peso).sum() / peso.sum()), 2) for v in (L, a, b))


def _huella(im):
    """Huella visual de la foto (dHash de 16x16): dos fotos iguales o casi iguales tienen huellas parecidas."""
    import numpy as np
    g = np.asarray(im.convert("L").resize((17, 16), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def _calidad_y_foco(im):
    """Puntuación sencilla de la foto (nitidez + contraste + color) para elegir las mejores de la tira,
    y el punto con más detalle (en %) para centrar el recorte cuadrado ahí."""
    import numpy as np
    c = im.convert("RGB").copy(); c.thumbnail((256, 256))
    a = np.asarray(c, dtype=np.float32)
    g = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lap = np.abs(4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    nitidez = float(np.percentile(lap, 99))                      # bordes nítidos en algún punto (el sujeto)
    contraste = float(g.std())
    rg, yb = a[..., 0] - a[..., 1], 0.5 * (a[..., 0] + a[..., 1]) - a[..., 2]
    color = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))
    calidad = round(nitidez / 60 + contraste / 50 + color / 60, 3)
    # centro del detalle: media ponderada por la energía de bordes
    w = lap ** 2; tot = w.sum() or 1
    ys, xs = np.mgrid[1:g.shape[0] - 1, 1:g.shape[1] - 1]
    fx = float((w * xs).sum() / tot / g.shape[1] * 100); fy = float((w * ys).sum() / tot / g.shape[0] * 100)
    return calidad, (round(min(max(fx, 15), 85)), round(min(max(fy, 15), 85)))


def _misma_rafaga(a, b):
    """DSC05033 y DSC05035: mismo prefijo y números de archivo muy seguidos = misma ráfaga."""
    def partes(n):   # prefijo (letras) y el último número largo del nombre (IMG_20260907_09532450 -> 09532450)
        nums = re.findall(r"\d{3,}", Path(n).stem)
        return (re.match(r"\D*", n).group(0).lower(), int(nums[-1])) if nums else (None, None)
    (pa, na), (pb, nb) = partes(a["origen"]), partes(b["origen"])
    return na is not None and pa == pb and abs(na - nb) <= 3


def _base_nombre(nombre):
    """DSC05033-2, DSC04761-2_1, _MG_1943 (2), _MG_8319 - Copy  ->  nombre de la toma original."""
    b = Path(nombre).stem.lower()
    while True:
        n = re.sub(r"(\s*\(\d+\)|\s*-\s*cop(y|ia)(\s*\d+)?|[-_]\d{1,2})$", "", b)
        if n == b or not re.search(r"\d", n):   # "J (11)" no se reduce a "j": sin número no es una toma
            return b
        b = n


def quitar_repetidas(fotos, vistas, carpeta):
    """Quita fotos repetidas: la misma imagen (aunque esté en otra galería o con otro nombre)
    o una versión de la misma toma (DSC05033 y DSC05033-2, aunque una sea en blanco y negro). Se queda la primera."""
    distancia = lambda a, b: bin(a ^ b).count("1")
    buenas = []
    for f in fotos:
        igual = next((v for v in vistas if distancia(f["huella"], v["huella"]) <= 10
                      or (_base_nombre(f["origen"]) == _base_nombre(v["origen"]) and distancia(f["huella"], v["huella"]) <= 135)), None)
        if igual:
            avisos.append(f"Foto repetida, no se publica: {carpeta}/{f['origen']} (igual que {igual['_carpeta']}/{igual['origen']})")
            continue
        f["_carpeta"] = carpeta
        vistas.append(f); buenas.append(f)
    return buenas


def orden_cromatico(fotos):
    """Ordena las fotos para que el color fluya de una a la siguiente:
    empieza por la más cálida y luminosa y va siempre a la más parecida (cadena de vecinos + mejora 2-opt)."""
    if len(fotos) < 3:
        return list(fotos)
    import numpy as np
    P = np.array([f["lab"] for f in fotos]) * np.array([0.6, 1, 1])   # el tono cuenta más que la luz
    D = np.sqrt(((P[:, None] - P[None]) ** 2).sum(-1))
    inicio = int(np.argmax(P[:, 0] * 0.4 + P[:, 2] + P[:, 1] * 0.5))
    ruta, libres = [inicio], set(range(len(fotos))) - {inicio}
    while libres:
        sig = min(libres, key=lambda j: D[ruta[-1], j]); ruta.append(sig); libres.remove(sig)
    mejora = True
    while mejora:
        mejora = False
        for i in range(1, len(ruta) - 1):
            for k in range(i + 1, len(ruta)):
                a, b = ruta[i - 1], ruta[i]
                c = ruta[k]; d = ruta[k + 1] if k + 1 < len(ruta) else None
                antes = D[a, b] + (D[c, d] if d is not None else 0)
                despues = D[a, c] + (D[b, d] if d is not None else 0)
                if despues + 1e-6 < antes:
                    ruta[i:k + 1] = ruta[i:k + 1][::-1]; mejora = True
    return [fotos[i] for i in ruta]


def entremezclar(grupos):
    """Mezcla las fotos de varias galerías: nunca dos seguidas de la misma galería (si se puede),
    reparto proporcional y, entre las candidatas, la de color más parecido a la anterior."""
    import numpy as np
    grupos = [list(g) for g in grupos if g]
    if len(grupos) < 2:
        return orden_cromatico(grupos[0]) if grupos else []
    total = sum(len(g) for g in grupos)
    lab = lambda f: np.array(f["lab"]) * np.array([0.6, 1, 1])
    # empieza por la foto más cálida y luminosa de la galería más grande
    g0 = max(range(len(grupos)), key=lambda i: len(grupos[i]))
    primera = max(grupos[g0], key=lambda f: f["lab"][0] * 0.4 + f["lab"][2] + f["lab"][1] * 0.5)
    orden, usadas, ultimo = [primera], [0] * len(grupos), g0
    grupos[g0].remove(primera); usadas[g0] = 1
    while any(grupos):
        n = len(orden) + 1
        candidatos = [i for i, g in enumerate(grupos) if g and i != ultimo] or [i for i, g in enumerate(grupos) if g]
        # la galería que más "atrasada" va respecto a su parte proporcional
        i = max(candidatos, key=lambda i: (len(grupos[i]) + usadas[i]) * n / total - usadas[i])
        sig = min(grupos[i], key=lambda f: float(np.linalg.norm(lab(f) - lab(orden[-1]))))
        grupos[i].remove(sig); orden.append(sig); usadas[i] += 1; ultimo = i
    return orden


def optimizar(src: Path, destino_rel: str, girar: int = 0):
    """Genera versiones WebP en varios anchos. Devuelve datos para <img srcset>."""
    base = slug(src.stem) + (f"-giro{girar % 360}" if girar % 360 else "")
    carpeta = IMG_DIR / destino_rel
    carpeta.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)          # respeta la orientación de la cámara
        if girar % 360:                           # giro pedido en textos (grados, en el sentido del reloj)
            im = im.rotate(-girar, expand=True)
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
                r = im.resize((w, h), Image.LANCZOS)
                # Fotos con mucho grano o detalle (azul bajo el agua, vistas aéreas) pesan mucho:
                # se baja la calidad poco a poco solo hasta que entran en el peso máximo.
                for q in (CALIDAD, 74, 68, 62):
                    r.save(out, "WEBP", quality=q, method=5)
                    if out.stat().st_size <= PESO_MAX: break
                while out.stat().st_size > PESO_MAX and r.width > 900:   # último recurso: algo más pequeña
                    r = im.resize((round(r.width * .87), round(r.height * .87)), Image.LANCZOS)
                    r.save(out, "WEBP", quality=68, method=5)
            versiones.append((w, f"img/{destino_rel}/{nombre}"))
        # Versión JPG para la vista previa al compartir en WhatsApp/redes (solo portada)
        if destino_rel == "inicio/portada":
            og = IMG_DIR / "compartir.jpg"
            generadas.add(og)
            c = im.copy(); c.thumbnail((1200, 1200))
            c.save(og, "JPEG", quality=82, optimize=True, progressive=True)
        lab = _color_lab(im)
        huella = _huella(im)
        calidad, foco = _calidad_y_foco(im)
    return {
        "calidad": calidad, "foco": foco,
        "lab": lab,
        "huella": huella,
        "origen": src.name,
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
            for p in sorted(archivos, key=lambda p: (p.suffix.lower() != ".svg", p.name)):   # el SVG tiene prioridad
                if clave in slug(p.stem):
                    return p
        return None
    claro = buscar("claro", "light", "blanco", "white")
    icono = buscar("icono", "icon", "simbolo", "symbol")
    principal = buscar("oscuro", "dark") or next((p for p in sorted(archivos, key=lambda p: (p.suffix.lower() != ".svg", p.name)) if p not in (claro, icono)), None) or claro
    destino = IMG_DIR / "logo"
    destino.mkdir(parents=True, exist_ok=True)

    def preparar(src, nombre):
        if src.suffix.lower() == ".svg":
            out = destino / f"{nombre}.svg"; generadas.add(out)
            shutil.copyfile(src, out)
            vb = re.search(r'viewBox="([^"]+)"', src.read_text(encoding="utf-8"))
            ancho = alto = 0
            if vb:                                       # tamaño intrínseco a 160 px de alto (evita saltos al cargar)
                _, _, w, h = (float(v) for v in vb.group(1).replace(",", " ").split())
                ancho, alto = round(w * 160 / h), 160
            return {"src": f"img/logo/{nombre}.svg", "ancho": ancho, "alto": alto}, None
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
    if icono and icono.suffix.lower() == ".svg":     # los favicons PNG salen de la versión PNG del icono, si existe
        icono = next((p for p in sorted(archivos) if p.stem == icono.stem and p.suffix.lower() != ".svg"), icono)
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
    def de_portadas(carpeta):
        """Primera foto de la subcarpeta «portada» de una sección o galería (originales/<carpeta>/portada/)."""
        return next(iter(fotos_de(f"{carpeta}/portada")), None)
    fotos_portada = fotos_de(C_PORTADA)[:1]
    if not fotos_portada and inicio.get("portada_foto"):
        # Sin foto en la carpeta de portada: usa la indicada en textos/inicio.yml (sin duplicar el archivo)
        candidata = ORIG / inicio["portada_foto"]
        if candidata.exists():
            fotos_portada = [candidata]
        else:
            avisos.append(f"No existe la foto de portada indicada en textos/inicio.yml: originales/{inicio['portada_foto']}")
    portada = [optimizar(p, "inicio/portada", int(inicio.get("portada_girar") or 0)) for p in fotos_portada]
    destacadas = [optimizar(p, "inicio/destacadas") for p in fotos_de(C_SELECCION)]
    # Sobre mí: 3-sobre-mi/portada/ (arriba) y retrato-… o about.yml → provisional.retrato (bloque «Hola»).
    # Si aún no hay fotos propias, se usan las de about.yml → provisional.
    propias = fotos_de(C_SOBRE_MI)
    prov = about.get("provisional") or {}
    def prov_foto(ruta):
        p = ORIG / ruta if ruta else None
        if p and p.exists(): return p
        if ruta: avisos.append(f"No existe la foto provisional de Sobre mí: originales/{ruta}")
        return None
    def elegir(clave):
        if clave == "portada" and de_portadas(C_SOBRE_MI):          # 3-sobre-mi/portada/
            return de_portadas(C_SOBRE_MI)
        return next((p for p in propias if slug(p.stem).startswith(clave)), None) or prov_foto(prov.get(clave))
    sobre = {
        "portada": optimizar(elegir("portada"), "about") if elegir("portada") else None,
        "retrato": optimizar(elegir("retrato"), "about") if elegir("retrato") else None,
    }
    if not propias and not de_portadas(C_SOBRE_MI):
        avisos.append("Sobre mí usa fotos provisionales: pon tus fotos en originales/3-sobre-mi/ (portada-…, retrato-… y el resto).")
    foto_about = [f for f in [sobre["portada"], sobre["retrato"]] if f]
    logo = procesar_logo()

    galerias = []
    conf = work.get("galerias", {}) or {}
    raiz = ORIG / C_TRABAJOS
    carpetas = sorted(d.name for d in raiz.iterdir() if d.is_dir() and d.name not in NO_SON_GALERIAS) if raiz.exists() else []
    carpetas += [c for c in conf if c not in carpetas]          # galerías definidas en work.yml aunque no tengan carpeta
    # orden de las galerías según work.yml, para que una foto repetida se quede en la primera galería
    carpetas.sort(key=lambda c: ((conf.get(c) or {}).get("orden", 99), c))
    ya_vistas = []
    for carpeta in carpetas:
        c = conf.get(carpeta, {}) or {}
        nombre = carpeta.replace("-", " ").capitalize()
        fotos = [optimizar(p, f"work/{carpeta}") for p in fotos_de(f"{C_TRABAJOS}/{carpeta}")]
        # portada del recuadro: portadas/portada-<galería>.jpg (si no hay, la de work.yml o la primera)
        p_portada = de_portadas(f"{C_TRABAJOS}/{carpeta}")
        f_portada = optimizar(p_portada, "inicio/portadas") if p_portada else None
        # si la portada es una de las fotos repetidas, en la galería se queda esa versión y no la otra
        es_portada = lambda f: f["origen"] == c.get("portada") or (f_portada and bin(f["huella"] ^ f_portada["huella"]).count("1") <= 10)
        fotos.sort(key=lambda f: not es_portada(f))
        fotos = quitar_repetidas(fotos, ya_vistas, carpeta)
        fotos.sort(key=lambda f: f["origen"])
        if not fotos:
            if carpeta not in conf:
                avisos.append(f"La galería '{carpeta}' está vacía y no se publica.")
                continue
            avisos.append(f"La galería '{carpeta}' aún no tiene fotos: se muestra como «Próximamente».")
        galerias.append({
            "id": carpeta,
            "url": slug(c.get("url", carpeta)),
            "orden": c.get("orden", 99),
            "titulo": c.get("titulo", {i: nombre for i in IDIOMAS}),
            "resumen": c.get("resumen", {i: "" for i in IDIOMAS}),
            "texto": c.get("texto", {i: "" for i in IDIOMAS}),
            "fotos": fotos,
            "portada": f_portada or next((f for f in fotos if f["origen"] == c.get("portada")), fotos[0] if fotos else None),
            "color": c.get("color", ""),
        })
    galerias.sort(key=lambda x: (x["orden"], x["id"]))
    if not destacadas:
        # Sin selección propia: tira con fotos de todas las galerías (hasta TIRA_POR_GALERIA de cada una)
        # y ordenadas por color para que pasen de unos tonos a otros con armonía.
        # De cada galería se cogen sus mejores fotos (nitidez + contraste + color); máximo TIRA_POR_GALERIA.
        def repartidas(lista, n):
            # las n mejores por nitidez, contraste y color, sin dos tomas casi iguales (ráfagas)
            elegidas = []
            for f in sorted(lista, key=lambda f: -f["calidad"]):
                if all(bin(f["huella"] ^ e["huella"]).count("1") > 100 and not _misma_rafaga(f, e) for e in elegidas):
                    elegidas.append(f)
                if len(elegidas) == n: break
            return elegidas
        filas = [gal["fotos"] for gal in galerias if gal["fotos"]]
        cupos = [min(TIRA_POR_GALERIA, len(f)) for f in filas]
        vistas, grupos = set(), []
        for f, n in zip(filas, cupos):
            grupo = []
            for foto_ in repartidas(f, n):
                clave = foto_["srcset"][0][1].rsplit("/", 1)[-1]   # la misma foto en dos galerías sale una vez
                if clave not in vistas: vistas.add(clave); grupo.append(foto_)
            grupos.append(grupo)
        destacadas = entremezclar(grupos)

    lista_servicios = []
    for s in services.get("lista", []):
        f = fotos_de(f"{C_SERVICIOS}/{s['carpeta']}")[:1]
        lista_servicios.append({**s, "foto": optimizar(f[0], f"services/{s['carpeta']}") if f else None})

    # Foto de arriba de Servicios y Contacto: su carpeta portada/ (si está vacía, la página sale sin foto)
    def portada_de(carpeta, destino):
        p = de_portadas(carpeta)
        return optimizar(p, destino) if p else None
    portada_servicios = portada_de(C_SERVICIOS, "services")
    portada_contacto = portada_de(C_CONTACTO, "contact")

    # Páginas: (id, ruta sin idioma, plantilla, datos extra)
    paginas = [("inicio", "", "inicio.html", {}),
               ("services", "services/", "services.html", {"portada_pagina": portada_servicios}),
               ("about", "about/", "about.html", {}),
               ("contact", "contact/", "contact.html", {"portada_pagina": portada_contacto})]
    for gal in galerias:
        paginas.append((f"galeria-{gal['id']}", f"work/{gal['url']}/", "galeria.html", {"galeria": gal}))

    # Iconos SVG locales (motor/assets/iconos/), incrustados en el HTML y coloreados con el color del texto
    iconos = {}
    for f in (MOTOR / "assets" / "iconos").glob("*.svg"):
        svg = f.read_text(encoding="utf-8")
        svg = re.sub(r"<title>.*?</title>", "", svg)
        svg = svg.replace('role="img"', 'aria-hidden="true" focusable="false" fill="currentColor" class="icono"')
        iconos[f.stem] = Markup(svg.strip())

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
                return rel + (PREFIJO_IMG if path.startswith("img/") else "") + path

            def srcset(foto, rel=rel):
                return ", ".join(f"{rel}{PREFIJO_IMG}{p} {w}w" for w, p in foto["srcset"])

            def foto(f, sizes="100vw", clase="", carga="lazy", alt="", rel=rel):
                alt = alt or f"{g['marca']} — {T(g['lema'])}"
                extra = ' fetchpriority="high"' if carga == "eager" else ""
                return Markup(
                    f'<img class="{escape(clase)}" src="{rel}{PREFIJO_IMG}{f["src"]}" srcset="{srcset(f)}" sizes="{sizes}" '
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
            if g["contacto"].get("instagram"): negocio["sameAs"] = ["https://www.instagram.com/" + g["contacto"]["instagram"] + "/"]
            grafo = [negocio]
            if ruta:
                migas = [("inicio", "")]
                elementos = [{"@type": "ListItem", "position": n + 1, "name": T(g["menu"][k]), "item": dom + "/" + prefijo + r}
                             for n, (k, r) in enumerate(migas)]
                nombre_actual = T(extra["galeria"]["titulo"]) if "galeria" in extra else T(g["menu"].get(pid, {}))
                elementos.append({"@type": "ListItem", "position": len(elementos) + 1, "name": nombre_actual,
                                  "item": dom + "/" + ruta_completa})
                grafo.append({"@type": "BreadcrumbList", "itemListElement": elementos})
            json_ld = Markup(json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False)
                             .replace("</", "<\\/"))

            html = env.get_template(plantilla).render(json_ld=json_ld,
                lang=lang, pid=pid, iconos=iconos, T=T, url=url, asset=asset, srcset=srcset, foto=foto,
                g=g, inicio=inicio, work=work, services=services, about=about, contact=contact,
                portada=portada[0] if portada else None, destacadas=destacadas,
                foto_about=foto_about[0] if foto_about else None, sobre=sobre,
                galerias=galerias, lista_servicios=lista_servicios,
                idiomas=otros_idiomas, alternos=alternos,
                canonical=g["dominio"].rstrip("/") + "/" + ruta_completa,
                tiene_compartir=bool(portada), logo=logo,
                # email de destino codificado (base64 al revés) para que no lo lean los robots de spam
                email_codificado=__import__("base64").b64encode((g["contacto"].get("email_formulario") or g["contacto"].get("email") or "").encode())[::-1].decode(),
                **extra,
            )
            out = SALIDA / ruta_completa / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            generadas.add(out)

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
    # Páginas que ya no existen (p. ej. una sección eliminada): se borran para que no queden huérfanas
    for viejo in SALIDA.rglob("index.html"):
        if viejo not in generadas:
            viejo.unlink()
            for d in [viejo.parent, *viejo.parent.parents]:
                if d == SALIDA or any(d.iterdir()): break
                d.rmdir()

    # Resumen
    total = sum(f.stat().st_size for f in IMG_DIR.rglob("*") if f.is_file()) if IMG_DIR.exists() else 0
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
