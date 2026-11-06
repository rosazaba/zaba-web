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
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageColor

RAIZ = Path(__file__).resolve().parent.parent
ORIG = RAIZ / "originales"
# Carpetas de originales/ (siguen el orden del menú). La portada y los trabajos son la misma página.
def _primera(*nombres):
    """La primera carpeta que exista (sirve con el nombre nuevo y con el antiguo mientras se renombra)."""
    return next((n for n in nombres if (ORIG / n).exists()), nombres[0])
C_TRABAJOS = _primera("1-servicio", "1-servicios", "1-trabajos")   # página «Servicios / My services»: portada/, seleccion/ y una carpeta por galería
C_PORTADA = f"{C_TRABAJOS}/portada"    # la foto grande de arriba (cada galería tiene además su <galería>/portada/)
C_SELECCION = f"{C_TRABAJOS}/seleccion"
C_SOBRE_MI = _primera("2-sobre-mi", "3-sobre-mi")
C_CONTACTO = _primera("3-contacto", "4-contacto")   # solo su carpeta portada/ (foto del fondo-mural de Contacto)
C_SERVICIOS = _primera("4-tarifa", "2-tarifa", "2-servicios")   # página «Tarifa / Rates» (dentro de «Más»): portada/ y <servicio>/
C_PRINT = _primera("6-tienda-de-impresiones", "6-tienda de impresiones", "5-tienda-de-impresiones", "5-tienda de impresiones", "5-tienda", "5-print-store")   # página «Tienda de impresiones / Print Store»: portada/ (cabecera) y las fotos que se venden impresas (las 2 primeras salen en las estancias)
C_CURSO = _primera("5-curso-foto-sub", "6-curso-foto-sub")   # página «Curso foto sub»: teoria/, practica/ y edicion/ (una foto en cada una)
C_VIAJES = _primera("8-viajes")   # página «Viajes / Trips» (dentro de «Más»): portada/ (opcional), una carpeta por viaje y anteriores/
C_ENCUENTRA = _primera("7-encuentra-tus-fotos", "6-encuentra-tus-fotos")  # (antes 6-encuentra-tus-fotos) portada/ (cabecera) y <playa>/<AAAA-MM-DD>/ con las fotos de cada sesión
# Rutas escritas en textos/*.yml con el nombre antiguo de una carpeta siguen funcionando
ALIAS_CARPETAS = {"1-trabajos": C_TRABAJOS, "1-servicios": C_TRABAJOS, "1-servicio": C_TRABAJOS, "2-servicios": C_SERVICIOS, "2-tarifa": C_SERVICIOS,
                  "5-tienda": C_PRINT, "5-tienda-de-impresiones": C_PRINT, "5-tienda de impresiones": C_PRINT, "5-print-store": C_PRINT,
                  "6-encuentra-tus-fotos": C_ENCUENTRA, "7-encuentra-tus-fotos": C_ENCUENTRA,
                  "4-tarifa": C_SERVICIOS, "2-sobre-mi": C_SOBRE_MI, "3-sobre-mi": C_SOBRE_MI, "3-contacto": C_CONTACTO, "4-contacto": C_CONTACTO,
                  "6-tienda-de-impresiones": C_PRINT, "6-tienda de impresiones": C_PRINT, "5-curso-foto-sub": C_CURSO, "6-curso-foto-sub": C_CURSO, "8-viajes": C_VIAJES}


def en_orig(ruta):
    """Ruta dentro de originales/ con la carpeta de primer nivel actualizada si se ha renombrado."""
    if not ruta: return None
    primera, _, resto = str(ruta).partition("/")
    return ORIG / ALIAS_CARPETAS.get(primera, primera) / resto
BANCOS_IMAGENES = ("unsplash", "pexels", "pixabay", "shutterstock", "istock", "adobestock", "freepik")
NO_SON_GALERIAS = {"portada", "portadas", "seleccion", "fotos-banco-imagenes"}
PRECIO_FOTO_DEFECTO = "15 €"
FOTOS_TIENDA_POR_GALERIA = 12   # Tienda sin fotos propias: cuántas fotos de cada galería se pueden elegir
# Menú (en este orden) y la dirección de cada página
RUTAS = {"inicio": "", "services": "rates/", "print": "print-store/", "curso": "underwater-photo-course/",
         "encuentra": "find-your-photos/", "viajes": "trips/", "about": "about/", "contact": "contact/"}
