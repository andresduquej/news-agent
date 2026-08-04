"""
Gate de Calidad de Video (28 jul 2026) — chequeo automático BLOQUEANTE antes
de que un video (completo o lámina de carrusel producida como video) quede
como entrega final. Solo aplica a video — los briefs de texto y las
imágenes/carruseles estáticos no pasan por acá.

Dos chequeos, sin decodificar frame a frame a mano (usa filtros nativos de
FFmpeg, que ya es una dependencia obligatoria del proyecto):

1. **Estático/sin B-roll**: `freezedetect` de FFmpeg detecta tramos sin
   cambio de imagen (voz sola sobre un frame congelado — señal de que el
   B-roll falló en pegar o se cortó antes de tiempo). Rechaza si hay un
   tramo seguido más largo que `UMBRAL_CONGELADO_SEG`, o si la cobertura
   visual total cae debajo de `UMBRAL_COBERTURA_MIN`.
2. **B-roll sin variedad real**: si el contenido pedía B-roll distinto por
   tramo (`broll_query_<segmento>`) pero todas las queries terminaron
   siendo la misma (fallback silencioso a un genérico), no hay variedad
   visual aunque el video "se mueva".
"""

import subprocess
from pathlib import Path

UMBRAL_CONGELADO_SEG = 3.0    # tramo seguido sin cambio de imagen que ya se considera "estático"
UMBRAL_COBERTURA_MIN = 0.85   # mínimo de duración total con movimiento real


def _duracion(video_path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(video_path),
    ]).strip())


def _detectar_congelados(video_path: Path) -> list:
    """Corre freezedetect y parsea los tramos [(inicio, fin), ...] del log
    de FFmpeg (freezedetect no tiene otra forma de reportar resultados)."""
    resultado = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-vf",
         f"freezedetect=n=-30dB:d={UMBRAL_CONGELADO_SEG}", "-map", "0:v", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    tramos, inicio = [], None
    for linea in resultado.stderr.splitlines():
        linea = linea.strip()
        if "freeze_start:" in linea:
            inicio = float(linea.split("freeze_start:")[1].strip())
        elif "freeze_end:" in linea and inicio is not None:
            tramos.append((inicio, float(linea.split("freeze_end:")[1].strip())))
            inicio = None
    return tramos


def _diversidad_broll(contenido: dict) -> str:
    """Devuelve un motivo de rechazo si el contenido pedía B-roll por tramo
    pero todas las queries usadas terminaron siendo idénticas — cadena
    vacía si no aplica o si está OK."""
    segmentos = ("hook", "obstaculo", "ejecucion", "cta")
    queries = [contenido.get(f"broll_query_{s}") for s in segmentos if contenido.get(f"broll_query_{s}")]
    if len(queries) < 2 or len(set(queries)) > 1:
        return ""
    return (f"Se pidieron {len(queries)} tramos de B-roll pero todos usan la misma "
            f"búsqueda ('{queries[0]}') — sin variedad visual real entre tramos.")


def evaluar(video_path: Path, contenido: dict | None = None) -> dict:
    """Corre el gate sobre un video/lámina-video ya ensamblado. Nunca
    levanta excepción por sí solo — devuelve {'aprobado': bool, 'motivos':
    [str, ...], 'cobertura': float, 'duracion': float} para que el caller
    decida qué hacer (rechazar entrega, loguear, etc.)."""
    motivos = []
    duracion = _duracion(video_path)
    congelados = _detectar_congelados(video_path)
    seg_congelados = sum(fin - ini for ini, fin in congelados)
    cobertura = round(1 - (seg_congelados / duracion), 3) if duracion else 0.0

    tramo_largo = max((fin - ini for ini, fin in congelados), default=0.0)
    if tramo_largo > UMBRAL_CONGELADO_SEG:
        motivos.append(f"{tramo_largo:.1f}s seguidos sin B-roll (imagen estática o solo voz).")
    if cobertura < UMBRAL_COBERTURA_MIN:
        motivos.append(f"Cobertura visual de {cobertura*100:.0f}% (mínimo {UMBRAL_COBERTURA_MIN*100:.0f}%).")

    if contenido is not None:
        motivo_diversidad = _diversidad_broll(contenido)
        if motivo_diversidad:
            motivos.append(motivo_diversidad)

    return {"aprobado": not motivos, "motivos": motivos, "cobertura": cobertura, "duracion": round(duracion, 2)}


def rechazar_archivo(video_path: Path) -> Path:
    """Renombra el archivo con prefijo RECHAZADO_ en la misma carpeta — no
    se borra (queda para que el usuario/desarrollador pueda revisar por qué
    falló), pero no queda como entrega final ni se registra en el historial."""
    destino = video_path.with_name(f"RECHAZADO_{video_path.name}")
    video_path.rename(destino)
    return destino
