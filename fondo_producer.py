"""
Fondo Producer (27 jul 2026) — fondos ANIMADOS para imagen suelta e historia,
en vez del color/gradiente sólido de siempre. Dos orígenes:

- **Pexels** (banco de stock gratis, libre de derechos): reusa `broll_pexels`
  ya validado en el pipeline de video, recortado a un clip corto en loop.
- **IA** (Gemini "nano-banana", `llm_client.generar_imagen`): genera una
  imagen fija desde un prompt y le aplica un efecto Ken Burns (zoom lento)
  con FFmpeg — Gemini no genera video, así que el "animado" acá es ese
  movimiento de cámara sobre la imagen generada, no una IA de video real
  (esas son caras/lentas; esto es $0 de FFmpeg + el costo fijo de 1 imagen).

El diseño de texto (título/logo/skin) se renderiza aparte como PNG
transparente (`image_producer.producir_overlay_slide`/`producir_overlay_
historia`) y se compone encima con FFmpeg — mismo patrón que las láminas de
carrusel en video (`video_producer.producir_slide_video`).

Requiere PEXELS_API_KEY (fuente Pexels) o GEMINI_API_KEY (fuente IA).
"""

import subprocess
import tempfile
from pathlib import Path

import image_producer
import llm_client
import ranker_ia  # carga .env
from test_video_pipeline import broll_pexels

BASE = Path(__file__).resolve().parent
OUT = BASE / "producciones"

DURACION_FONDO_SEG = 6.0
FPS_FONDO = 25

# Gemini solo acepta un set fijo de proporciones — la más cercana a cada
# formato de la app (todas calzan exacto salvo que se agregue un formato
# nuevo más adelante).
_ASPECT_GEMINI = {(1080, 1080): "1:1", (1080, 1350): "4:5", (1080, 1920): "9:16"}


def _aspect_ratio_gemini(w: int, h: int) -> str:
    return _ASPECT_GEMINI.get((w, h), "9:16")


def fondo_pexels(query: str, destino: Path, w: int, h: int,
                 duracion: float = DURACION_FONDO_SEG) -> Path:
    """Clip corto de Pexels (libre de derechos), recortado/escalado a (w,h)
    y sin audio — listo para loopear como fondo animado."""
    orientation = "square" if w == h else "portrait"
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        crudo = Path(tmp.name)
    broll_pexels(query, crudo, orientation=orientation)
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(crudo), "-t", f"{duracion:.2f}",
         "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1",
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "22", str(destino)],
        check=True, capture_output=True,
    )
    crudo.unlink(missing_ok=True)
    return destino


def fondo_ia(prompt: str, destino: Path, w: int, h: int,
             duracion: float = DURACION_FONDO_SEG) -> Path:
    """Imagen generada por Gemini + efecto Ken Burns (zoom lento) con FFmpeg
    para que se sienta "animada" — sin audio, misma duración que fondo_
    pexels() para que ambas fuentes sean intercambiables en el resto del
    pipeline."""
    imagen_bytes = llm_client.generar_imagen(
        f"{prompt}. Fondo abstracto/cinematográfico, sin texto, sin logos, sin personas reconocibles.",
        tarea="fondo_animado", aspect_ratio=_aspect_ratio_gemini(w, h),
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        base_png = Path(tmp.name)
    base_png.write_bytes(imagen_bytes)

    frames = int(duracion * FPS_FONDO)
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(base_png), "-t", f"{duracion:.2f}",
         "-vf", (f"scale={w*2}:{h*2},"
                 f"zoompan=z='min(zoom+0.0012,1.2)':d={frames}:s={w}x{h}:fps={FPS_FONDO},"
                 "format=yuv420p"),
         "-c:v", "libx264", "-preset", "fast", "-crf", "22", str(destino)],
        check=True, capture_output=True,
    )
    base_png.unlink(missing_ok=True)
    return destino


def componer_fondo_con_overlay(fondo: Path, overlay_png_bytes: bytes, destino: Path,
                               w: int, h: int) -> Path:
    """Compone el PNG transparente del diseño (título/logo/skin) encima del
    fondo animado ya recortado a (w,h) — sin audio, mismo criterio que las
    láminas-video de carrusel."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        overlay_png = Path(tmp.name)
    overlay_png.write_bytes(overlay_png_bytes)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(fondo), "-i", str(overlay_png),
         "-filter_complex", f"[0:v][1:v]overlay=0:0[ov]",
         "-map", "[ov]", "-an",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22", str(destino)],
        check=True, capture_output=True,
    )
    overlay_png.unlink(missing_ok=True)
    return destino


def producir_imagen_animada(contenido: dict, slug: str, formato_imagen: str = "vertical",
                            estilo_visual: str = "editorial", fuente_fondo: str = "pexels",
                            fondo_query: str = "") -> Path:
    """Imagen suelta (formato != carrusel) como MP4 con fondo animado en vez
    de PNG estático — mismo diseño de texto, `fuente_fondo` ("pexels"|"ia")
    elige el origen del fondo. `fondo_query` es la búsqueda/prompt; si no se
    pasa, usa el título de la pieza."""
    brand = image_producer.obtener_brand(contenido["perfil"])
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    w, h = image_producer.DIMENSIONES.get(formato_imagen, image_producer.DIMENSIONES["vertical"])
    query = fondo_query or contenido["titulo"]

    fondo_path = carpeta / "fondo_imagen.mp4"
    if fuente_fondo == "ia":
        fondo_ia(query, fondo_path, w, h)
    else:
        fondo_pexels(query, fondo_path, w, h)

    overlay_png = image_producer.producir_overlay_slide(
        brand, {"rol": "hook", "titular": contenido["titulo"], "cuerpo": contenido.get("cuerpo", "")},
        estilo_visual, w, h,
    )
    destino = componer_fondo_con_overlay(fondo_path, overlay_png, carpeta / "imagen_animada.mp4", w, h)
    fondo_path.unlink(missing_ok=True)
    return destino


def producir_historia_animada(contenido: dict, slug: str, estilo_visual: str = "editorial",
                              fuente_fondo: str = "pexels", fondo_query: str = "") -> Path:
    """Historia (9:16) como MP4 con fondo animado — misma idea que
    producir_imagen_animada() pero con la plantilla de historia-teaser."""
    brand = image_producer.obtener_brand(contenido["perfil"])
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    w, h = image_producer.DIMENSIONES["historia"]
    query = fondo_query or contenido["titulo"]

    fondo_path = carpeta / "fondo_historia.mp4"
    if fuente_fondo == "ia":
        fondo_ia(query, fondo_path, w, h)
    else:
        fondo_pexels(query, fondo_path, w, h)

    overlay_png = image_producer.producir_overlay_historia(brand, contenido, estilo_visual)
    destino = componer_fondo_con_overlay(fondo_path, overlay_png, carpeta / "historia_animada.mp4", w, h)
    fondo_path.unlink(missing_ok=True)
    return destino
