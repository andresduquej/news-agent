"""
Image Generator — produce una imagen base (.png) por cada brief con formato
"imagen", usando Pillow (oficial, sin API, sin key, costo $0).

Genera una imagen tipo post con texto principal, texto de apoyo y pie
(según lo que ya arma generator.py en `sugerencia_imagen`).

NO es diseño pulido: es una BASE lista para usar directo o para retocar
en Canva/Photoshop si quieres darle más estilo.

Uso:
  python3 image_generator.py briefs.json --dir imagenes
"""

import json
import os
import re
import sys

from text_image import crear_imagen, dibujar_bloque

ANCHO, ALTO = 1080, 1350  # formato post (4:5), buen estándar para feed.
COLOR_FONDO = (26, 26, 46)  # azul oscuro neutro, fácil de leer.
COLOR_TITULO = (255, 255, 255)
COLOR_APOYO = (204, 204, 204)
COLOR_PIE = (136, 136, 136)

OUT_DIR = "imagenes"


def _slugify(texto: str, max_len: int = 40) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    t = texto.lower().translate(tabla)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:max_len].strip("-") or "imagen"


def generar_imagen(brief: dict, carpeta_salida: str, indice: int) -> str:
    img_data = brief.get("sugerencia_imagen") or {}
    titulo = img_data.get("texto_principal", brief.get("titulo_fuente", ""))
    apoyo = img_data.get("texto_apoyo", "")
    pie = img_data.get("pie", "")

    nombre = f"{indice:02d}-{_slugify(brief.get('titulo_fuente', ''))}.png"
    ruta = os.path.join(carpeta_salida, nombre)
    os.makedirs(carpeta_salida, exist_ok=True)

    img, draw = crear_imagen(ANCHO, ALTO, COLOR_FONDO)
    dibujar_bloque(draw, titulo, int(ALTO * 0.32), ANCHO, 60, COLOR_TITULO)
    if apoyo:
        dibujar_bloque(draw, apoyo, int(ALTO * 0.62), ANCHO, 38, COLOR_APOYO)
    if pie:
        dibujar_bloque(draw, pie, int(ALTO * 0.90), ANCHO, 26, COLOR_PIE)

    img.save(ruta)
    return ruta


def generar_para_briefs(briefs: list, base_dir: str = OUT_DIR) -> list:
    """Genera imagen solo para los briefs con formato == 'imagen'."""
    rutas = []
    de_imagen = [b for b in briefs if b.get("formato") == "imagen"]
    for i, brief in enumerate(de_imagen, 1):
        print(f"  · Generando imagen {i}/{len(de_imagen)}: "
              f"{brief.get('titulo_fuente', '')[:50]}...", file=sys.stderr)
        ruta = generar_imagen(brief, base_dir, i)
        rutas.append(ruta)
    return rutas


def _load_briefs(ruta) -> list:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 image_generator.py briefs.json [--dir imagenes]", file=sys.stderr)
        sys.exit(1)
    base_dir = OUT_DIR
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir")
        base_dir = sys.argv[i + 1]

    briefs = _load_briefs(sys.argv[1])
    rutas = generar_para_briefs(briefs, base_dir)
    print(f"\n✅ Generadas {len(rutas)} imágenes en: {base_dir}/", file=sys.stderr)
    for r in rutas:
        print(f"   - {r}", file=sys.stderr)


if __name__ == "__main__":
    main()
