"""
News Fetcher — Sprint 1 del Agente de Contenido de Andrés Duque.

Recolecta noticias/información reciente en 5 temas usando RSS de Google News
(sin API key, sin servidor, costo $0) y las devuelve estructuradas en JSON.

NO rankea ni genera contenido: solo recolecta y estructura.
"""

import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote_plus

import feedparser

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Cada tema mapea a una consulta de búsqueda que se envía a Google News.
TOPICS = {
    "IA y automatizaciones": "inteligencia artificial automatizacion empresas",
    "Meta Ads": "Meta Ads Facebook Instagram publicidad",
    "TikTok Ads": "TikTok Ads publicidad marketing",
    "Ecommerce": "ecommerce comercio electronico tendencias",
    "Infoproductos": "infoproductos cursos online creadores negocio digital",
}

# Cuántas noticias pedir por tema. 5 temas x 3-4 = 15-20 objetivo.
PER_TOPIC = 4

# Google News RSS. hl=idioma, gl=pais, ceid=pais:idioma.
GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=es-419&gl=US&ceid=US:es-419"
)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

# Símbolos decorativos que a veces meten los títulos de YouTube/redes.
_DECORATIVE_SYMBOLS = re.compile(r"[📣►▶️🔥✅⚡️🚀💥🎯]+")
# Código de video de YouTube al final del título, ej. "... (D9MPcACAKF)".
_TRAILING_VIDEO_CODE = re.compile(r"\s*\([A-Za-z0-9_-]{8,15}\)\s*$")


def clean_text(raw: str) -> str:
    """Quita etiquetas HTML, símbolos decorativos y normaliza espacios."""
    if not raw:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", raw)
    sin_simbolos = _DECORATIVE_SYMBOLS.sub("", unescape(no_tags))
    sin_codigo = _TRAILING_VIDEO_CODE.sub("", sin_simbolos)
    return re.sub(r"\s+", " ", sin_codigo).strip()


def parse_date(entry) -> str:
    """Devuelve la fecha en ISO (YYYY-MM-DD) o cadena vacía si no existe."""
    parsed = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
    return ""


def extract_source(entry) -> str:
    """Obtiene la fuente del feed; Google News la incluye en 'source'."""
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return source.title
    # Fallback: Google News pone " - Fuente" al final del título.
    title = getattr(entry, "title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Desconocida"


def clean_title(entry) -> str:
    """Quita el sufijo ' - Fuente' que Google News agrega al título."""
    title = clean_text(getattr(entry, "title", ""))
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title


# ---------------------------------------------------------------------------
# Recolección
# ---------------------------------------------------------------------------

def fetch_topic(topic: str, query: str, limit: int = PER_TOPIC) -> list:
    """Descarga y estructura las noticias de un tema."""
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
    feed = feedparser.parse(url)

    items = []
    for entry in feed.entries[:limit]:
        title = clean_title(entry)
        link = getattr(entry, "link", "")

        rss_summary = clean_text(getattr(entry, "summary", ""))
        resumen = rss_summary if rss_summary and rss_summary != title else ""

        items.append(
            {
                "titulo": title,
                "resumen": resumen[:280] if resumen else "(sin resumen)",
                "fuente": extract_source(entry),
                "fecha": parse_date(entry),
                "tema": topic,
                "url": link,
            }
        )
    return items


def fetch_all() -> list:
    """Recolecta noticias de los 5 temas."""
    noticias = []
    for topic, query in TOPICS.items():
        encontradas = fetch_topic(topic, query)
        print(f"  · {topic}: {len(encontradas)} noticias", file=sys.stderr)
        noticias.extend(encontradas)
    return noticias


def main() -> None:
    print("Recolectando noticias (Google News RSS)...", file=sys.stderr)
    noticias = fetch_all()
    print(f"\nTotal recolectadas: {len(noticias)}\n", file=sys.stderr)
    # JSON limpio a stdout — separado de los mensajes de progreso (stderr).
    print(json.dumps(noticias, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
