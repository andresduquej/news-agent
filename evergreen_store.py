"""
Evergreen Store — banco de noticias/ángulos que no caducan, guardados para
usar en días flojos (sin noticias frescas relevantes). Persiste en evergreen.jsonl.
"""

import json
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "evergreen.jsonl"


def agregar(noticia: dict, nota: str = "") -> dict:
    """Guarda una noticia/ángulo en el banco evergreen."""
    entrada = {
        "id": uuid.uuid4().hex[:12],
        "fecha_guardado": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nota": nota,
        "noticia": {
            "titulo": noticia.get("titulo", ""),
            "resumen": noticia.get("resumen", ""),
            "tema": noticia.get("tema", ""),
            "fuente": noticia.get("fuente", ""),
            "url": noticia.get("url", ""),
            "justificacion": noticia.get("justificacion", noticia.get("motivo", "")),
        },
    }
    entradas = _leer()
    entradas.append(entrada)
    _escribir(entradas)
    return entrada


def listar() -> list:
    """Todas las entradas, más reciente primero."""
    return sorted(_leer(), key=lambda e: e["fecha_guardado"], reverse=True)


def eliminar(entry_id: str) -> bool:
    entradas = _leer()
    filtradas = [e for e in entradas if e["id"] != entry_id]
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