# Menú: apartados principales y, dentro del desplegable «Más», el resto (en este orden)
MENU_PRINCIPAL = ["inicio", "about", "contact"]
MENU_MAS = ["services", "curso", "print", "encuentra", "viajes"]
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



# ── Mapa de Viajes: mapa del mundo (Natural Earth, dominio público, simplificado en motor/datos/mundo.json)
#    en proyección Equal Earth, recortado en vertical (4:5) alrededor de los destinos que tienen «mapa» en viajes.yml.
def mapa_viajes(lista):
    import math
    A1, A2, A3, A4, M = 1.340264, -0.081106, 0.000893, 0.003796, math.sqrt(3) / 2
    def proy(lon, lat):
        l, f = math.radians(lon), math.radians(lat)
        t = math.asin(M * math.sin(f)); t2 = t * t; t6 = t2 ** 3
        x = 2 * math.sqrt(3) * l * math.cos(t) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
        y = t * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
        return x, -y
    puntos = [(v["carpeta"], v["mapa"]) for v in lista if v.get("mapa")]
    if not puntos:
        return None
    pp = [proy(m["lon"], m["lat"]) for _, m in puntos]
    xs, ys = [p[0] for p in pp], [p[1] for p in pp]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    w = max((max(xs) - min(xs)) * 1.5, proy(130, 0)[0])        # como mínimo ~130° de ancho: se ve en qué parte del mundo está
    h = max((max(ys) - min(ys)) * 1.5, w * 5 / 4); w = h * 4 / 5   # vertical 4:5
    x0, y0 = cx - w / 2, cy - h / 2 - h * 0.12   # algo más de norte: arriba va la frase
    W, H = 400, 500
    def a_svg(x, y):
        return (x - x0) / w * W, (y - y0) / h * H
    paises_de = {}
    for carpeta, m in puntos:
        for iso in m.get("paises", []):
            paises_de.setdefault(iso, []).append(carpeta)
    datos = json.loads((MOTOR / "datos" / "mundo.json").read_text())
    caminos = []
    for iso, anillos in datos.items():
        trozos = []
        for an in anillos:
            pts = [a_svg(*proy(lon, lat)) for lon, lat in an]
            if max(p[0] for p in pts) < -20 or min(p[0] for p in pts) > W + 20 or max(p[1] for p in pts) < -20 or min(p[1] for p in pts) > H + 20:
                continue
            trozos.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z")
        if trozos:
            caminos.append({"d": "".join(trozos), "viajes": " ".join(paises_de.get(iso, []))})
    marcas = [{"carpeta": c, "x": round(a_svg(*p)[0], 1), "y": round(a_svg(*p)[1], 1)} for (c, _), p in zip(puntos, pp)]
    return {"ancho": W, "alto": H, "paises": caminos, "marcas": marcas}

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


def ordenar_variado(fotos, primeras, carpeta):
    """Orden de un apartado: primero las fotos de «primeras» (work.yml, elegidas para que la tira de 6 sea variada:
    salto, descenso, vida marina, retrato, paisaje, contraluz…) y después el resto, sin dejar juntas fotos parecidas
    (color, composición o misma ráfaga) y dando preferencia a las mejores."""
    import math
    por_nombre = {f["origen"]: f for f in fotos}
    elegidas = []
    for n in primeras:
        if n in por_nombre and por_nombre[n] not in elegidas:
            elegidas.append(por_nombre[n])
        else:
            avisos.append(f"«primeras» de {carpeta}: no encuentro {n} (¿la has movido o renombrado?).")
    resto = [f for f in fotos if f not in elegidas]
    if not resto:
        return elegidas
    cal = [f["calidad"] for f in resto]; lo, hi = min(cal), max(cal)
    def distancia(a, b):
        d = math.dist(a["lab"], b["lab"]) / 40 + bin(a["huella"] ^ b["huella"]).count("1") / 128
        return d * (0.3 if _misma_rafaga(a, b) else 1)
    while resto:
        def puntos(f):
            cerca = min((distancia(f, e) for e in elegidas[-4:]), default=1)
            return min(cerca, 1.5) + 0.5 * ((f["calidad"] - lo) / ((hi - lo) or 1))
        mejor = max(resto, key=puntos)
        elegidas.append(mejor); resto.remove(mejor)
    return elegidas


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
        "origen_ruta": src.relative_to(ORIG).as_posix() if ORIG in src.parents else str(src),
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


