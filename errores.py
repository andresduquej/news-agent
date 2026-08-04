"""
Errores — registro de fallos de la plataforma para el apartado de Configuración.

Cada error se guarda en errores.jsonl (persiste entre reinicios) y se expone
para el dashboard: qué pasó, cuándo, en qué parte de la app.
"""

import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "errores.jsonl"
MAX_MOSTRAR = 100


def log(contexto: str, mensaje: str) -> None:
    """Registra un error. `contexto` identifica la parte de la app (ej. 'ranker_ia')."""
    entrada = {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "contexto": contexto,
        "mensaje": str(mensaje)[:500],
    }
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def listar(limite: int = MAX_MOSTRAR) -> list:
    """Devuelve los últimos `limite` errores, más reciente primero."""
    if not ARCHIVO.exists():
        return []
    lineas = ARCHIVO.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in reversed(lineas[-limite:])]


def limpiar() -> None:
    if ARCHIVO.exists():
        ARCHIVO.unlink()
