"""Sprint 0 — prueba real del pipeline de video: ElevenLabs + Pexels + FFmpeg.

Guión corto → voz (ElevenLabs) → B-roll vertical (Pexels) → video 9:16 con FFmpeg.

Requiere variables de entorno:
    ELEVENLABS_API_KEY   https://elevenlabs.io  (free tier ~10 min/mes)
    PEXELS_API_KEY       https://www.pexels.com/api/  (gratis)

Uso: .venv/bin/python test_video_pipeline.py
"""

import base64
import os
import subprocess
import sys
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
OUT = BASE / "test_video"

_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GUION = (
    "La inteligencia artificial ya escribe el cuarenta por ciento del contenido "
    "de marcas en Latinoamérica. Las agencias que automatizan su pipeline "
    "publican cinco veces más sin subir costos. Sígueme para más contenido."
)
PEXELS_QUERY = "technology office vertical"
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # "Sarah", multilingüe


def voz_elevenlabs(texto: str, destino: Path, voice_id: str = VOICE_ID) -> Path:
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def voz_elevenlabs_con_timestamps(texto: str, destino: Path, voice_id: str = VOICE_ID) -> tuple:
    """Como voz_elevenlabs() pero además devuelve el alignment carácter por
    carácter (timing REAL de la voz generada, no una estimación) — usado para
    armar subtítulos que sigan exactamente lo que se está diciendo en cada
    instante, en vez de repartir el texto proporcional a la duración estimada
    del tramo. Devuelve (ruta_audio, alignment) donde alignment es
    {"characters": [...], "character_start_times_seconds": [...],
    "character_end_times_seconds": [...]} — prefiere normalized_alignment
    (timing del texto ya normalizado por ElevenLabs, ej. números en letras)
    si viene, si no cae al alignment del texto original."""
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    destino.write_bytes(base64.b64decode(data["audio_base64"]))
    alignment = data.get("normalized_alignment") or data["alignment"]
    return destino, alignment


def broll_pexels(query: str, destino: Path, orientation: str = "portrait", indice: int = 0) -> Path:
    """`indice` elige cuál de los resultados de Pexels bajar (0 = el más
    relevante) — para poder pedir varias tomas DISTINTAS de la misma query
    (misma búsqueda, clips distintos) en vez de repetir siempre el primero."""
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": os.environ["PEXELS_API_KEY"]},
        params={"query": query, "orientation": orientation, "per_page": 5},
        timeout=60,
    )
    r.raise_for_status()
    videos = r.json()["videos"]
    if not videos:
        raise RuntimeError(f"Pexels no devolvió videos para: {query}")
    files = videos[min(indice, len(videos) - 1)]["video_files"]
    hd = min(
        (f for f in files if f["width"] and f["width"] >= 720),
        key=lambda f: f["width"],
        default=files[0],
    )
    with requests.get(hd["link"], stream=True, timeout=300) as v:
        v.raise_for_status()
        with open(destino, "wb") as fh:
            for chunk in v.iter_content(1 << 20):
                fh.write(chunk)
    return destino


def ensamblar(voz: Path, broll: Path, salida: Path) -> Path:
    dur = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(voz)]
        ).strip()
    )
    subprocess.run(
        ["ffmpeg", "-y",
         "-stream_loop", "-1", "-i", str(broll),
         "-i", str(voz),
         "-t", f"{dur:.2f}",
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,setsar=1",
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-c:a", "aac", "-shortest",
         str(salida)],
        check=True, capture_output=True,
    )
    return salida


def ensamblar_cuadrado(voz: Path, broll: Path, salida: Path) -> Path:
    """Igual que ensamblar() pero recorta a 1:1 (1080x1080) — para láminas de
    carrusel producidas como video corto en vez de imagen estática."""
    dur = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(voz)]
        ).strip()
    )
    subprocess.run(
        ["ffmpeg", "-y",
         "-stream_loop", "-1", "-i", str(broll),
         "-i", str(voz),
         "-t", f"{dur:.2f}",
         "-vf", "scale=1080:1080:force_original_aspect_ratio=increase,"
                "crop=1080:1080,setsar=1",
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-c:a", "aac", "-shortest",
         str(salida)],
        check=True, capture_output=True,
    )
    return salida