# ── «Encuentra tus fotos»: vistas previas pequeñas con marca de agua ──
ANCHO_MARCA = 960          # las fotos a la venta solo se publican a este tamaño y con marca de agua


def con_marca(src: Path, destino_rel: str, codigo: str):
    """Vista previa protegida: pequeña, con el logo repetido en diagonal y el código de la foto."""
    from PIL import ImageDraw
    carpeta = IMG_DIR / destino_rel
    carpeta.mkdir(parents=True, exist_ok=True)
    out = carpeta / f"{slug(codigo)}.webp"
    generadas.add(out)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((ANCHO_MARCA, ANCHO_MARCA), Image.LANCZOS)
        w, h = im.size
        if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
            capa = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
            logo_marca = next((p for p in [ORIG / "logo" / "logo-claro.png", ORIG / "logo" / "logo-oscuro.png"] if p.exists()), None)
            if logo_marca:
                with Image.open(logo_marca) as lg:
                    lg = lg.convert("RGBA")
                    lg.thumbnail((int(w * .26), int(w * .26)), Image.LANCZOS)
                    blanco = Image.new("RGBA", lg.size, (255, 255, 255, 0))
                    blanco.putalpha(lg.getchannel("A").point(lambda a: int(a * .42)))
                    paso_x, paso_y = int(lg.width * 1.45), int(lg.height * 3.2)
                    for fila, y in enumerate(range(0, capa.height, paso_y)):
                        for x in range(-paso_x + (fila % 2) * paso_x // 2, capa.width, paso_x):
                            capa.alpha_composite(blanco, (x, y))
            capa = capa.rotate(24, resample=Image.BICUBIC)
            capa = capa.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
            base = im.convert("RGBA"); base.alpha_composite(capa)
            # banda inferior con el código, para que el cliente lo pueda citar
            d = ImageDraw.Draw(base)
            d.rectangle([0, h - 30, w, h], fill=(46, 41, 37, 150))
            d.text((12, h - 23), f"ZABA · {codigo}", fill=(255, 255, 255, 230))
            base.convert("RGB").save(out, "WEBP", quality=62, method=5)
    return {"codigo": codigo, "src": f"img/{destino_rel}/{out.name}", "ancho": w, "alto": h}


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
        candidata = en_orig(inicio["portada_foto"])
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
        p = en_orig(ruta) if ruta else None
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
        if c.get("primeras") and not c.get("apartados"):   # surf / dron: la tira de 6 la elige Rosa y el resto se mezcla sin juntar parecidas
            fotos = ordenar_variado(fotos, c["primeras"], carpeta)
        hay_en_apartados = any(fotos_de(f"{C_TRABAJOS}/{carpeta}/{a['carpeta']}") for a in (c.get("apartados") or []))
        if not fotos and not hay_en_apartados:
            if carpeta not in conf:
                avisos.append(f"La galería '{carpeta}' está vacía y no se publica.")
                continue
            avisos.append(f"La galería '{carpeta}' aún no tiene fotos: se muestra como «Próximamente».")
        # Apartados (solo si work.yml los define, p. ej. buceo: reportaje / buceo-100 / curso): cada uno su subcarpeta.
        apartados = []
        for a in c.get("apartados") or []:
            sub = f"{carpeta}/{a['carpeta']}"
            fa = [optimizar(p, f"work/{sub}") for p in fotos_de(f"{C_TRABAJOS}/{sub}")]
            fa = quitar_repetidas(fa, ya_vistas, sub)
            fa.sort(key=lambda f: f["origen"])
            fa = ordenar_variado(fa, a.get("primeras") or [], sub)
            if a.get("max") and len(fa) > int(a["max"]):
                avisos.append(f"Apartado «{sub}»: hay {len(fa)} fotos y se muestran {a['max']} (las de «primeras» y, después, las más variadas).")
                fa = fa[:int(a["max"])]
            apartados.append({"id": slug(a["carpeta"]), "titulo": a.get("titulo") or {i: a["carpeta"] for i in IDIOMAS},
                              "texto": a.get("texto") or {i: "" for i in IDIOMAS}, "fotos": fa})
        if c.get("apartados"):
            con_fotos = [a for a in apartados if a["fotos"]]
            if con_fotos and fotos:
                avisos.append(f"Hay {len(fotos)} fotos sueltas en {C_TRABAJOS}/{carpeta}/ que no salen en la galería: muévelas a "
                              + ", ".join(a["carpeta"] for a in c["apartados"]) + ".")
            elif not con_fotos and fotos:
                avisos.append(f"Los apartados de «{carpeta}» están vacíos: de momento la galería enseña las fotos sueltas, sin apartados.")
            # para la portada, la tira «Selección» y la Tienda cuentan todas las fotos de la galería
            fotos_pagina = None if not con_fotos else con_fotos
            fotos = fotos + [f for a in apartados for f in a["fotos"]]
            apartados = fotos_pagina or []
        galerias.append({
            "apartados": apartados,
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
        if not f and s.get("foto_provisional") and en_orig(s["foto_provisional"]).exists():   # mientras su carpeta esté vacía
            f = [en_orig(s["foto_provisional"])]
        lista_servicios.append({**s, "foto": optimizar(f[0], f"services/{s['carpeta']}") if f else None})

    # ── Curso foto sub: tres partes (teoría, práctica, edición) con una foto cada una ──
    curso = leer("curso")
    partes_curso = []
    for p_ in curso.get("partes", []):
        f = fotos_de(f"{C_CURSO}/{p_['carpeta']}")
        if not f and p_.get("foto_provisional") and en_orig(p_["foto_provisional"]).exists():
            f = [en_orig(p_["foto_provisional"])]
            avisos.append(f"Curso foto sub: {C_CURSO}/{p_['carpeta']}/ está vacía; de momento sale una foto de buceo de ejemplo.")
        partes_curso.append({**p_, "foto": optimizar(f[0], f"curso/{p_['carpeta']}") if f else None})

    # ── Viajes: una tarjeta por viaje (foto de 8-viajes/<carpeta>/ o foto_provisional) y tira de viajes anteriores ──
    viajes = leer("viajes")
    lista_viajes = []
    for v in viajes.get("lista", []):
        f = fotos_de(f"{C_VIAJES}/{v['carpeta']}")[:1]
        if not f and v.get("foto_provisional") and en_orig(v["foto_provisional"]).exists():
            f = [en_orig(v["foto_provisional"])]
        lista_viajes.append({**v, "foto": optimizar(f[0], f"viajes/{v['carpeta']}") if f else None})
    mapa = mapa_viajes(viajes.get("lista", []))
    fotos_viajes_anteriores = [optimizar(x, "viajes/anteriores") for x in fotos_de(f"{C_VIAJES}/anteriores")]

    # Foto de arriba de Servicios y Contacto: su carpeta portada/ (si está vacía, la página sale sin foto)
    def portada_de(carpeta, destino):
        p = de_portadas(carpeta)
        return optimizar(p, destino) if p else None
    portada_servicios = portada_de(C_SERVICIOS, "services")
    portada_contacto = portada_de(C_CONTACTO, "contact")

    # ── Tienda: estancias (salón, dormitorio, estudio…) con una foto enmarcada en la pared ──
    tienda = leer("print-store")
    portada_tienda = portada_de(C_PRINT, "print-store")
    # Estancias REALES: originales/5-tienda-de-impresiones/estancias/<tipo>-… (salon-…, dormitorio-…, estudio-…; fotos reales o de IA).
    # La foto que se cuelga en cada una: print-store.yml → estancias_reales.<tipo>.foto (ruta dentro de originales/).
    # Las fotos de las habitaciones no pasan por fotos_de(): pueden venir de un banco de imágenes (no son trabajo suyo).
    carpeta_est = ORIG / C_PRINT / "estancias"
    conf_est = tienda.get("estancias_reales") or {"salon": {}, "dormitorio": {}}
    reserva = fotos_de(C_PRINT)[:len(conf_est)]
    if len(reserva) < len(conf_est):
        # sin foto indicada: las mejores fotos horizontales de galerías distintas
        candidatas = []
        for gal in galerias:
            horiz = sorted([f for f in gal["fotos"] if f["ratio"] > 1.25], key=lambda f: -f["calidad"])
            if horiz: candidatas.append(ORIG / horiz[0]["origen_ruta"])
        reserva += candidatas
    estancias = []
    for tipo, c in conf_est.items():
        c = c or {}
        src = en_orig(c["foto"]) if c.get("foto") and en_orig(c["foto"]).exists() else None
        if c.get("foto") and not src:
            avisos.append(f"Tienda: no encuentro la foto de la estancia «{tipo}»: {c['foto']}")
        if not src:
            src = reserva.pop(0) if reserva else None
        # la habitación: «habitacion:» en print-store.yml o, si no, el archivo que empieza por el nombre de la estancia
        if c.get("habitacion"):
            sala = carpeta_est / c["habitacion"]
            if not sala.exists():
                avisos.append(f"Tienda: no encuentro la habitación de la estancia «{tipo}»: {C_PRINT}/estancias/{c['habitacion']}")
                sala = None
        else:
            sala = next((p for p in sorted(carpeta_est.glob("*")) if p.suffix.lower() in EXT
                         and slug(p.stem).startswith(tipo)), None) if carpeta_est.exists() else None
        e = {"tipo": tipo, "foto": None, "real": None}
        if not src:
            continue
        if not sala:
            if tipo in ("salon", "dormitorio"):          # ilustración SVG de reserva
                e["foto"] = optimizar(src, "print-store"); estancias.append(e)
            continue
        out = IMG_DIR / "print-store" / f"estancia-{tipo}.webp"
        out.parent.mkdir(parents=True, exist_ok=True)
        generadas.add(out)
        with Image.open(sala) as fondo, Image.open(src) as cuadro:
            fondo = ImageOps.exif_transpose(fondo).convert("RGB")
            fondo.thumbnail((2000, 2000), Image.LANCZOS)
            W, H = fondo.size
            cuadro = ImageOps.exif_transpose(cuadro).convert("RGB")
            if c.get("girar"):
                cuadro = cuadro.rotate(-float(c["girar"]), expand=True)     # grados en el sentido del reloj
            def guardar(img, centro_px):
                """Las tres estancias salen cuadradas (misma altura en la Tienda), centradas en el cuadro."""
                lado = min(img.size)
                x = min(max(0, round(centro_px - lado / 2)), img.width - lado)
                y = (img.height - lado) // 2 if img.height > lado else 0
                img = img.crop((x, y, x + lado, y + lado))
                img.save(out, "WEBP", quality=82, method=5)
                e["real"] = {"src": f"img/print-store/{out.name}", "ancho": lado, "alto": lado}
            def con_paspartu(ancho_l, alto_l, refs):
                """La foto entera (sin recortar) sobre un paspartú del tamaño del lienzo. El paspartú toma la luz de la
                pared a ambos lados del cuadro (algo más clara) y lleva una sombra fina en el borde, como en un marco real."""
                import numpy as np
                foto = cuadro
                if c.get("luz"):                       # habitaciones con poca luz: la foto algo más oscura, como la vería el ojo
                    foto = Image.eval(foto, lambda v, k=float(c["luz"]): min(255, round(v * k)))
                pas = c.get("paspartu", True)
                if pas is False:
                    return ImageOps.fit(foto, (ancho_l, alto_l), Image.LANCZOS)
                if isinstance(pas, str):               # color fijo, p. ej. "#121212" (paspartú negro)
                    capa = np.ones((alto_l, ancho_l, 3)) * np.array(ImageColor.getrgb(pas), float)
                else:
                    izq, der = (np.array(fondo.crop(r).resize((1, 1), Image.BOX).getpixel((0, 0)), float) for r in refs)
                    t = np.linspace(0, 1, ancho_l)[None, :, None]
                    capa = (1 - t) * izq + t * der
                    capa = np.repeat(capa, alto_l, axis=0) * 1.05 + 5
                # sombra interior: más marcada arriba (la luz viene de arriba) y suave en los lados
                yy = np.arange(alto_l)[:, None]; xx = np.arange(ancho_l)[None, :]
                d = max(3, round(min(ancho_l, alto_l) * 0.012))
                sombra = 1 - 0.28 * np.exp(-yy / d) - 0.16 * np.exp(-xx / d) - 0.16 * np.exp(-(ancho_l - 1 - xx) / d) - 0.10 * np.exp(-(alto_l - 1 - yy) / d)
                base = Image.fromarray(np.clip(capa * sombra[:, :, None], 0, 255).astype("uint8"))
                m = round(min(ancho_l, alto_l) * float(c.get("margen", 7.5)) / 100)
                f = foto.copy(); f.thumbnail((ancho_l - 2 * m, alto_l - 2 * m), Image.LANCZOS)
                base.paste(f, ((ancho_l - f.width) // 2, (alto_l - f.height) // 2))
                return base
            if c.get("recorte"):                                            # proporción ancho/alto, p. ej. 1.5
                rw = float(c["recorte"])
                cw, ch = (cuadro.width, round(cuadro.width / rw)) if cuadro.width / cuadro.height < rw else (round(cuadro.height * rw), cuadro.height)
                cuadro = ImageOps.fit(cuadro, (cw, ch), Image.LANCZOS)
            if c.get("esquinas"):
                # la foto sustituye el lienzo de un cuadro que ya está en la habitación, aunque se vea en perspectiva:
                # esquinas [[x, y] arriba-izq, arriba-der, abajo-der, abajo-izq] en %
                dst = [(v[0] / 100 * W, v[1] / 100 * H) for v in c["esquinas"]]
                ancho_l = max(abs(dst[1][0] - dst[0][0]), abs(dst[2][0] - dst[3][0]))
                alto_l = max(abs(dst[3][1] - dst[0][1]), abs(dst[2][1] - dst[1][1]))
                cw, ch = round(ancho_l * 2), round(alto_l * 2)
                xs = [p[0] for p in dst]; ys = [p[1] for p in dst]
                refs = ((round(min(xs) - W * 0.06), round(min(ys)), round(min(xs) - W * 0.02), round(max(ys))),
                        (round(max(xs) + W * 0.02), round(min(ys)), round(max(xs) + W * 0.06), round(max(ys))))
                lienzo = con_paspartu(cw, ch, refs)
                src_pts = [(0, 0), (cw, 0), (cw, ch), (0, ch)]
                # coeficientes de la transformación (de cada punto de la habitación al punto del lienzo)
                import numpy as np
                A, B = [], []
                for (X, Y), (u, v) in zip(dst, src_pts):
                    A += [[X, Y, 1, 0, 0, 0, -u * X, -u * Y], [0, 0, 0, X, Y, 1, -v * X, -v * Y]]; B += [u, v]
                coef = np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()
                capa = lienzo.transform(fondo.size, Image.PERSPECTIVE, coef, Image.BICUBIC)
                mascara = Image.new("L", fondo.size, 0)
                ImageDraw.Draw(mascara).polygon(dst, fill=255)
                fondo.paste(capa, (0, 0), mascara.filter(ImageFilter.GaussianBlur(0.6)))
                guardar(fondo, sum(xs) / 4)
                estancias.append(e)
                continue
            if c.get("hueco"):
                # la foto sustituye el lienzo de un cuadro que ya está en la habitación: [x0, y0, x1, y1] en %
                x0, y0, x1, y1 = (round(v / 100 * (W if i % 2 == 0 else H)) for i, v in enumerate(c["hueco"]))
                refs = ((max(0, x0 - round(W * 0.06)), y0, max(1, x0 - round(W * 0.03)), y1),
                        (min(W - 2, x1 + round(W * 0.03)), y0, min(W - 1, x1 + round(W * 0.06)), y1))
                fondo.paste(con_paspartu(x1 - x0, y1 - y0, refs), (x0, y0))
                guardar(fondo, (x0 + x1) / 2)
                estancias.append(e)
                continue
            # marco de roble fino y paspartú blanco (grosor relativo al ancho de la habitación)
            con_marco = c.get("marco", True)
            borde = (max(4, round(W * 0.008)) if con_marco else 0, round(W * 0.025) if con_marco else 0)
            b = sum(borde)
            # tamaño del cuadro entero: por «ancho» o por «alto» (en % de la foto de la estancia)
            cx, cy = float(c.get("centro_x", 50)) / 100, float(c.get("centro_y", 33)) / 100
            r = cuadro.height / cuadro.width
            if c.get("alto"):
                h = round(H * float(c["alto"]) / 100); fh = h - 2 * b; fw = round(fh / r); w = fw + 2 * b
            else:
                w = round(W * float(c.get("ancho", 34)) / 100); fw = w - 2 * b; fh = round(fw * r); h = fh + 2 * b
            x, y = round(W * cx - w / 2), round(H * cy - h / 2)
            if con_marco:
                # sombra de contacto muy suave en la pared (para que no parezca pegado)
                sombra = Image.new("L", fondo.size, 0)
                ImageDraw.Draw(sombra).rectangle((x + 2, y + 6, x + w + 2, y + h + 8), fill=70)
                sombra = sombra.filter(ImageFilter.GaussianBlur(max(6, w // 60)))
                fondo = Image.composite(Image.new("RGB", fondo.size, (60, 52, 45)), fondo, sombra)
                d = ImageDraw.Draw(fondo)
                d.rectangle((x, y, x + w - 1, y + h - 1), fill=(176, 138, 98))                   # roble
                d.rectangle((x + borde[0], y + borde[0], x + w - borde[0] - 1, y + h - borde[0] - 1), fill=(246, 244, 239))  # paspartú
            fondo.paste(cuadro.resize((fw, fh), Image.LANCZOS), (x + b, y + b))   # la foto entera, sin recortar
            guardar(fondo, x + w / 2)
        estancias.append(e)
    if not any(e["real"] for e in estancias):
        avisos.append(f"La Tienda usa las estancias dibujadas: pon fotos de habitaciones en originales/{C_PRINT}/estancias/.")
    # «Elige tu foto» (paso 1): una pestaña por galería (Surf, Buceo, Dron) con las fotos que la usuaria pone a la venta
    # en originales/5-tienda-de-impresiones/<galería>/. Si esa carpeta está vacía, de ejemplo salen las mejores de la galería.
    # Cada foto lleva un código corto (SURF-03, por su orden en la carpeta) que se apunta solo en el formulario de pedido.
    grupos_tienda = []
    for gal in galerias:
        venta = [optimizar(p, f"print-store/{gal['id']}") for p in fotos_de(f"{C_PRINT}/{gal['id']}")]
        if not venta and gal["fotos"]:
            avisos.append(f"Tienda: {C_PRINT}/{gal['id']}/ está vacía; de ejemplo salen fotos de la galería «{gal['id']}».")
        if venta or gal["fotos"]:
            grupos_tienda.append({"id": gal["id"], "titulo": gal["titulo"], "fotos": venta or gal["fotos"], "ejemplo": not venta})
    for gr in grupos_tienda:
        pre = slug(gr["id"]).upper().replace("-", "")[:8]
        # el código sale del orden (no cambia aunque se muestren menos)
        todas = [{"foto": f, "codigo": f"{pre}-{n:02d}"} for n, f in enumerate(gr["fotos"], 1)]
        if gr["ejemplo"] and len(todas) > FOTOS_TIENDA_POR_GALERIA:
            # ejemplo sacado de la galería: solo las mejores (nitidez, contraste y color), en su orden
            mejores = sorted(todas, key=lambda x: -x["foto"].get("calidad", 0))[:FOTOS_TIENDA_POR_GALERIA]
            todas = [x for x in todas if x in mejores]
        gr["fotos"] = todas

    # ── Encuentra tus fotos: playa → sesión (fecha) → fotos con marca de agua y código ──
    encuentra = leer("encuentra")
    portada_encuentra = portada_de(C_ENCUENTRA, "encuentra")
    if not portada_encuentra:
        # sin foto en 6-encuentra-tus-fotos/portada/: una foto horizontal de acción de surf (no la del surfista en el agua)
        surf = next((gal["fotos"] for gal in galerias if gal["id"] == "surf"), [])
        horiz = sorted([f for f in surf if f["ratio"] > 1.2 and "05313" not in f["origen"]], key=lambda f: -f["calidad"])
        portada_encuentra = horiz[0] if horiz else None
    precio_foto = encuentra.get("precio_foto") or PRECIO_FOTO_DEFECTO
    playas = []
    for loc in encuentra.get("localizaciones", []):
        base = ORIG / C_ENCUENTRA / loc["carpeta"]
        sesiones = []
        if base.exists():
            for d in sorted((d for d in base.iterdir() if d.is_dir() and d.name != "portada"), key=lambda d: d.name, reverse=True):
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", d.name)
                if not m:
                    avisos.append(f"Sesión con nombre que no es una fecha AAAA-MM-DD, no se publica: {d.relative_to(ORIG)}")
                    continue
                fotos_sesion = [con_marca(p, f"encuentra/{loc['carpeta']}/{d.name}",
                                          f"{loc['codigo']}-{''.join(m.groups())}-{n:03d}")
                                for n, p in enumerate(fotos_de(d.relative_to(ORIG).as_posix()), 1)]
                if fotos_sesion:
                    fecha = "-".join(m.groups())
                    sesiones.append({"fecha": fecha, "fecha_corta": f"{m.group(3)}/{m.group(2)}/{m.group(1)}",
                                     "dia_mes": f"{m.group(3)}.{m.group(2)}", "fotos": fotos_sesion,
                                     # cada sesión tiene su página: find-your-photos/<playa>-<AAAA-MM-DD>/
                                     "ruta": f"{RUTAS['encuentra']}{loc['carpeta']}-{fecha}/"})
        playas.append({**loc, "sesiones": sesiones, "n_fotos": sum(len(x["fotos"]) for x in sesiones)})

    # Páginas: (id, ruta sin idioma, plantilla, datos extra)
    # Rutas de las páginas del menú (sin idioma). Las mismas en los tres idiomas.
    paginas = [("inicio", "", "inicio.html", {}),
               ("services", RUTAS["services"], "services.html", {"portada_pagina": portada_servicios}),
               ("print", RUTAS["print"], "print-store.html", {"portada_pagina": portada_tienda}),
               ("curso", RUTAS["curso"], "curso.html", {}),
               ("encuentra", RUTAS["encuentra"], "encuentra.html", {"portada_pagina": portada_encuentra}),
               ("viajes", RUTAS["viajes"], "viajes.html", {}),
               ("about", RUTAS["about"], "about.html", {}),
               ("contact", RUTAS["contact"], "contact.html", {"portada_pagina": portada_contacto})]
    for gal in galerias:
        paginas.append((f"galeria-{gal['id']}", f"work/{gal['url']}/", "galeria.html", {"galeria": gal}))
    # Encuentra tus fotos: una página por sesión (la marca del menú sigue en «Encuentra tus fotos»)
    for pl in playas:
        for ses in pl["sesiones"]:
            paginas.append(("encuentra", ses["ruta"], "encuentra-sesion.html",
                            {"playa": pl, "sesion": ses, "miga": f"{pl['nombre']} · {ses['fecha_corta']}"}))

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
                migas = [("inicio", "")] + ([("encuentra", RUTAS["encuentra"])] if "miga" in extra else [])
                elementos = [{"@type": "ListItem", "position": n + 1, "name": T(g["menu"][k]), "item": dom + "/" + prefijo + r}
                             for n, (k, r) in enumerate(migas)]
                nombre_actual = (T(extra["galeria"]["titulo"]) if "galeria" in extra
                                 else extra["miga"] if "miga" in extra else T(g["menu"].get(pid, {})))
                elementos.append({"@type": "ListItem", "position": len(elementos) + 1, "name": nombre_actual,
                                  "item": dom + "/" + ruta_completa})
                grafo.append({"@type": "BreadcrumbList", "itemListElement": elementos})
            json_ld = Markup(json.dumps({"@context": "https://schema.org", "@graph": grafo}, ensure_ascii=False)
                             .replace("</", "<\\/"))

            html = env.get_template(plantilla).render(json_ld=json_ld,
                lang=lang, pid=pid, iconos=iconos, T=T, url=url, asset=asset, srcset=srcset, foto=foto,
                g=g, inicio=inicio, work=work, services=services, about=about, contact=contact,
                rutas=RUTAS, menu_principal=MENU_PRINCIPAL, menu_mas=MENU_MAS, curso=curso, partes_curso=partes_curso, viajes=viajes, lista_viajes=lista_viajes, mapa_viajes=mapa, fotos_viajes_anteriores=fotos_viajes_anteriores, tienda=tienda, estancias=estancias, grupos_tienda=grupos_tienda, encuentra=encuentra, playas=playas, precio_foto=precio_foto,
                portada=portada[0] if portada else None, destacadas=destacadas,
                foto_about=foto_about[0] if foto_about else None, sobre=sobre,
                galerias=galerias, lista_servicios=lista_servicios,
                idiomas=otros_idiomas, alternos=alternos,
                canonical=g["dominio"].rstrip("/") + "/" + ruta_completa,
                tiene_compartir=bool(portada), logo=logo,
                # email de destino codificado (base64 al revés) para que no lo lean los robots de spam
                email_icono_codificado=__import__("base64").b64encode((g["contacto"].get("email_icono") or "").encode())[::-1].decode(),
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
