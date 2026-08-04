"""
text_image.py — utilidad compartida para dibujar texto sobre un fondo de
color y guardarlo como imagen (.png), usando Pillow (oficial, $0).

La usan image_generator.py, carousel_generator.py y video_generator.py
(para las slides de los videos), evitando depender del filtro `drawtext`
de ffmpeg, que la versión de Homebrew no trae por defecto.
"""

from PIL import Image, ImageDraw, ImageFont

FUENTE_PATH = "/System/Library/Fonts/Helvetica.ttc"  # incluida en macOS.


def _cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FUENTE_PATH, tamano)
    except OSError:
        return ImageFont.load_default()


def _envolver_texto(draw: ImageDraw.ImageDraw, texto: str, fuente, max_ancho: int) -> list:
    """Parte el texto en líneas que quepan dentro de max_ancho píxeles."""
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        ancho = draw.textbbox((0, 0), prueba, font=fuente)[2]
        if ancho <= max_ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def dibujar_bloque(
    draw: ImageDraw.ImageDraw,
    texto: str,
    y_centro: int,
    ancho_imagen: int,
    tamano_fuente: int,
    color: str,
    margen: int = 80,
) -> None:
    """Dibuja `texto` centrado horizontalmente, envuelto en varias líneas,
    con el bloque completo centrado verticalmente en y_centro."""
    if not texto:
        return
    fuente = _cargar_fuente(tamano_fuente)
    lineas = _envolver_texto(draw, texto, fuente, ancho_imagen - 2 * margen)
    alto_linea = int(tamano_fuente * 1.3)
    alto_total = alto_linea * len(lineas)
    y = y_centro - alto_total // 2
    for linea in lineas:
        ancho_linea = draw.textbbox((0, 0), linea, font=fuente)[2]
        x = (ancho_imagen - ancho_linea) // 2
        draw.text((x, y), linea, font=fuente, fill=color)
        y += alto_linea


def crear_imagen(ancho: int, alto: int, color_fondo: str) -> tuple:
    img = Image.new("RGB", (ancho, alto), color_fondo)
    return img, ImageDraw.Draw(img)
