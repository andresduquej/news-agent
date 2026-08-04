"""
Calendario Store — planificador de contenido semanal.

Organiza QUÉ publicar cada día (formato + canal + tema), no publica nada
automáticamente — es solo el mapa de la semana. Cada slot se puede llevar
después al flujo normal ("Crear contenido") y opcionalmente asociarlo a la
producción ya hecha (`slug` del history).

Persiste en calendario.jsonl (slots) y calendario_config.json (canales
activos + objetivo semanal por formato).
"""

import json
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import series_store

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "calendario.jsonl"
CONFIG_FILE = BASE / "calendario_config.json"

CANALES_DISPONIBLES = ["Instagram", "TikTok", "LinkedIn", "YouTube"]
FORMATOS = ["video", "carrusel", "imagen"]
ESTADOS = ["pendiente", "listo", "publicado"]

DEFAULT_CONFIG = {
    "canales": ["Instagram", "TikTok"],
    "objetivo_semanal": {"video": 3, "carrusel": 2, "imagen": 1},
}


# ---------------------------------------------------------------------------
# Config (canales activos + objetivo semanal)
# ---------------------------------------------------------------------------

def cargar_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def guardar_config(canales: list, objetivo_semanal: dict) -> dict:
    config = {
        "canales": [c for c in canales if c in CANALES_DISPONIBLES] or DEFAULT_CONFIG["canales"],
        "objetivo_semanal": {f: max(0, int(objetivo_semanal.get(f, 0))) for f in FORMATOS},
    }
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return config


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

def _leer() -> list:
    if not ARCHIVO.exists():
        return []
    return [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escribir(slots: list) -> None:
    ARCHIVO.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in slots) + ("\n" if slots else ""),
        encoding="utf-8",
    )


def lunes_de(fecha_iso: str) -> str:
    """Dado cualquier fecha YYYY-MM-DD, devuelve el lunes de esa semana."""
    d = date.fromisoformat(fecha_iso)
    return (d - timedelta(days=d.weekday())).isoformat()


def semana_actual() -> str:
    return lunes_de(date.today().isoformat())


def listar_semana(lunes: str) -> list:
    fin = (date.fromisoformat(lunes) + timedelta(days=6)).isoformat()
    return sorted(
        (s for s in _leer() if lunes <= s["fecha"] <= fin),
        key=lambda s: (s["fecha"], s["creado"]),
    )


def agregar_slot(fecha: str, formato: str, canal: str, tema: str = "",
                 serie_id: str = "", serie_nombre: str = "") -> dict:
    slot = {
        "id": uuid.uuid4().hex[:12],
        "fecha": fecha,
        "formato": formato if formato in FORMATOS else FORMATOS[0],
        "canal": canal if canal in CANALES_DISPONIBLES else CANALES_DISPONIBLES[0],
        "tema": tema,
        "estado": "pendiente",
        "slug": "",
        "serie_id": serie_id,
        "serie_nombre": serie_nombre,
        "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    slots = _leer()
    slots.append(slot)
    _escribir(slots)
    return slot


def editar_slot(slot_id: str, cambios: dict) -> dict | None:
    slots = _leer()
    for s in slots:
        if s["id"] == slot_id:
            for k in ("fecha", "formato", "canal", "tema", "estado", "slug"):
                if k in cambios:
                    s[k] = cambios[k]
            _escribir(slots)
            return s
    return None


def eliminar_slot(slot_id: str) -> bool:
    slots = _leer()
    filtrados = [s for s in slots if s["id"] != slot_id]
    if len(filtrados) == len(slots):
        return False
    _escribir(filtrados)
    return True


def generar_semana(lunes: str, forzar: bool = False) -> list:
    """Genera los slots de la semana según el objetivo/canales de la config.
    Si ya hay slots esa semana y no se fuerza, devuelve los existentes sin tocar nada."""
    existentes = listar_semana(lunes)
    if existentes and not forzar:
        return existentes
    if forzar:
        ids_semana = {s["id"] for s in existentes}
        slots_restantes = [s for s in _leer() if s["id"] not in ids_semana]
        _escribir(slots_restantes)

    config = cargar_config()
    canales = config["canales"] or DEFAULT_CONFIG["canales"]
    items = []
    for formato, cantidad in config["objetivo_semanal"].items():
        items.extend([formato] * cantidad)
    if not items:
        return []

    dias = [(date.fromisoformat(lunes) + timedelta(days=i)).isoformat() for i in range(7)]
    nuevos = []
    for i, formato in enumerate(items):
        fecha = dias[i % 7]
        canal = canales[i % len(canales)]
        nuevos.append(agregar_slot(fecha, formato, canal))

    # Series recurrentes: cita fija por día de la semana, además del reparto
    # round-robin de arriba (no lo reemplaza — es un slot extra garantizado).
    for serie in series_store.activas():
        fecha = dias[serie["dia_semana"]]
        nuevos.append(agregar_slot(
            fecha, serie["formato"] or FORMATOS[0], serie["canal"] or canales[0],
            tema=serie["tema"], serie_id=serie["id"], serie_nombre=serie["nombre"],
        ))
    return listar_semana(lunes)