def ensamblar_con_overlays(voz: Path, broll: Path, salida: Path, w: int, h: int,
                           overlays: list | None = None) -> Path:
    """Como ensamblar()/ensamblar_cuadrado() pero compone PNGs transparentes
    encima del B-roll. `overlays`: lista de (ruta_png, inicio_seg, fin_seg) —
    cada PNG debe ser del mismo tamaño (w, h). `fin_seg=None` = se muestra
    toda la duración (para el overlay de una lámina de carrusel completa)."""
    dur = float(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(voz)]
        ).strip()
    )
    inputs = ["-stream_loop", "-1", "-i", str(broll), "-i", str(voz)]
    filtro = [f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[base]"]
    ultimo = "base"
    for i, (png, ini, fin) in enumerate(overlays or []):
        inputs += ["-i", str(png)]
        idx = 2 + i
        enable = f":enable='between(t,{ini},{fin})'" if fin is not None else ""
        filtro.append(f"[{ultimo}][{idx}:v]overlay=0:0{enable}[ov{i}]")
        ultimo = f"ov{i}"
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-t", f"{dur:.2f}",
         "-filter_complex", ";".join(filtro),
         "-map", f"[{ultimo}]", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-c:a", "aac", "-shortest",
         str(salida)],
        check=True, capture_output=True,
    )
    return salida


def ensamblar_multi_broll(voz: Path, brolls: list, salida: Path, w: int, h: int,
                          overlays: list | None = None) -> Path:
    """Como ensamblar_con_overlays() pero con un B-ROLL DISTINTO por tramo del
    guion en vez de uno solo repetido — cambia de toma según lo que se está
    diciendo. `brolls`: lista de (ruta_video, duracion_seg) EN ORDEN — cada
    clip se recorta a su duración, se escala/recorta a (w,h) y se encadena
    (concat) antes de superponer `overlays` igual que siempre."""
    n = len(brolls)
    inputs = []
    for ruta, _ in brolls:
        inputs += ["-stream_loop", "-1", "-i", str(ruta)]
    idx_voz = n
    inputs += ["-i", str(voz)]

    filtro = []
    for i, (_, dur) in enumerate(brolls):
        filtro.append(
            f"[{i}:v]trim=duration={dur:.2f},"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"setsar=1,setpts=PTS-STARTPTS[seg{i}]"
        )
    concat_in = "".join(f"[seg{i}]" for i in range(n))
    filtro.append(f"{concat_in}concat=n={n}:v=1:a=0[base]")

    ultimo = "base"
    for i, (png, ini, fin) in enumerate(overlays or []):
        idx = idx_voz + 1 + i
        inputs += ["-i", str(png)]
        enable = f":enable='between(t,{ini},{fin})'" if fin is not None else ""
        filtro.append(f"[{ultimo}][{idx}:v]overlay=0:0{enable}[ov{i}]")
        ultimo = f"ov{i}"

    dur_total = sum(d for _, d in brolls)
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-t", f"{dur_total:.2f}",
         "-filter_complex", ";".join(filtro),
         "-map", f"[{ultimo}]", "-map", f"{idx_voz}:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-c:a", "aac", "-shortest",
         str(salida)],
        check=True, capture_output=True,
    )
    return salida


def main() -> int:
    faltan = [k for k in ("ELEVENLABS_API_KEY", "PEXELS_API_KEY") if not os.environ.get(k)]
    if faltan:
        print(f"Faltan API keys: {', '.join(faltan)}")
        print("Exporta las variables y vuelve a correr:")
        for k in faltan:
            print(f"  export {k}=...")
        return 1

    OUT.mkdir(exist_ok=True)
    print("1/3  Generando voz con ElevenLabs...")
    voz = voz_elevenlabs(GUION, OUT / "voz.mp3")
    print("2/3  Descargando B-roll de Pexels...")
    broll = broll_pexels(PEXELS_QUERY, OUT / "broll.mp4")
    print("3/3  Ensamblando con FFmpeg...")
    video = ensamblar(voz, broll, OUT / "test_video_9x16.mp4")
    print(f"\n✅ Video listo: {video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
