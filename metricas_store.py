"""
Métricas Store — registro manual de qué resultado dio cada pieza publicada
(likes, comentarios, guardados, alcance). Un registro por slug de historial;
si se vuelve a registrar, se actualiza. Persiste en metricas.jsonl.

Sirve como base para más adelante detectar qué temas/hooks funcionan mejor;
por ahora solo guarda y muestra los datos.
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "metricas.jsonl"


def registrar(slug: str, likes: int = 0, comentarios: int = 0, guardados: int = 0,
             compartidos: int = 0, alcance: int = 0) -> dict:
    """Guarda/actualiza las métricas de la pieza `slug`."""
    entrada = {
        "slug": slug,
        "fecha_registro": time.strftime("%Y-%m-%d %H:%M:%S"),
        "likes": max(0, int(likes)),
        "comentarios": max(0, int(comentarios)),
        "guardados": max(0, int(guardados)),
        "compartidos": max(0, int(compartidos)),
        "alcance": max(0, int(alcance)),
    }
    entradas = [e for e in _leer() if e["slug"] != slug]
    entradas.append(entrada)
    _escribir(entradas)
    return entrada


def obtener(slug: str) -> dict | None:
    for e in _leer():
        if e["slug"] == slug:
            return e
    return None


def listar() -> dict:
    """Todas las métricas indexadas por slug, para joinear con el historial."""
    return {e["slug"]: e for e in _leer()}


def eliminar(slug: str) -> bool:
    entradas = _leer()
    filtradas = [e for e in entradas if e["slug"] != slug]
    if len(filtradas) == len(entradas):
        return False
    _escribir(filtradas)
    return True


def _leer() -> list:
    if not ARCHIVO.exists():
        return []
    return [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escribir(entradas: list) -> None:
    ARCHIVO.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entradas) + ("\n" if entradas else ""),
        encoding="utf-8",
    )
