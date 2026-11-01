# Web de Zaba — cómo funciona

## Carpetas

| Carpeta | Qué es | ¿La tocas tú? |
|---|---|---|
| `originales/` | Tus fotos originales, a máxima calidad. **No se suben a internet.** | Sí: aquí dejas las fotos |
| `textos/` | Todos los textos de la web en inglés, español y francés | Sí, si quieres corregir algo (o pídeselo a Claude) |
| `motor/` | El generador, las plantillas, el diseño y la revisión automática | No hace falta |
| `docs/` | La web final ya generada (es lo que publica GitHub) | No: se genera sola |
| `vista-previa/` | Copia de la web para verla en tu ordenador: abre `vista-previa\index.html` con doble clic | Solo para mirar |

## Dónde va cada foto

```
originales/
├── inicio/
│   ├── portada/        → 1 foto grande para la portada (mejor horizontal)
│   └── destacadas/     → 6–9 fotos para la selección de la página de inicio
├── work/
│   ├── surf/           → galería de Surf
│   └── buceo/          → galería de Buceo
├── about/              → 1 foto tuya (mejor vertical)
├── logo/               → tu logo original (SVG ideal; PNG o JPG también valen)
└── services/
    ├── surf/           → 1 foto para "Sesión de surf"
    ├── buceo/          → 1 foto para "Sesión submarina"
    └── copias/         → 1 foto para "Copias artísticas"
```

- **Orden:** las fotos se ordenan por nombre. Llámalas `01-...`, `02-...` para elegir el orden.
- **Formato:** JPG, PNG o TIFF, al tamaño original. No hace falta reducirlas; Claude las optimiza solo.
- **Galería nueva:** crea una carpeta dentro de `originales/work/` (por ejemplo `originales/work/apnea/`), mete las fotos y pídele a Claude que la añada.

## Cómo actualizar la web

1. Deja las fotos en su carpeta o cambia un texto en `textos/`.
2. Dile a Claude, por ejemplo: *"He añadido fotos a surf, publica"* o *"cambia el precio de la sesión de surf a 140 €"*.
3. Claude optimiza las fotos, genera la web, pasa la revisión automática y la publica.

## Qué comprueba la revisión automática

Se ejecuta cada vez que se genera la web. Si encuentra **errores**, no se publica:

- **Enlaces e imágenes:** que no haya ninguno roto, incluidos los enlaces a secciones (#).
- **Por página:** un solo título H1, título único, meta descripción con la longitud adecuada y URL canónica.
- **Idiomas:** versiones EN/ES/FR enlazadas entre sí (hreflang) y ninguna traducción vacía.
- **Fotos:** texto alternativo en todas, dimensiones declaradas y peso razonable.
- **Archivos para buscadores:** sitemap completo, robots.txt, datos estructurados (schema.org) y vista previa al compartir.
- **Pendientes:** avisa de datos sin rellenar, como el email o el Instagram.

## Para generar la web a mano (opcional)

```
pip install -r motor/requisitos.txt
python motor/build.py
```
