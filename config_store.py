"""
Config Store — claves API y selección de modelo de IA por tarea.

Las claves viven en news_agent/.env (nunca se devuelven completas al
frontend, solo enmascaradas). La asignación de modelo por tarea vive en
ia_config.json.
"""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
IA_CONFIG_FILE = BASE / "ia_config.json"
VOZ_CONFIG_FILE = BASE / "voz_config.json"

DEFAULT_VOZ = {"voice_id": "EXAVITQu4vr4xnSDxMaL", "nombre": "Sarah"}

# proveedor -> nombre de la env var. Los modelos de IA (gemini/claude/openai/
# perplexity) ya NO están hardcodeados: se consultan en vivo a cada API
# (ver llm_client.listar_modelos). PROVEEDORES_IA marca cuáles sirven para
# tareas de generación; los de solo-clave (elevenlabs/pexels) no.
PROVEEDORES = {
    "gemini": {"env_var": "GEMINI_API_KEY"},
    "claude": {"env_var": "ANTHROPIC_API_KEY"},
    "openai": {"env_var": "OPENAI_API_KEY"},
    "perplexity": {"env_var": "PERPLEXITY_API_KEY"},
    "elevenlabs": {"env_var": "ELEVENLABS_API_KEY"},
    "pexels": {"env_var": "PEXELS_API_KEY"},
}

PROVEEDORES_IA = ["gemini", "claude", "openai", "perplexity"]

# Respaldo si la API de listado de modelos falla (sin key, sin internet, etc.)
# — así el selector nunca se queda vacío ni la app se cuelga esperando.
MODELOS_RESPALDO = {
    "gemini": ["gemini-2.5-flash"],
    "claude": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "perplexity": ["sonar-pro", "sonar"],
}

TAREAS = ["ranking", "generacion", "resumen", "investigacion", "referentes"]
DEFAULT_IA_CONFIG = {
    "ranking": {"proveedor": "gemini", "modelo": "gemini-2.5-flash"},
    "generacion": {"proveedor": "gemini", "modelo": "gemini-2.5-flash"},
    "resumen": {"proveedor": "gemini", "modelo": "gemini-2.5-flash"},
    # Investigación bajo demanda (Modo 2): Perplexity por defecto — es el
    # único proveedor con acceso a búsqueda web en vivo integrado.
    "investigacion": {"proveedor": "perplexity", "modelo": "sonar-pro"},
    # Análisis de referentes (Modo 3): solo analiza texto (transcripción ya
    # local), no necesita búsqueda web — mismo modelo que generación.
    "referentes": {"proveedor": "gemini", "modelo": "gemini-2.5-flash"},
}


# ---------------------------------------------------------------------------
# Claves API (.env)
# ---------------------------------------------------------------------------

def _leer_env() -> dict:
    if not ENV_FILE.exists():
        return {}
    valores = {}
    for linea in ENV_FILE.read_text().splitlines():
        if "=" in linea and not linea.startswith("#"):
            k, _, v = linea.partition("=")
            valores[k.strip()] = v.strip()
    return valores


def _escribir_env(valores: dict) -> None:
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in valores.items()) + "\n")


def _enmascarar(valor: str) -> str:
    if not valor:
        return ""
    return "•" * 8 + valor[-4:] if len(valor) > 4 else "•" * len(valor)


def listar_claves() -> list:
    actuales = _leer_env()
    return [
        {
            "proveedor": prov,
            "env_var": info["env_var"],
            "configurada": bool(actuales.get(info["env_var"])),
            "valor_enmascarado": _enmascarar(actuales.get(info["env_var"], "")),
        }
        for prov, info in PROVEEDORES.items()
    ]


def guardar_clave(proveedor: str, valor: str) -> None:
    if proveedor not in PROVEEDORES:
        raise ValueError(f"Proveedor desconocido: {proveedor}")
    env_var = PROVEEDORES[proveedor]["env_var"]
    actuales = _leer_env()
    actuales[env_var] = valor.strip()
    _escribir_env(actuales)
    import os
    os.environ[env_var] = valor.strip()


def borrar_clave(proveedor: str) -> None:
    if proveedor not in PROVEEDORES:
        raise ValueError(f"Proveedor desconocido: {proveedor}")
    env_var = PROVEEDORES[proveedor]["env_var"]
    actuales = _leer_env()
    actuales.pop(env_var, None)
    _escribir_env(actuales)
    import os
    os.environ.pop(env_var, None)


# ---------------------------------------------------------------------------
# Modelo de IA por tarea
# ---------------------------------------------------------------------------

def cargar_ia_config() -> dict:
    if not IA_CONFIG_FILE.exists():
        guardar_ia_config(DEFAULT_IA_CONFIG)
    return json.loads(IA_CONFIG_FILE.read_text())


def guardar_ia_config(config: dict) -> dict:
    IA_CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    return config


def set_tarea(tarea: str, proveedor: str, modelo: str) -> dict:
    if tarea not in TAREAS:
        raise ValueError(f"Tarea desconocida: {tarea}")
    if proveedor not in ("gemini", "claude", "openai", "perplexity"):
        raise ValueError(f"Proveedor de IA inválido para tareas: {proveedor}")
    config = cargar_ia_config()
    config[tarea] = {"proveedor": proveedor, "modelo": modelo}
    return guardar_ia_config(config)


def modelo_para(tarea: str) -> dict:
    return cargar_ia_config().get(tarea, DEFAULT_IA_CONFIG[tarea])


# ---------------------------------------------------------------------------
# Voz de ElevenLabs para video
# ---------------------------------------------------------------------------

def cargar_voz() -> dict:
    if not VOZ_CONFIG_FILE.exists():
        set_voz(DEFAULT_VOZ["voice_id"], DEFAULT_VOZ["nombre"])
    return json.loads(VOZ_CONFIG_FILE.read_text())


def set_voz(voice_id: str, nombre: str) -> dict:
    voz = {"voice_id": voice_id, "nombre": nombre}
    VOZ_CONFIG_FILE.write_text(json.dumps(voz, ensure_ascii=False, indent=2))
    return voz
