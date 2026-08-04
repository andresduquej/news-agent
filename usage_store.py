"""
Usage Store — registro de gastos de herramientas (tokens y USD estimados)
para el apartado de Configuración.

Precios aproximados (USD por 1M tokens, o por 1K caracteres para voz).
Actualizar aquí si cambian las tarifas de cada proveedor.
"""

import csv
import io
import json
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "gastos.jsonl"

PRECIOS_TOKENS = {
    # modelo: (USD por 1M tokens entrada, USD por 1M tokens salida)
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-image": (0.30, 30.00),  # salida de imagen se factura como tokens, tarifa pública
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "sonar-pro": (3.00, 15.00),
    "sonar": (1.00, 1.00),
}
PRECIO_ELEVENLABS_POR_1K_CHARS = 0.30  # estimado, plan Creator

CAMPOS_CSV = ["id", "fecha", "herramienta", "modelo", "tarea",
              "tokens_entrada", "tokens_salida", "costo_usd"]


def _costo_tokens(modelo: str, tokens_in: int, tokens_out: int) -> float:
    precio_in, precio_out = PRECIOS_TOKENS.get(modelo, (0.0, 0.0))
    return (tokens_in / 1_000_000 * precio_in) + (tokens_out / 1_000_000 * precio_out)


def registrar_ia(tarea: str, proveedor: str, modelo: str,
                 tokens_in: int, tokens_out: int) -> None:
    entrada = {
        "id": uuid.uuid4().hex[:12],
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "herramienta": proveedor,
        "modelo": modelo,
        "tarea": tarea,
        "tokens_entrada": tokens_in,
        "tokens_salida": tokens_out,
        "costo_usd": round(_costo_tokens(modelo, tokens_in, tokens_out), 6),
    }
    _append(entrada)


def registrar_voz(caracteres: int) -> None:
    entrada = {
        "id": uuid.uuid4().hex[:12],
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "herramienta": "elevenlabs",
        "modelo": "voz",
        "tarea": "video",
        "tokens_entrada": caracteres,
        "tokens_salida": 0,
        "costo_usd": round(caracteres / 1000 * PRECIO_ELEVENLABS_POR_1K_CHARS, 6),
    }
    _append(entrada)


def _append(entrada: dict) -> None:
    with ARCHIVO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def _leer_todas() -> list:
    if not ARCHIVO.exists():
        return []
    entradas = []
    cambio = False
    for l in ARCHIVO.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if "id" not in e:  # entradas viejas sin id (antes de este cambio)
            e["id"] = uuid.uuid4().hex[:12]
            cambio = True
        entradas.append(e)
    if cambio:
        _escribir_todas(entradas)
    return entradas


def _escribir_todas(entradas: list) -> None:
    with ARCHIVO.open("w", encoding="utf-8") as f:
        for e in entradas:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def eliminar(entry_id: str) -> bool:
    """Borra una línea de gasto por id. Devuelve True si existía."""
    entradas = _leer_todas()
    restantes = [e for e in entradas if e["id"] != entry_id]
    if len(restantes) == len(entradas):
        return False
    _escribir_todas(restantes)
    return True


def eliminar_todo() -> None:
    if ARCHIVO.exists():
        ARCHIVO.unlink()


def exportar_csv() -> str:
    entradas = _leer_todas()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CAMPOS_CSV)
    writer.writeheader()
    for e in entradas:
        writer.writerow({k: e.get(k, "") for k in CAMPOS_CSV})
    return buf.getvalue()


def resumen(herramienta: str = "", tarea: str = "", limite: int = 5) -> dict:
    """Totales generales (siempre globales) + lista reciente filtrable/limitable.

    `herramienta`/`tarea` filtran la lista `recientes` (no los totales).
    `limite` acota cuántas entradas recientes devolver — por defecto 5, para
    no dejar una lista larga en la UI.
    """
    entradas = _leer_todas()

    total_usd = sum(e["costo_usd"] for e in entradas)
    por_herramienta: dict = {}
    for e in entradas:
        h = e["herramienta"]
        acc = por_herramienta.setdefault(h, {"herramienta": h, "llamadas": 0,
                                              "tokens_entrada": 0, "tokens_salida": 0,
                                              "costo_usd": 0.0})
        acc["llamadas"] += 1
        acc["tokens_entrada"] += e["tokens_entrada"]
        acc["tokens_salida"] += e["tokens_salida"]
        acc["costo_usd"] += e["costo_usd"]
    for acc in por_herramienta.values():
        acc["costo_usd"] = round(acc["costo_usd"], 4)

    filtradas = list(reversed(entradas))
    if herramienta:
        filtradas = [e for e in filtradas if e["herramienta"] == herramienta]
    if tarea:
        filtradas = [e for e in filtradas if e["tarea"] == tarea]

    return {
        "total_usd": round(total_usd, 4),
        "por_herramienta": sorted(por_herramienta.values(), key=lambda x: -x["costo_usd"]),
        "herramientas": sorted({e["herramienta"] for e in entradas}),
        "tareas": sorted({e["tarea"] for e in entradas}),
        "recientes": filtradas[:limite] if limite else filtradas,
        "total_filtradas": len(filtradas),
    }
