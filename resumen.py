"""
Resumen — Agente de Contenido.

Al expandir una noticia en el dashboard, trae el artículo real (si el sitio
lo permite) y lo resume en 3-4 frases informativas con Gemini, para que el
usuario decida si le interesa sin salir del dashboard. Cachea en memoria
por URL para no repetir la llamada.
"""

from pathlib import Path

import requests
from bs4 import BeautifulSoup

import llm_client
import ranker_ia  # carga .env

BASE = Path(__file__).resolve().parent

SCHEMA = {
    "type": "object",
    "properties": {"resumen": {"type": "string"}},
    "required": ["resumen"],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

SYSTEM = (
    "Resumes noticias en español latino de forma clara e informativa, para que "
    "el lector decida si le interesa profundizar antes de abrir el enlace. "
    "3 a 4 frases, directo a los hechos y datos concretos, sin opinar ni usar "
    "clickbait. No repitas el titular literalmente."
)

_cache: dict = {}


def _extraer_texto(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    return " ".join(p for p in parrafos if len(p) > 40)[:6000]


def _resumir_con_ia(titulo: str, contenido: str) -> str:
    prompt = f"Titular: {titulo}\n\nContenido disponible:\n{contenido}"
    resultado = llm_client.generar_json("resumen", SYSTEM, prompt, SCHEMA)
    return resultado["resumen"].strip()


def obtener_resumen(url: str, titulo: str, contexto: str = "") -> dict:
    """Devuelve {"resumen": str, "fuente": "articulo"|"contexto"}. Cachea por URL."""
    if url in _cache:
        return _cache[url]

    try:
        texto = _extraer_texto(url)
        fuente = "articulo" if len(texto) >= 200 else "contexto"
    except Exception:
        texto, fuente = "", "contexto"

    contenido = texto if fuente == "articulo" else (contexto or titulo)
    resumen = _resumir_con_ia(titulo, contenido)
    resultado = {"resumen": resumen, "fuente": fuente}
    _cache[url] = resultado
    return resultado
