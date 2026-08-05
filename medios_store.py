"""
Medios Store — registro de clips de stock (Pexels) ya usados en piezas
anteriores, para no repetir el mismo B-roll entre videos/imágenes distintos
que van a la MISMA red social — Andrés pidió esto porque el público puede
notar que dos posts comparten imágenes (4 ago 2026). Persiste en
medios_usados.jsonl.
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "medios_usados.jsonl"

VENTANA_DIAS = 60  # cuánto atrás se considera "reciente" para evitar repetir un clip


def _leer() -> list:
    if not ARCHIVO.exists():
        return []
    entradas = []
    for linea in ARCHIVO.read_text().splitlines():
        if linea.strip():
            entradas.append(json.loads(linea))
    return entradas


def registrar(video_id: int, query: str, perfil: str = "") -> None:
    entrada = {
        "video_id": video_id, "query": query, "perfil": perfil,
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with ARCHIVO.open("a") as fh:
        fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def usados_recientes(perfil: str = "") -> set:
    """IDs de video de Pexels usados en los últimos VENTANA_DIAS. Si `perfil`
    viene vacío, se filtra a nivel global (ignora todas las cuentas); si se
    pasa, solo cuenta lo usado por ESE perfil (dos perfiles distintos pueden
    compartir clip sin problema, ya que publican en cuentas separadas)."""
    corte = time.time() - VENTANA_DIAS * 86400
    ids = set()
    for e in _leer():
        try:
            ts = time.mktime(time.strptime(e["fecha"], "%Y-%m-%d %H:%M:%S"))
        except (KeyError, ValueError):
            continue
        if ts < corte:
            continue
        if perfil and e.get("perfil") and e["perfil"] != perfil:
            continue
        ids.add(e["video_id"])
    return ids
