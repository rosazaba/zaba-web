#!/usr/bin/env python3
"""
Revisión automática de la web generada (docs/) y de los textos.

  python motor/revisar.py

Se ejecuta solo al final de build.py. Si hay ERRORES, no se debe publicar.
Los AVISOS no bloquean, pero conviene resolverlos.
"""
import json, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
TEXTOS = RAIZ / "textos"
IDIOMAS = ["en", "es", "fr"]
PESO_MAX_FOTO = 600_000      # bytes
TITULO_MAX, DESC_MIN, DESC_MAX = 65, 50, 165


class Pagina(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None; self.titulos = []; self.h1 = 0; self.metas = {}; self.links = []
        self.hreflang = {}; self.canonical = None; self.imgs = []; self.refs = []; self.ids = set()
        self.jsonld = []; self._en = None; self._buf = ""
        self.codigos = []; self.comprar = []; self.estancias = 0; self.menu = []; self._en_menu = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        if tag == "html": self.lang = a.get("lang")
        elif tag == "title": self._en, self._buf = "title", ""
        elif tag == "h1": self.h1 += 1
        elif tag == "meta":
            k = a.get("name") or a.get("property")
            if k: self.metas[k] = a.get("content", "")
        elif tag == "link":
            rel = a.get("rel", "")
            if rel == "canonical": self.canonical = a.get("href")
            elif rel == "alternate" and a.get("hreflang"): self.hreflang[a["hreflang"]] = a.get("href")
            elif a.get("href") and rel in ("stylesheet", "icon"): self.refs.append(("link", a["href"]))
        elif tag == "script":
            if a.get("type") == "application/ld+json": self._en, self._buf = "jsonld", ""
            elif a.get("src"): self.refs.append(("script", a["src"]))
        elif tag == "image" and a.get("href"):          # foto dentro de las estancias ilustradas (SVG)
            self.refs.append(("img", a["href"]))
            self.estancias += 1
        elif tag == "nav" and a.get("id") == "menu":
            self._en_menu = True
        elif tag == "li" and "data-codigo" in a:
            self.codigos.append(a["data-codigo"])
        elif tag == "img":
            self.imgs.append(a)
            if a.get("src"): self.refs.append(("img", a["src"]))
            for parte in (a.get("srcset") or "").split(","):
                if parte.strip(): self.refs.append(("img", parte.strip().split()[0]))
        elif tag == "a" and a.get("href"):
            if self._en_menu and a.get("href") and not a.get("hreflang"): self.menu.append(a["href"])
            if "wa.me" in a["href"] and "text=" in a["href"]: self.comprar.append(a["href"])
            self.refs.append(("a", a["href"]))
            if a.get("target") == "_blank" and "noopener" not in (a.get("rel") or ""):
                self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "nav": self._en_menu = False
        if tag in ("title", "script") and self._en:
            (self.titulos if self._en == "title" else self.jsonld).append(self._buf.strip())
            self._en = None

    def handle_data(self, data):
        if self._en: self._buf += data


def destino(pagina: Path, href: str):
    """Convierte un enlace relativo en un archivo de docs/. None si es externo."""
    partes = urlsplit(href)
    if partes.scheme or href.startswith(("mailto:", "tel:", "//", "data:")):
        return None, None
    ruta = unquote(partes.path)
    if not ruta:
        return pagina, partes.fragment
    p = (pagina.parent / ruta).resolve()
    if ruta.endswith("/") or p.is_dir():
        p = p / "index.html"
    return p, partes.fragment


def revisar_textos(errores, avisos):
    def recorrer(nodo, ruta, archivo):
        if isinstance(nodo, dict):
            claves = set(nodo)
            if claves & set(IDIOMAS):
                for l in IDIOMAS:
                    v = nodo.get(l)
                    if v in (None, "", []):
                        errores.append(f"Falta traducción '{l}' en textos/{archivo} → {ruta}")
                if isinstance(nodo.get("en"), list):
                    largos = {l: len(nodo.get(l) or []) for l in IDIOMAS}
                    if len(set(largos.values())) > 1:
                        avisos.append(f"Distinto número de elementos por idioma en textos/{archivo} → {ruta}: {largos}")
                return
            for k, v in nodo.items():
                recorrer(v, f"{ruta}.{k}" if ruta else k, archivo)
        elif isinstance(nodo, list):
            for i, v in enumerate(nodo):
                recorrer(v, f"{ruta}[{i}]", archivo)

    for f in sorted(TEXTOS.glob("*.yml")):
        try:
            datos = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errores.append(f"textos/{f.name} tiene un error de formato (revisa comillas y sangría): {e}")
            continue
        recorrer(datos, "", f.name)

    g = yaml.safe_load((TEXTOS / "general.yml").read_text(encoding="utf-8"))
    c = g.get("contacto", {})
    if not (c.get("email_formulario") or c.get("email")):
        errores.append("Falta el email de destino del formulario (textos/general.yml → contacto.email_formulario)")
    if not c.get("instagram"): avisos.append("Pendiente: usuario de Instagram (textos/general.yml → contacto.instagram)")
    if not c.get("web3forms_clave"): avisos.append("Pendiente: clave de Web3Forms; el formulario abrirá el correo del visitante en vez de enviarse solo")
    return g


def main():
    errores, avisos = [], []
    g = revisar_textos(errores, avisos)
    dominio = g["dominio"].rstrip("/")

    paginas = sorted(DOCS.rglob("*.html"))
    if not paginas:
        print("✗ No hay páginas en docs/. Ejecuta primero motor/build.py"); return 1

    analizadas, titulos = {}, {}
    for p in paginas:
        a = Pagina(); a.feed(p.read_text(encoding="utf-8")); analizadas[p] = a

    for p, a in analizadas.items():
        rel = p.relative_to(DOCS).as_posix()
        ruta = rel[:-len("index.html")]
        lang = ruta.split("/")[0] if ruta.split("/")[0] in IDIOMAS[1:] else IDIOMAS[0]
        E = lambda m: errores.append(f"{rel}: {m}")
        A = lambda m: avisos.append(f"{rel}: {m}")

        # Idioma y estructura
        if a.lang != lang: E(f"lang='{a.lang}' y debería ser '{lang}'")
        if len(a.titulos) != 1 or not a.titulos[0]: E("debe tener exactamente un <title>")
        else:
            t = a.titulos[0]
            if len(t) > TITULO_MAX: A(f"título largo ({len(t)} caracteres, Google corta a ~{TITULO_MAX}): «{t}»")
            titulos.setdefault((lang, t), []).append(rel)
        if a.h1 != 1: E(f"tiene {a.h1} H1 (debe haber exactamente uno)")

        # Descripción y redes sociales
        d = a.metas.get("description", "")
        if not d: E("falta meta description")
        elif not DESC_MIN <= len(d) <= DESC_MAX: A(f"meta description de {len(d)} caracteres (ideal {DESC_MIN}–{DESC_MAX})")
        for k in ("og:title", "og:description", "og:url"):
            if not a.metas.get(k): E(f"falta {k}")
        if not a.metas.get("og:image"): A("falta og:image (vista previa al compartir): pon una foto de portada")
        if "viewport" not in a.metas: E("falta meta viewport (móvil)")

        # Canonical y hreflang
        esperado = f"{dominio}/{ruta}"
        if a.canonical != esperado: E(f"canonical '{a.canonical}' debería ser '{esperado}'")
        for l in IDIOMAS + ["x-default"]:
            if l not in a.hreflang: E(f"falta hreflang '{l}'")
        for l in IDIOMAS:
            h = a.hreflang.get(l, "")
            otra = DOCS / (h[len(dominio) + 1:] if h.startswith(dominio) else "x") / "index.html"
            if h and not otra.exists(): E(f"hreflang '{l}' apunta a una página que no existe: {h}")

        # Datos estructurados
        if not a.jsonld: E("faltan datos estructurados (JSON-LD)")
        for j in a.jsonld:
            try: json.loads(j)
            except ValueError: E("JSON-LD mal formado")

        # Imágenes
        for img in a.imgs:
            if img.get("aria-hidden") == "true": continue   # imagen decorativa duplicada (p. ej. logo claro)
            if not (img.get("alt") or "").strip(): E(f"imagen sin texto alternativo: {img.get('src')}")
            if not img.get("width") or not img.get("height"): A(f"imagen sin width/height (provoca saltos al cargar): {img.get('src')}")

        # Enlaces internos y recursos
        for tipo, href in a.refs:
            archivo, ancla = destino(p, href)
            if archivo is None: continue
            if not archivo.exists():
                E(f"enlace roto ({tipo}): {href}")
            elif ancla and archivo.suffix == ".html":
                destino_pag = analizadas.get(archivo)
                if destino_pag and ancla not in destino_pag.ids: E(f"el ancla #{ancla} no existe en {href}")
        for href in a.links:
            A(f"enlace externo sin rel=noopener: {href}")

    for (lang, t), lista in titulos.items():
        if len(lista) > 1: errores.append(f"Título repetido en {lang} «{t}»: {', '.join(lista)}")

    # Menú: mismo número de apartados en todas las páginas
    n_menu = {len(a.menu) for a in analizadas.values()}
    if len(n_menu) > 1: errores.append(f"El menú no tiene los mismos apartados en todas las páginas: {sorted(n_menu)}")
    # Encuentra tus fotos: códigos únicos y botón «Comprar» con el código de cada foto
    todos = []
    for p, a in analizadas.items():
        rel = p.relative_to(DOCS).as_posix()
        if not rel.startswith(("find-your-photos", "es/find-your-photos", "fr/find-your-photos")): continue
        if len(set(a.codigos)) != len(a.codigos): errores.append(f"{rel}: hay fotos con el código repetido")
        for c in a.codigos:
            if not any(c in u for u in a.comprar): errores.append(f"{rel}: la foto {c} no tiene botón de compra con su código")
        if rel.startswith("find-your-photos"): todos += a.codigos
    # Print Store: las dos estancias con su foto
    for p, a in analizadas.items():
        rel = p.relative_to(DOCS).as_posix()
        if rel.endswith("print-store/index.html") and a.estancias < 2:
            avisos.append(f"{rel}: Print Store tiene {a.estancias} estancias con foto (deberían ser 2)")

    # Sitemap y robots
    sm = DOCS / "sitemap.xml"
    if not sm.exists(): errores.append("Falta sitemap.xml")
    else:
        contenido = sm.read_text()
        for p in paginas:
            ruta = p.relative_to(DOCS).as_posix()[:-len("index.html")]
            if f"<loc>{dominio}/{ruta}</loc>" not in contenido:
                errores.append(f"sitemap.xml no incluye {dominio}/{ruta}")
    if not (DOCS / "robots.txt").exists(): errores.append("Falta robots.txt")

    # Peso de las fotos
    for f in (DOCS / "img").rglob("*") if (DOCS / "img").exists() else []:
        if f.is_file() and f.stat().st_size > PESO_MAX_FOTO:
            avisos.append(f"Foto pesada ({f.stat().st_size/1e3:.0f} KB): {f.relative_to(DOCS)}")

    # Resultado
    print(f"\nRevisión: {len(paginas)} páginas · {len(errores)} errores · {len(avisos)} avisos")
    for e in errores: print("  ✗", e)
    for w in avisos: print("  ⚠", w)
    if not errores: print("  ✓ Todo correcto para publicar")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
