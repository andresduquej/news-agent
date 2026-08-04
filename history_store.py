"""
History Store — registro del contenido ya generado/producido, para verlo
en el dashboard. Cada entrada guarda la metadata + las rutas de los archivos
producidos. Persiste en history.jsonl.
"""

import json
import shutil
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "history.jsonl"
PRODUCCIONES = BASE / "producciones"


def registrar(slug: str, contenido: dict, archivos: list,
             test_id: str = "", test_variante: str = "", prediccion: str = "") -> dict:
    """Guarda una producción en el historial. `archivos` son rutas web
    (/producciones/...). Si el slug ya existe, lo reemplaza (regeneración).
    `test_id`/`test_variante` (opcionales): cuando la pieza es una de varias
    variantes de un mismo test (hook×CTA, ver "Test de variantes" en el
    dashboard), agrupa esta pieza con sus hermanas en /history.
    `prediccion` (opcional): expectativa del usuario ANTES de publicar, en
    texto libre — para comparar después contra el resultado real (métricas
    cargadas en /history) y calibrar criterio propio."""
    entrada = {
        "id": slug,
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "titulo": contenido.get("titulo", "Sin título"),
        "formato": contenido.get("formato", ""),
        "perfil": contenido.get("perfil", ""),
        "tema": contenido.get("noticia", {}).get("tema", ""),
        "caption": contenido.get("caption", ""),
        "hashtags": contenido.get("hashtags", []),
        "noticia_url": contenido.get("noticia", {}).get("url", ""),
        "archivos": archivos,
        "test_id": test_id,
        "test_variante": test_variante,
        "prediccion": prediccion,
    }
    entradas = [e for e in _leer() if e["id"] != slug]
    entradas.append(entrada)
    _escribir(entradas)
    return entrada


def listar() -> list:
    """Todas las entradas, más reciente primero."""
    return sorted(_leer(), key=lambda e: e["fecha"], reverse=True)


def eliminar(slug: str, borrar_archivos: bool = True) -> None:
    """Quita la entrada del historial y (por defecto) borra su carpeta."""
    entradas = [e for e in _leer() if e["id"] != slug]
    _escribir(entradas)
    if borrar_archivos:
        carpeta = (PRODUCCIONES / slug).resolve()
        # Guardrail: solo borrar dentro de producciones/.
        if carpeta.is_dir() and PRODUCCIONES.resolve() in carpeta.parents:
            shutil.rmtree(carpeta, ignore_errors=True)


def _leer() -> list:
    if not ARCHIVO.exists():
        return []
    return [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]


def _escribir(entradas: list) -> None:
    ARCHIVO.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entradas) + ("\n" if entradas else ""),
        encoding="utf-8",
    )
