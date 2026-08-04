"""
Generador de ideas por referentes — Modo 3 del Agente de Contenido.

El usuario pega links de videos de referentes/competidores (o sube el
archivo si el link no se puede descargar). Si el video tiene narración
hablada, se descarga (yt-dlp) y se transcribe local y gratis (whisper.cpp).
Si NO tiene audio (ej. un scroll silencioso de un carrusel de Instagram
grabado en pantalla), se extraen frames en su lugar y una IA con visión
(Gemini/Claude) analiza la estructura visual directamente — mismo resultado
final, distinta fuente de análisis. Cada video se trata de forma
independiente, así que se puede mezclar en una sola tanda videos con voz y
carruseles silenciosos.

Converge en el mismo flujo que los Modos 1 y 2: cada ángulo se trata como
una "noticia" sintética y entra a generator_ia.generar_contenido.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

import llm_client
import ranker_ia  # carga .env

BASE = Path(__file__).resolve().parent
MODELO_WHISPER = BASE / "models" / "ggml-medium.bin"

MAX_TRANSCRIPCION_CHARS = 6000  # recorte por referente para no volar el prompt
FRAMES_ANALISIS_VISUAL = 6  # frames repartidos parejo a lo largo del video sin audio


class ReferentesError(Exception):
    pass


def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _descargar_video(url: str, destino: Path) -> Path:
    """Descarga el mejor video+audio disponible de `url` con yt-dlp (no solo
    audio — hace falta el video completo por si hay que sacar frames)."""
    salida = destino.with_suffix("")
    r = _run([
        "yt-dlp", "-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4",
        "-o", f"{salida}.%(ext)s", "--", url,
    ], timeout=300)
    candidatos = list(destino.parent.glob(f"{destino.stem}.*"))
    if r.returncode != 0 or not candidatos:
        raise ReferentesError(
            f"No se pudo descargar el video ({url}). Puede ser privado o no "
            f"disponible — subí el archivo manualmente. Detalle: {r.stderr.strip()[-300:]}"
        )
    return candidatos[0]


def _tiene_audio(archivo: Path) -> bool:
    r = _run([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", str(archivo),
    ], timeout=30)
    return bool(r.stdout.strip())


def _duracion(archivo: Path) -> float:
    r = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(archivo),
    ], timeout=30)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _extraer_audio_de_archivo(origen: Path, destino: Path) -> Path:
    """Convierte un archivo de video/audio a wav 16kHz mono (formato que espera whisper)."""
    r = _run([
        "ffmpeg", "-y", "-i", str(origen), "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le", str(destino),
    ], timeout=180)
    if r.returncode != 0 or not destino.exists():
        raise ReferentesError(f"No se pudo procesar el audio: {r.stderr.strip()[-300:]}")
    return destino


def _transcribir(audio_wav: Path) -> str:
    if not MODELO_WHISPER.exists():
        raise ReferentesError(
            "Falta el modelo de transcripción (whisper) — no se encontró "
            f"{MODELO_WHISPER}."
        )
    salida = audio_wav.with_suffix("")
    r = _run([
        "whisper-cli", "-m", str(MODELO_WHISPER), "-f", str(audio_wav),
        "-l", "es", "-otxt", "-of", str(salida), "-nt",
    ], timeout=600)
    txt = salida.with_suffix(".txt")
    if r.returncode != 0 or not txt.exists():
        raise ReferentesError(f"No se pudo transcribir el audio: {r.stderr.strip()[-300:]}")
    return txt.read_text().strip()


def _extraer_frames(archivo: Path, tmpdir: Path, idx: int, n: int = FRAMES_ANALISIS_VISUAL) -> list:
    """Saca `n` frames repartidos parejo a lo largo del video (sin contar los
    bordes) — para analizar visualmente un video sin audio."""
    dur = _duracion(archivo) or float(n)
    paso = dur / (n + 1)
    rutas = []
    for i in range(1, n + 1):
        t = i * paso
        salida = tmpdir / f"frame{idx}_{i}.jpg"
        _run([
            "ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(archivo),
            "-frames:v", "1", "-q:v", "3", str(salida),
        ], timeout=60)
        if salida.exists():
            rutas.append(salida)
    if not rutas:
        raise ReferentesError("No se pudieron extraer frames del video para el análisis visual.")
    return rutas


def _preparar_fuente(fuente: dict, tmpdir: Path, idx: int) -> dict:
    """fuente: {"tipo": "url"|"archivo", "valor": str (url) | Path (archivo subido),
    "caption": str (opcional) — el copy/caption del post, si se consiguió aparte
    (el video en sí no lo trae; hay que pegarlo a mano o sacarlo por scraping)}.
    Devuelve {"fuente", "tipo": "texto"|"visual", "contenido": str | [bytes,...],
    "caption": str}."""
    caption = (fuente.get("caption") or "").strip()
    if fuente["tipo"] == "url":
        local = _descargar_video(fuente["valor"], tmpdir / f"ref{idx}")
        etiqueta = fuente["valor"]
    else:
        local = Path(fuente["valor"])
        etiqueta = local.name

    if _tiene_audio(local):
        audio = tmpdir / f"ref{idx}.wav"
        _extraer_audio_de_archivo(local, audio)
        texto = _transcribir(audio)
        return {"fuente": etiqueta, "tipo": "texto", "contenido": texto[:MAX_TRANSCRIPCION_CHARS],
               "caption": caption}

    frames = _extraer_frames(local, tmpdir, idx)
    return {"fuente": etiqueta, "tipo": "visual", "contenido": [f.read_bytes() for f in frames],
           "caption": caption}


SCHEMA = {
    "type": "object",
    "properties": {
        "referentes": {
            "type": "array",
            "description": "Análisis de cada video, en el mismo orden que las transcripciones dadas",
            "items": {
                "type": "object",
                "properties": {
                    "tema_principal": {"type": "string"},
                    "hook_usado": {"type": "string",
                                   "description": "Los primeros segundos, textual o parafraseado"},
                    "estructura": {"type": "string",
                                   "description": "Cómo está armado el video de principio a fin, en 1-2 frases"},
                    "por_que_funciona": {"type": "string",
                                         "description": "Qué mecanismo de retención/persuasión usa"},
                    "patron_copy": {"type": "string",
                                    "description": "Patrón del copy/caption que acompaña el post: tono, "
                                                   "largo, uso de emojis, tipo de CTA al final, hashtags "
                                                   "— cadena vacía si no había caption disponible para este"},
                },
                "required": ["tema_principal", "hook_usado", "estructura", "por_que_funciona", "patron_copy"],
            },
        },
        "angulos": {
            "type": "array",
            "description": "3 a 5 ángulos de contenido PROPIOS (no copiar), inspirados en los "
                           "patrones que funcionaron en los referentes analizados",
            "items": {
                "type": "object",
                "properties": {
                    "angulo": {"type": "string"},
                    "gancho": {"type": "string", "description": "Hook concreto y listo para usar"},
                    "inspirado_en": {"type": "string",
                                     "description": "Qué referente/patrón inspiró este ángulo — usar "
                                                    "\"Referente 1\", \"Referente 2\"... NUNCA nombres "
                                                    "propios de personas/marcas/cuentas"},
                    "formato_sugerido": {"type": "string", "enum": ["video", "carrusel", "imagen"]},
                },
                "required": ["angulo", "gancho", "inspirado_en", "formato_sugerido"],
            },
        },
    },
    "required": ["referentes", "angulos"],
}

_CITA = re.compile(r"\[\d+\]")


def _brand(perfil: str) -> dict:
    marcas = json.loads((BASE / "brand_config.json").read_text())
    return marcas.get(perfil, {})


def analizar_referentes(fuentes: list, perfil: str = "") -> dict:
    """fuentes: lista de {"tipo": "url"|"archivo", "valor": ...}. Devuelve análisis + ángulos.

    Cada fuente se procesa de forma independiente: si tiene audio se transcribe
    (whisper); si no (ej. scroll silencioso de un carrusel), se analiza por
    frames con IA con visión. Se puede mezclar ambos tipos en una sola tanda.
    """
    if not fuentes:
        raise ReferentesError("Pasá al menos un link o archivo de video.")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        preparadas = [_preparar_fuente(f, tmpdir, i) for i, f in enumerate(fuentes)]

    brand = _brand(perfil)
    contexto_audiencia = (
        f" La audiencia del creador que va a usar estas ideas es: {brand['target_audience']}."
        if brand.get("target_audience") else ""
    )
    system = (
        "Eres un analista de contenido viral para redes sociales (TikTok/Reels/IG). "
        "Te paso videos de referentes/competidores — algunos como transcripción de "
        "su narración, otros (sin audio, ej. scrolls de carrusel grabados en "
        "pantalla) como frames en orden para que los analices visualmente. Por "
        "cada uno identificas tema, hook usado (el gancho visual o hablado de "
        "los primeros segundos/láminas), estructura narrativa y por qué funciona. "
        "Después, basándote en esos PATRONES (nunca copiando el contenido literal), "
        "propones ángulos de contenido propios y originales para otro creador.\n\n"
        "REGLA ESTRICTA: NUNCA menciones nombres propios de personas, marcas, "
        "empresas o @handles de las cuentas de referencia, aunque aparezcan "
        "visibles en el video/frames (nombre del creador, firma, marca de agua, "
        "logo, título del negocio, etc.). Referite a cada uno SIEMPRE como "
        "\"Referente 1\", \"Referente 2\", etc. — nunca por su nombre real. Esto "
        "aplica a todos los campos de tu respuesta, incluido `inspirado_en`."
        + contexto_audiencia
    )

    de_texto = [p for p in preparadas if p["tipo"] == "texto"]
    # generar_json_imagenes manda la etiqueta como texto justo antes de los
    # frames — si hay caption, se lo agregamos a la etiqueta para que el
    # modelo lo vea junto a las imágenes (no hay un canal aparte para texto
    # extra por fuente visual en ese formato de partes intercaladas).
    visuales = []
    for p in preparadas:
        if p["tipo"] != "visual":
            continue
        etiqueta = f"{p['fuente']} — caption/copy del post: {p['caption']}" if p["caption"] else p["fuente"]
        visuales.append((etiqueta, p["contenido"]))

    bloque = "\n\n".join(
        f"--- {p['fuente']} (transcripción de audio) ---\n{p['contenido']}"
        + (f"\n\n--- {p['fuente']} (caption/copy del post) ---\n{p['caption']}" if p["caption"] else "")
        for p in de_texto
    )
    texto_prompt = (
        "Analiza estos videos de referentes (guion hablado Y el caption/copy que "
        f"acompaña cada post cuando esté disponible) y proponé ángulos de contenido "
        f"propios:\n\n{bloque}"
    )

    if visuales:
        resultado = llm_client.generar_json_imagenes("referentes", system, texto_prompt, visuales, SCHEMA)
    else:
        resultado = llm_client.generar_json("referentes", system, texto_prompt, SCHEMA)

    for r in resultado.get("referentes", []):
        for k in ("tema_principal", "hook_usado", "estructura", "por_que_funciona", "patron_copy"):
            r[k] = _CITA.sub("", r.get(k, "")).strip()
    for a in resultado.get("angulos", []):
        for k in ("angulo", "gancho", "inspirado_en"):
            a[k] = _CITA.sub("", a.get(k, "")).strip()

    # La etiqueta SIEMPRE es genérica ("Referente N") — nunca la URL/nombre
    # de archivo crudo, que puede llevar el handle de la cuenta (ver regla
    # de privacidad).
    for i, r in enumerate(resultado.get("referentes", []), 1):
        r["fuente"] = f"Referente {i}"

    return resultado


if __name__ == "__main__":
    import sys
    urls = sys.argv[1:]
    if not urls:
        print("Uso: python referentes.py <url1> [url2 ...]")
        sys.exit(1)
    fuentes = [{"tipo": "url", "valor": u} for u in urls]
    print(json.dumps(analizar_referentes(fuentes), ensure_ascii=False, indent=2))
