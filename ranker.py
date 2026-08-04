"""
Ranker — Sprint 2 del Agente de Contenido de Andrés Duque.

Toma las noticias recolectadas por el News Fetcher y las ordena por
POTENCIAL DE CONTENIDO con una heurística local (sin IA, sin key, costo $0).

Cada noticia recibe:
  - score: entero de 1 a 5 (5 = mayor potencial de impacto)
  - motivo: explicación corta de por qué obtuvo ese puntaje

Los 5 temas pesan igual: el ranking mide qué tan "publicable" es la noticia,
no qué tema es. NO genera contenido todavía — solo rankea.

Uso:
  python3 news_fetcher.py > noticias.json
  python3 ranker.py noticias.json
  # o encadenado:
  python3 news_fetcher.py | python3 ranker.py
"""

import json
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Señales de la heurística
# ---------------------------------------------------------------------------

# Palabras que suelen indicar alto gancho para contenido (en título/resumen).
# Minúsculas y sin tildes: la comparación se hace normalizada.
# Afinadas al nicho de Andrés: ventas, ads, ecommerce e infoproductos.
HOOK_WORDS = {
    # Novedad / cambio (siempre generan contenido)
    "nuevo", "lanza", "lanzamiento", "gratis", "gratuito", "cambio", "cambia",
    "actualizacion", "update", "prohibe", "prohibicion", "ban", "cierra",
    "record", "viral", "tendencia", "crece", "cae", "millones", "billones",
    "alerta", "demanda", "multa", "adquiere", "compra", "fusion",
    # IA / herramientas
    "ia", "inteligencia artificial", "chatgpt", "gemini", "openai",
    "automatiza", "automatizacion", "algoritmo", "funcion", "feature",
    # Formato / valor accionable
    "guia", "como", "trucos", "tips", "error", "estrategia", "paso a paso",
    # Ventas / dinero (nicho Andrés)
    "vender", "ventas", "cerrar", "cierre", "escalar", "escala", "facturar",
    "ingresos", "rentable", "rentabilidad", "roas", "cac", "roi", "conversion",
    "leads", "embudo", "funnel", "monetizar", "monetizacion",
    # Ads
    "anuncios", "ads", "campana", "campanas", "creativo", "creativos",
    "segmentacion", "publico", "retargeting", "presupuesto", "puja",
    # Orgánico / creador
    "organico", "alcance", "engagement", "creador", "creadores", "audiencia",
    # Ecommerce / infoproductos
    "ecommerce", "tienda", "checkout", "carrito", "curso", "membresia",
    "lanzamiento de producto", "webinar", "email marketing", "infoproductos",
    # Prioridad del nicho indicada por Andrés
    "meta ads", "ventas por internet", "ventas online", "live", "lives",
    "ventas en lives", "en vivo", "directo", "tiktok", "innovacion",
}

# Cuánto suma cada señal al puntaje bruto (antes de mapear a 1-5).
W_FRESHNESS_TODAY = 2.0     # publicada hoy
W_FRESHNESS_2DAYS = 1.5     # <= 2 días
W_FRESHNESS_WEEK = 0.8      # <= 7 días
W_FRESHNESS_OLD = 0.2       # más vieja o sin fecha
W_HOOK_EACH = 0.6           # por cada palabra gancho encontrada (con tope)
MAX_HOOKS_COUNTED = 3       # tope de palabras gancho que suman
W_HAS_SUMMARY = 0.4         # tiene resumen real (no "(sin resumen)")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    return text.translate(tabla)


def normalize(text: str) -> str:
    return _strip_accents((text or "").lower())


def days_since(fecha_iso: str, today: datetime = None) -> int:
    """Días desde la fecha ISO (YYYY-MM-DD). None si no se puede parsear."""
    if not fecha_iso:
        return None
    try:
        d = datetime.strptime(fecha_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    today = today or datetime.now(timezone.utc)
    return (today.date() - d.date()).days


def freshness_points(dias):
    if dias is None:
        return W_FRESHNESS_OLD, "sin fecha"
    if dias <= 0:
        return W_FRESHNESS_TODAY, "de hoy"
    if dias <= 2:
        return W_FRESHNESS_2DAYS, f"reciente ({dias}d)"
    if dias <= 7:
        return W_FRESHNESS_WEEK, f"de esta semana ({dias}d)"
    return W_FRESHNESS_OLD, f"antigua ({dias}d)"


def count_hooks(texto_norm: str) -> list:
    """Lista de palabras gancho presentes (sin repetir), respetando el tope."""
    encontradas = []
    for palabra in HOOK_WORDS:
        if palabra in texto_norm and palabra not in encontradas:
            encontradas.append(palabra)
        if len(encontradas) >= MAX_HOOKS_COUNTED:
            break
    return encontradas


# ---------------------------------------------------------------------------
# Puntaje
# ---------------------------------------------------------------------------

def raw_to_scale(raw: float) -> int:
    """Mapea el puntaje bruto (~0.2 a ~4.2) a una escala entera de 1 a 5."""
    if raw >= 3.4:
        return 5
    if raw >= 2.6:
        return 4
    if raw >= 1.8:
        return 3
    if raw >= 1.0:
        return 2
    return 1


def score_news(noticia: dict, today: datetime = None) -> dict:
    """Devuelve una copia de la noticia con 'score' (1-5) y 'motivo'."""
    texto = normalize(f"{noticia.get('titulo', '')} {noticia.get('resumen', '')}")

    dias = days_since(noticia.get("fecha", ""), today)
    f_pts, f_txt = freshness_points(dias)

    hooks = count_hooks(texto)
    h_pts = len(hooks) * W_HOOK_EACH

    tiene_resumen = noticia.get("resumen", "") not in ("", "(sin resumen)")
    s_pts = W_HAS_SUMMARY if tiene_resumen else 0.0

    raw = f_pts + h_pts + s_pts
    score = raw_to_scale(raw)

    partes = [f_txt]
    if hooks:
        partes.append("ganchos: " + ", ".join(hooks))
    if tiene_resumen:
        partes.append("con resumen")
    motivo = "; ".join(partes)

    resultado = dict(noticia)
    resultado["score"] = score
    resultado["motivo"] = motivo
    return resultado


def rank(noticias: list, today: datetime = None) -> list:
    """Devuelve las noticias con score, ordenadas de mayor a menor potencial."""
    puntuadas = [score_news(n, today) for n in noticias]
    # Desempate: mayor score, luego más reciente (menos días).
    puntuadas.sort(
        key=lambda n: (
            n["score"],
            -(days_since(n.get("fecha", ""), today) or 999),
        ),
        reverse=True,
    )
    return puntuadas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_input(argv) -> list:
    """Lee el JSON desde un archivo (argv[1]) o desde stdin si está encadenado."""
    if len(argv) > 1:
        with open(argv[1], "r", encoding="utf-8") as f:
            return json.load(f)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    print(
        "Uso: python3 ranker.py noticias.json  (o encadenado con news_fetcher.py)",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    noticias = _load_input(sys.argv)
    ordenadas = rank(noticias)

    print(f"Rankeadas {len(ordenadas)} noticias (5 = mayor potencial)\n", file=sys.stderr)
    for i, n in enumerate(ordenadas, 1):
        print(f"  {i:>2}. [{n['score']}] {n['titulo'][:70]}", file=sys.stderr)
    print("", file=sys.stderr)

    print(json.dumps(ordenadas, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
