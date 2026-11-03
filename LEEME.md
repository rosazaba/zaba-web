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

Las carpetas siguen el orden del menú de la web: Servicios · Tarifa · Sobre mí · Contacto · Print Store · Encuentra tus fotos. La portada de la web es la página «Servicios» (tus galerías).

> **Renombrar:** `1-trabajos` → `1-servicios` y `2-servicios` → `2-tarifa`. La web funciona con los dos nombres, así que puedes cambiarlos cuando quieras.

```
originales/
├── 1-servicios/         → PORTADA = página «Servicios» (antes 1-trabajos)
│   ├── portada/         → foto para la vista previa al compartir la web
│   ├── buceo/  surf/  dron/   → una galería cada una
│   │   └── portada/     →   foto del recuadro de esa galería
│   └── seleccion/       → opcional: fotos para la tira «Selección»
├── 2-tarifa/            → página «Tarifa» (antes 2-servicios)
│   ├── portada/         → la foto apaisada de arriba
│   └── surf/  buceo/  copias/   → 1 foto para cada servicio
├── 3-sobre-mi/
│   ├── portada/         → foto de «¡Hola! Soy Rosa»
│   └── retrato-…        → (opcional) otra foto tuya para ese bloque
├── 4-contacto/
│   └── portada/         → la foto del fondo-mural (sale en transparencia)
├── 5-print-store/       → fotos que vendes impresas (las 2 primeras salen en el salón y el dormitorio)
│   └── portada/         → (opcional) foto de la cabecera
├── 6-encuentra-tus-fotos/
│   ├── portada/         → (opcional) foto de la cabecera
│   ├── playa-de-patos-vigo/
│   │   └── 2026-11-01/  → una carpeta por sesión, con la fecha AAAA-MM-DD
│   └── playa-de-berria-santona/
└── logo/                → el logo (ya está preparado)
```

- **Encuentra tus fotos:** pon las fotos de cada sesión en `<playa>/<fecha>/`. La web las publica pequeñas, con marca de agua y un código (p. ej. `PATOS-20261101-007`). Quien compra te escribe por WhatsApp con ese código; tú cobras y le envías el original. Para añadir otra playa, pídeselo a Claude (o copia un bloque en `textos/encuentra.yml`).
- **Portadas:** cada sección y cada galería tiene su carpeta `portada` con UNA foto. Para cambiar una portada, sustituye esa foto.
- **Fotos de bancos de imágenes** (Unsplash, Pexels…): no las pongas dentro de las galerías. Si hay alguna, la web la ignora y avisa, para que nunca salga como trabajo tuyo.

- **Orden:** las fotos se ordenan por nombre. Llámalas `01-...`, `02-...` para elegir el orden.
- **Tira «Selección»:** si `seleccion/` está vacía, se hace sola con fotos de buceo, surf y dron ordenadas por color. Si pones fotos ahí, salen solo esas.
- **Formato:** JPG, PNG o TIFF, al tamaño original. No hace falta reducirlas; Claude las optimiza.
- **Galería nueva:** crea otra carpeta dentro de `originales/1-trabajos/` (por ejemplo `apnea/`), mete las fotos y pídele a Claude que la añada.

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
