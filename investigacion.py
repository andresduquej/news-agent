"""
Investigación bajo demanda — Modo 2 del Agente de Contenido.

El usuario escribe un tema puntual (NO depende de que sea "noticia" — puede
ser cualquier cosa, ej. "cómo funciona el nuevo algoritmo de TikTok Shop").
El agente lo investiga a fondo (por defecto con Perplexity, que tiene
acceso a la web en vivo) y devuelve hallazgos + ángulos de contenido
posibles, cada uno con su propio gancho.

Converge en el mismo flujo de generación que el Modo 1 (barrido de
noticias): cada ángulo se puede tratar como una "noticia" sintética y
pasarse a generator_ia.generar_contenido.
"""

import json
import re
from pathlib import Path

import llm_client
import ranker_ia  # carga .env

_CITA = re.compile(r"\[\d+\]")
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _limpiar(texto: str) -> str:
    """Quita marcadores de cita [3][11] y **negritas** markdown que deja
    Perplexity — el frontend renderiza texto plano, no markdown."""
    texto = _CITA.sub("", texto)
    texto = _MARKDOWN_BOLD.sub(r"\1", texto)
    return texto.strip()

BASE = Path(__file__).resolve().parent

# Mismo filtro de 4 dimensiones que ranker_ia.py (28 jul 2026) — un ángulo
# sin evidencia detrás ("Prueba" baja) se descarta aunque el resto puntúe
# alto, aplicado también al Modo 2.
UMBRAL_PRUEBA = 4

SCHEMA = {
    "type": "object",
    "properties": {
        "resumen": {
            "type": "string",
            "description": "Hallazgos principales sobre el tema: 4-6 frases con datos "
                           "concretos, cifras y fechas — no opiniones genéricas",
        },
        "puntos_clave": {
            "type": "array",
            "description": "3 a 5 datos/cifras/hechos concretos encontrados en la investigación",
            "items": {"type": "string"},
        },
        "angulos": {
            "type": "array",
            "description": "3 a 4 ángulos de contenido distintos posibles sobre este tema, "
                           "cada uno evaluado en 4 dimensiones independientes",
            "items": {
                "type": "object",
                "properties": {
                    "angulo": {
                        "type": "string",
                        "enum": ["Noticia pura", "Opinión", "Qué significa esto para ti",
                                 "Caso práctico", "Contrarian"],
                    },
                    "gancho": {"type": "string",
                              "description": "Hook concreto y específico para ese ángulo"},
                    "formato_sugerido": {"type": "string", "enum": ["video", "carrusel", "imagen"]},
                    "novedad": {"type": "integer", "description": "Qué tan nuevo/reciente es (1 a 10)"},
                    "prueba": {"type": "integer",
                              "description": "¿Hay dato/cifra/fuente verificable de la investigación "
                                             "que lo respalde? No opinión sin sustento (1 a 10)"},
                    "conflicto": {"type": "integer",
                                 "description": "¿Alguien pierde algo o cambia una creencia si esto "
                                                "es verdad? (1 a 10)"},
                    "accion": {"type": "integer",
                              "description": "¿El espectador puede hacer algo concreto hoy con esto? (1 a 10)"},
                    "justificacion": {"type": "string", "description": "Por qué esos puntajes, 1 frase"},
                },
                "required": ["angulo", "gancho", "formato_sugerido", "novedad", "prueba",
                            "conflicto", "accion", "justificacion"],
            },
        },
    },
    "required": ["resumen", "puntos_clave", "angulos"],
}


def _brand(perfil: str) -> dict:
    marcas = json.loads((BASE / "brand_config.json").read_text())
    return marcas.get(perfil, {})


def investigar(tema: str, perfil: str = "") -> dict:
    """Investiga `tema` a fondo y devuelve hallazgos + ángulos de contenido."""
    brand = _brand(perfil)
    contexto_audiencia = (
        f" La audiencia del contenido es: {brand['target_audience']}."
        if brand.get("target_audience") else ""
    )
    system = (
        "Eres un investigador digital que profundiza en temas puntuales para "
        "un creador de contenido de marketing digital, IA y ecommerce. Buscas "
        "información ACTUAL y verificable — cifras, fechas, fuentes concretas — "
        "no opiniones genéricas ni relleno. Después propones ángulos de "
        "contenido distintos entre sí, cada uno con su propio gancho listo "
        "para usar, y evalúas cada ángulo en 4 dimensiones independientes "
        "(Novedad/Prueba/Conflicto/Acción, 1 a 10). Sé exigente con Prueba: un "
        "ángulo sin dato o fuente verificable de tu propia investigación detrás "
        "no merece puntaje alto ahí, por más llamativo que sea el gancho."
        + contexto_audiencia
    )
    prompt = f"Investiga a fondo este tema para crear contenido de redes sociales: {tema}"
    resultado = llm_client.generar_json("investigacion", system, prompt, SCHEMA)
    resultado["resumen"] = _limpiar(resultado["resumen"])
    resultado["puntos_clave"] = [_limpiar(p) for p in resultado.get("puntos_clave", [])]

    angulos = []
    for angulo in resultado.get("angulos", []):
        if angulo["prueba"] < UMBRAL_PRUEBA:
            continue  # descartado: sin evidencia sólida, no importa el resto
        angulo["gancho"] = _limpiar(angulo["gancho"])
        angulo["puntajes"] = {k: angulo.pop(k) for k in ("novedad", "prueba", "conflicto", "accion")}
        angulos.append(angulo)
    angulos.sort(key=lambda a: sum(a["puntajes"].values()), reverse=True)
    resultado["angulos"] = angulos

    resultado["tema"] = tema
    return resultado


if __name__ == "__main__":
    import sys
    tema = " ".join(sys.argv[1:]) or "cómo funciona el algoritmo de TikTok Shop en 2026"
    print(json.dumps(investigar(tema), ensure_ascii=False, indent=2))
