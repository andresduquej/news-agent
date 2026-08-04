"""
Series Store — series recurrentes de contenido (ej. "Lunes de IA"): un
nombre + día de la semana fijo + tema/formato/canal por defecto. Al generar
una semana en `/calendario`, cada serie ACTIVA agrega su propio slot en su
día correspondiente además del reparto round-robin normal — no reemplaza
nada, es una cita fija que siempre aparece.

Persiste en series.jsonl. No genera contenido ni publica nada — igual que
el resto del calendario, es solo el mapa de la semana.
"""

import json
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "series.jsonl"

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
FORMATOS = ["video", "carrusel", "imagen"]


def _leer() -> list:
    if not ARCHIVO.exists():
        return []
    return [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escribir(series: list) -> None:
    ARCHIVO.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in series) + ("\n" if series else ""),
        encoding="utf-8",
    )


def listar() -> list:
    return sorted(_leer(), key=lambda s: (s["dia_semana"], s["creado"]))


def activas() -> list:
    return [s for s in listar() if s["activa"]]


def crear(nombre: str, dia_semana: int, tema: str = "", formato: str = "", canal: str = "") -> dict:
    serie = {
        "id": uuid.uuid4().hex[:12],
        "nombre": nombre.strip() or "Serie sin nombre",
        "dia_semana": max(0, min(6, int(dia_semana))),
        "tema": tema,
        "formato": formato if formato in FORMATOS else "",
        "canal": canal,
        "activa": True,
        "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    series = _leer()
    series.append(serie)
    _escribir(series)
    return serie


def editar(serie_id: str, cambios: dict) -> dict | None:
    series = _leer()
    for s in series:
        if s["id"] == serie_id:
            for k in ("nombre", "dia_semana", "tema", "formato", "canal", "activa"):
                if k in cambios:
                    s[k] = cambios[k]
            _escribir(series)
            return s
    return None


def eliminar(serie_id: str) -> bool:
    series = _leer()
    filtradas = [s for s in series if s["id"] != serie_id]
    if len(filtradas) == len(series):
        return False
    _escribir(filtradas)
    return True
