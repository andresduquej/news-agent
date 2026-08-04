"""
Matriz de Viralidad (28 jul 2026) — detecta qué patrones (hooks, temas,
estructura, frases, duración, CTA) se repiten en las piezas propias que
mejor funcionaron vs. las que menos, comparando `history_store` (lo ya
producido) contra las métricas reales que el usuario cargó en `/history`
(`metricas_store`). Después, `simular_guion()` cruza un guion nuevo contra
esa matriz ya generada y devuelve una probabilidad + sugerencias concretas
ANTES de producir el contenido final.

Inspirado en un sistema similar visto en un PDF de un tercero (scraping de
referentes con Apify + matrix + simulador) — acá se arma 100% con datos que
la app ya tenía guardados (historial + métricas manuales), sin scraping ni
costo nuevo de API.

Reusa la tarea "generacion" de config_store — no amerita una tarea de IA
propia, es el mismo tipo de trabajo (redacción/análisis de contenido).
"""

import json
import time
from pathlib import Path

import history_store
import llm_client
import metricas_store
import ranker_ia  # carga .env

BASE = Path(__file__).resolve().parent
ARCHIVO_MATRIZ = BASE / "matriz_viralidad.json"

MINIMO_PIEZAS = 3

SCHEMA_MATRIZ = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string", "description": "1-2 frases con la conclusión general"},
        "hooks": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "patron": {"type": "string", "description": "Tipo de hook que mejor funcionó (pregunta/dato/negación/historia/etc.)"},
                "evidencia": {"type": "string", "description": "Qué piezas (por título) lo prueban y sus métricas"},
            },
            "required": ["patron", "evidencia"],
        }},
        "temas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "patron": {"type": "string", "description": "Tema o ángulo que generó más engagement"},
                "evidencia": {"type": "string"},
            },
            "required": ["patron", "evidencia"],
        }},
        "estructuras": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "patron": {"type": "string", "description": "Estructura narrativa que se repite en lo que mejor funcionó"},
                "evidencia": {"type": "string"},
            },
            "required": ["patron", "evidencia"],
        }},
        "frases": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "patron": {"type": "string", "description": "Palabra/expresión que aparece en lo viral y no en lo flojo"},
                "evidencia": {"type": "string"},
            },
            "required": ["patron", "evidencia"],
        }},
        "ctas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "patron": {"type": "string", "description": "Tipo de CTA que generó más comentarios/guardados"},
                "evidencia": {"type": "string"},
            },
            "required": ["patron", "evidencia"],
        }},
        "duracion_o_extension_optima": {"type": "string", "description": "Duración (video) o cantidad de slides/longitud de copy que mejor performó"},
    },
    "required": ["resumen", "hooks", "temas", "estructuras", "frases", "ctas", "duracion_o_extension_optima"],
}

SCHEMA_SIMULACION = {
    "type": "object",
    "properties": {
        "probabilidad": {"type": "string", "enum": ["alta", "media", "baja"]},
        "justificacion": {"type": "string", "description": "Por qué esa probabilidad, en 1-2 frases concretas"},
        "cumple": {"type": "array", "items": {"type": "string"}, "description": "Elementos del patrón que el guion SÍ cumple"},
        "no_cumple": {"type": "array", "items": {"type": "string"}, "description": "Elementos del patrón que el guion NO cumple"},
        "sugerencias": {"type": "array", "items": {"type": "string"}, "description": "Cambios concretos al hook/estructura/CTA para subir probabilidades"},
    },
    "required": ["probabilidad", "justificacion", "cumple", "no_cumple", "sugerencias"],
}


def _piezas_con_metricas(perfil: str = "") -> list:
    """Cruza history_store (lo producido) con metricas_store (lo cargado a
    mano) por id/slug — solo entran piezas que SÍ tienen métricas
    registradas, ordenadas de más a menos engagement (likes+comentarios*3+
    guardados*2+compartidos*2 — pondera más lo que cuesta más conseguir)."""
    metricas = metricas_store.listar()
    piezas = []
    for h in history_store.listar():
        if perfil and h.get("perfil") != perfil:
            continue
        m = metricas.get(h["id"])
        if not m:
            continue
        score = m["likes"] + m["comentarios"] * 3 + m["guardados"] * 2 + m["compartidos"] * 2
        piezas.append({**h, "metricas": m, "_score": score})
    return sorted(piezas, key=lambda p: p["_score"], reverse=True)


