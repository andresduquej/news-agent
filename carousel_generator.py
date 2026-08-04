"""
Carousel Generator — produce las imágenes (.png) de cada slide para los
briefs con formato "carrusel", usando Pillow (oficial, sin API, costo $0).

Cada brief con formato carrusel genera una carpeta con una imagen por
slide (portada, contenido, cierre), lista para subir en orden.

Uso:
  python3 carousel_generator.py briefs.json --dir carruseles
"""

import json
import os
import re
import sys

from text_image import crear_imagen, dibujar_bloque

ANCHO, ALTO = 1080, 1350
COLOR_FONDO_PORTADA = (74, 26, 94)
COLOR_FONDO_SLIDE = (26, 26, 46)
COLOR_TEXTO = (255, 255, 255)

OUT_DIR = "carruseles"


def _slugify(texto: str, max_len: int = 40) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    t = texto.lower().translate(tabla)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:max_len].strip("-") or "carrusel"


def generar_carrusel(brief: dict, carpeta_salida: str, indice: int) -> str:
    slides = brief.get("sugerencia_slides") or [brief.get("gancho", "")]
    nombre_base = f"{indice:02d}-{_slugify(brief.get('titulo_fuente', ''))}"
    carpeta = os.path.join(carpeta_salida, nombre_base)
    os.makedirs(carpeta, exist_ok=True)

    for i, texto in enumerate(slides, 1):
        es_portada = i == 1
        color_fondo = COLOR_FONDO_PORTADA if es_portada else COLOR_FONDO_SLIDE
        tamano = 56 if es_portada else 44
        img, draw = crear_imagen(ANCHO, ALTO, color_fondo)
        dibujar_bloque(draw, texto, ALTO // 2, ANCHO, tamano, COLOR_TEXTO)
        img.save(os.path.join(carpeta, f"slide-{i:02d}.png"))

    return carpeta


def generar_para_briefs(briefs: list, base_dir: str = OUT_DIR) -> list:
    """Genera carrusel solo para los briefs con formato == 'carrusel'."""
    rutas = []
    de_carrusel = [b for b in briefs if b.get("formato") == "carrusel"]
    for i, brief in enumerate(de_carrusel, 1):
        print(f"  · Generando carrusel {i}/{len(de_carrusel)}: "
              f"{brief.get('titulo_fuente', '')[:50]}...", file=sys.stderr)
        ruta = generar_carrusel(brief, base_dir, i)
        rutas.append(ruta)
    return rutas


def _load_briefs(ruta) -> list:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 carousel_generator.py briefs.json [--dir carruseles]", file=sys.stderr)
        sys.exit(1)
    base_dir = OUT_DIR
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir")
        base_dir = sys.argv[i + 1]

    briefs = _load_briefs(sys.argv[1])
    rutas = generar_para_briefs(briefs, base_dir)
    print(f"\n✅ Generados {len(rutas)} carruseles en: {base_dir}/", file=sys.stderr)
    for r in rutas:
        print(f"   - {r}", file=sys.stderr)


if __name__ == "__main__":
    main()
