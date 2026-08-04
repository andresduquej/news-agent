"""
Video Generator — produce un video base (.mp4) por cada brief con formato
"video", usando SOLO herramientas locales y gratis:

  - `say` (macOS)   -> narra el guion con voz en español, sin API/key.
  - `ffmpeg` (local)-> arma slides de texto + audio en un .mp4.

NO es edición final pulida: es un VIDEO BASE listo para overlay o para
usarlo directo si el estilo simple funciona. Todo local, costo $0.

Uso:
  python3 video_generator.py briefs/2026-07-21/index.json
  (o, más fácil, desde run.py que ya lo hace automático)
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from text_image import crear_imagen, dibujar_bloque

VOZ = "Paulina"  # voz en español (México) incluida en macOS, sin costo.
ANCHO, ALTO = 1080, 1920  # formato vertical (Reels/TikTok/Shorts).
FPS = 30
COLOR_FONDO = (0, 0, 0)
COLOR_TEXTO = (255, 255, 255)
FUENTE_TAMANO = 60

OUT_DIR = "videos"


def _guion_desde_brief(brief: dict) -> list:
    """Arma la lista de frases del guion: gancho -> puntos clave -> cierre/CTA."""
    frases = [brief.get("gancho", "")]
    frases += brief.get("puntos_clave", [])
    cierre = brief.get("cta") or "Gracias por ver hasta el final."
    frases.append(cierre)
    return [f for f in frases if f.strip()]


def _slugify(texto: str, max_len: int = 40) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    t = texto.lower().translate(tabla)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:max_len].strip("-") or "video"


def _narrar(texto: str, ruta_audio_aiff: str) -> None:
    subprocess.run(["say", "-v", VOZ, "-o", ruta_audio_aiff, texto], check=True)


def _duracion_audio(ruta_audio: str) -> float:
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", ruta_audio],
        capture_output=True, text=True, check=True,
    )
    return float(salida.stdout.strip())


def _slide_a_imagen(texto: str, ruta_png: str) -> None:
    """Dibuja el texto centrado en un PNG del tamaño del video (con Pillow)."""
    img, draw = crear_imagen(ANCHO, ALTO, COLOR_FONDO)
    dibujar_bloque(draw, texto, ALTO // 2, ANCHO, FUENTE_TAMANO, COLOR_TEXTO)
    img.save(ruta_png)


def _slide_a_video(ruta_png: str, duracion: float, ruta_salida: str) -> None:
    """Convierte la imagen fija en un clip mudo del largo de `duracion`."""
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", ruta_png, "-t", str(duracion),
         "-r", str(FPS), "-pix_fmt", "yuv420p", ruta_salida],
        check=True, capture_output=True,
    )


def _combinar_clip_con_audio(clip_video: str, clip_audio: str, salida: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", clip_video, "-i", clip_audio,
         "-c:v", "copy", "-c:a", "aac", "-shortest", salida],
        check=True, capture_output=True,
    )


def _concatenar(clips: list, salida: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lista:
        for c in clips:
            lista.write(f"file '{os.path.abspath(c)}'\n")
        ruta_lista = lista.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", ruta_lista,
             "-c", "copy", salida],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(ruta_lista)


def generar_video(brief: dict, carpeta_salida: str, indice: int) -> str:
    """Genera el .mp4 de un brief. Devuelve la ruta del archivo final."""
    frases = _guion_desde_brief(brief)
    nombre = f"{indice:02d}-{_slugify(brief.get('titulo_fuente', ''))}"
    ruta_final = os.path.join(carpeta_salida, f"{nombre}.mp4")

    with tempfile.TemporaryDirectory() as tmp:
        clips_finales = []
        for i, frase in enumerate(frases):
            audio = os.path.join(tmp, f"a{i}.aiff")
            png = os.path.join(tmp, f"s{i}.png")
            slide = os.path.join(tmp, f"s{i}.mp4")
            unido = os.path.join(tmp, f"u{i}.mp4")

            _narrar(frase, audio)
            duracion = max(_duracion_audio(audio), 1.0) + 0.5  # margen de aire
            _slide_a_imagen(frase, png)
            _slide_a_video(png, duracion, slide)
            _combinar_clip_con_audio(slide, audio, unido)
            clips_finales.append(unido)

        os.makedirs(carpeta_salida, exist_ok=True)
        _concatenar(clips_finales, ruta_final)

    return ruta_final


def generar_para_briefs(briefs: list, base_dir: str = OUT_DIR) -> list:
    """Genera video solo para los briefs con formato == 'video'."""
    rutas = []
    de_video = [b for b in briefs if b.get("formato") == "video"]
    for i, brief in enumerate(de_video, 1):
        print(f"  · Generando video {i}/{len(de_video)}: "
              f"{brief.get('titulo_fuente', '')[:50]}...", file=sys.stderr)
        ruta = generar_video(brief, base_dir, i)
        rutas.append(ruta)
    return rutas


def _load_briefs(ruta) -> list:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 video_generator.py briefs.json [--dir videos]", file=sys.stderr)
        sys.exit(1)
    base_dir = OUT_DIR
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir")
        base_dir = sys.argv[i + 1]

    briefs = _load_briefs(sys.argv[1])
    rutas = generar_para_briefs(briefs, base_dir)
    print(f"\n✅ Generados {len(rutas)} videos en: {base_dir}/", file=sys.stderr)
    for r in rutas:
        print(f"   - {r}", file=sys.stderr)


if __name__ == "__main__":
    main()
