"""
Ranker IA — Sprint 2 del Agente de Contenido.

Toma las noticias YA filtradas por la heurística local (ranker.py) y usa
Gemini Flash (free tier, $0) para elegir el TOP 5 con score 1-10 y
justificación real, evaluando: relevancia para la audiencia, novedad,
potencial de engagement y aplicabilidad.

Nunca recibe el feed crudo: el filtro heurístico acota a MAX_CANDIDATAS ítems
antes de llamar a la API.

Requiere GEMINI_API_KEY (en el entorno o en .env).
"""

import json
import os
from pathlib import Path

import llm_client

BASE = Path(__file__).resolve().parent

_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

MAX_CANDIDATAS = 15
TOP_N = 5

# Filtro de investigación más estricto (28 jul 2026): en vez de un único
# score, 4 dimensiones independientes. Si "Prueba" puntúa bajo, la noticia
# se descarta del todo aunque el resto sume alto — un ángulo sin evidencia
# verificable detrás no sirve como contenido, por más gancho que tenga.
UMBRAL_PRUEBA = 4

DIMENSIONES = {
    "novedad": "Qué tan nuevo/reciente es esto — no algo que ya se contó mil veces",
    "prueba": "¿Hay un dato, cifra o fuente verificable que lo respalde? No opinión sin sustento",
    "conflicto": "¿Alguien pierde algo, cambia una creencia o se pone en juego si esto es verdad?",
    "accion": "¿El espectador puede hacer algo CONCRETO hoy mismo con esta información?",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "evaluaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer",
                               "description": "Índice de la noticia en la lista de entrada (0-based)"},
                    "novedad": {"type": "integer", "description": DIMENSIONES["novedad"] + " (1 a 10)"},
                    "prueba": {"type": "integer", "description": DIMENSIONES["prueba"] + " (1 a 10)"},
                    "conflicto": {"type": "integer", "description": DIMENSIONES["conflicto"] + " (1 a 10)"},
                    "accion": {"type": "integer", "description": DIMENSIONES["accion"] + " (1 a 10)"},
                    "justificacion": {"type": "string",
                                      "description": "Por qué esos puntajes, en 1-2 frases concretas"},
                    "formato_sugerido": {"type": "string",
                                         "enum": ["video", "carrusel", "imagen"],
                                         "description": "Formato óptimo para esta noticia"},
                },
                "required": ["indice", "novedad", "prueba", "conflicto", "accion",
                            "justificacion", "formato_sugerido"],
            },
        }
    },
    "required": ["evaluaciones"],
}

SYSTEM = (
    "Eres estratega de contenido para redes sociales (Instagram/TikTok) de una agencia "
    "de marketing digital. Audiencia: emprendedores digitales de LatAm interesados en "
    "IA, automatización, ads y ecommerce. Evalúas CADA noticia en 4 dimensiones "
    "independientes (1 a 10 cada una): "
    + " | ".join(f"{k.upper()}: {v}" for k, v in DIMENSIONES.items())
    + ". Sé exigente con PRUEBA en particular — una noticia con gancho pero sin dato/"
    "fuente verificable detrás no merece un puntaje alto ahí, aunque el resto de la "
    "nota te parezca interesante."
)


def rank_ia(noticias: list, top: int = TOP_N) -> list:
    """Devuelve el TOP `top` de `noticias` con 4 puntajes (novedad/prueba/
    conflicto/acción), justificación y formato — descarta cualquier
    candidata cuyo puntaje de Prueba quede debajo de UMBRAL_PRUEBA antes de
    ordenar, sin importar cuánto sume el resto.

    `noticias` debe venir ya filtrado/rankeado por la heurística (ranker.rank).
    """
    candidatas = noticias[:MAX_CANDIDATAS]
    if not candidatas:
        return []

    listado = "\n".join(
        f"[{i}] {n['titulo']} — {n.get('resumen', '')} "
        f"(tema: {n.get('tema', '')}, fuente: {n.get('fuente', '')}, fecha: {n.get('fecha', 's/f')})"
        for i, n in enumerate(candidatas)
    )

    prompt = f"Evalúa CADA UNA de estas noticias en las 4 dimensiones:\n\n{listado}"
    resultado = llm_client.generar_json("ranking", SYSTEM, prompt, SCHEMA)

    evaluadas = []
    for item in resultado["evaluaciones"]:
        i = item["indice"]
        if not (0 <= i < len(candidatas)):
            continue
        if item["prueba"] < UMBRAL_PRUEBA:
            continue  # descartada: sin evidencia sólida, no importa el resto
        noticia = dict(candidatas[i])
        puntajes = {k: item[k] for k in ("novedad", "prueba", "conflicto", "accion")}
        noticia["puntajes"] = puntajes
        noticia["score_ia"] = round(sum(puntajes.values()) / 4)  # promedio 1-10, para el destaque de estrellas
        noticia["justificacion"] = item["justificacion"]
        noticia["formato_sugerido"] = item["formato_sugerido"]
        evaluadas.append(noticia)

    evaluadas.sort(key=lambda n: n["score_ia"], reverse=True)
    return evaluadas[:top]


if __name__ == "__main__":
    import sys
    import news_fetcher
    import ranker

    print("Recolectando y filtrando...", file=sys.stderr)
    filtradas = ranker.rank(news_fetcher.fetch_all())
    print(f"Rankeando {min(len(filtradas), MAX_CANDIDATAS)} con Gemini...", file=sys.stderr)
    print(json.dumps(rank_ia(filtradas), ensure_ascii=False, indent=2))