def _cargar_todas() -> dict:
    if not ARCHIVO_MATRIZ.exists():
        return {}
    return json.loads(ARCHIVO_MATRIZ.read_text(encoding="utf-8"))


def _guardar_todas(datos: dict) -> None:
    ARCHIVO_MATRIZ.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def obtener_matriz(perfil: str = "") -> dict | None:
    return _cargar_todas().get(perfil or "_global")


def generar_matriz(perfil: str = "") -> dict:
    """Genera (y persiste) la matriz de viralidad para `perfil` (o global si
    no se pasa). Requiere al menos MINIMO_PIEZAS piezas con métricas
    cargadas en /history — si no, levanta ValueError con un mensaje claro
    para mostrar en el dashboard (no es un error de la IA, es falta de
    datos)."""
    piezas = _piezas_con_metricas(perfil)
    if len(piezas) < MINIMO_PIEZAS:
        raise ValueError(
            f"Necesitás al menos {MINIMO_PIEZAS} piezas con métricas cargadas en /history "
            f"para generar la matriz (hoy hay {len(piezas)}). Cargá likes/comentarios/"
            "guardados/compartidos de lo que ya publicaste y volvé a intentar."
        )

    bloque = "\n\n".join(
        f"--- {p['titulo']} ({p['formato']}, {p['fecha']}) ---\n"
        f"Tema: {p.get('tema', '')}\nCaption: {p.get('caption', '')}\n"
        f"Métricas: {p['metricas']['likes']} likes, {p['metricas']['comentarios']} comentarios, "
        f"{p['metricas']['guardados']} guardados, {p['metricas']['compartidos']} compartidos, "
        f"{p['metricas']['alcance']} de alcance."
        for p in piezas
    )
    system = (
        "Eres un analista de contenido viral para redes sociales. Te paso piezas YA "
        "PUBLICADAS de un mismo creador, con sus métricas reales, ordenadas de más a "
        "menos engagement. Comparando las que MÁS funcionaron contra las que MENOS "
        "funcionaron, detectá patrones concretos en hooks, temas, estructura narrativa, "
        "frases/palabras y CTAs — cada patrón con evidencia citando qué piezas lo prueban. "
        "Sé específico y honesto: si no hay suficiente contraste en los datos para un "
        "campo, decilo en vez de inventar un patrón."
    )
    prompt = f"Piezas publicadas, de más a menos engagement:\n\n{bloque}"

    resultado = llm_client.generar_json("generacion", system, prompt, SCHEMA_MATRIZ)
    resultado["fecha_generada"] = time.strftime("%Y-%m-%d %H:%M:%S")
    resultado["piezas_analizadas"] = len(piezas)

    datos = _cargar_todas()
    datos[perfil or "_global"] = resultado
    _guardar_todas(datos)
    return resultado


def simular_guion(texto: str, perfil: str = "") -> dict:
    """Cruza `texto` (guion/copy nuevo, todavía sin producir) contra la
    última matriz generada para `perfil` — requiere haberla generado antes
    (ValueError si no existe)."""
    matriz = obtener_matriz(perfil)
    if not matriz:
        raise ValueError("Todavía no generaste la matriz de viralidad — hacelo primero en /history.")

    system = (
        "Eres un analista de contenido viral. Te paso la MATRIZ DE VIRALIDAD ya "
        "detectada (patrones de lo que funcionó antes, con evidencia) y un GUION NUEVO "
        "que el usuario quiere publicar. Cruzá el guion contra la matriz y decidí qué "
        "probabilidad tiene de performar. Sé honesto y específico — no digas que todo "
        "está bien si no lo está."
    )
    prompt = (
        f"MATRIZ DE VIRALIDAD:\n{json.dumps(matriz, ensure_ascii=False, indent=2)}\n\n"
        f"GUION NUEVO A EVALUAR:\n{texto}"
    )
    return llm_client.generar_json("generacion", system, prompt, SCHEMA_SIMULACION)
