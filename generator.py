"""
Generator — Sprint 3 del Agente de Contenido de Andrés Duque.

Toma las noticias YA rankeadas y arma un BRIEF por cada una de las top N
(default: 5) con una plantilla estructurada (sin IA, sin key, costo $0).

Ideas clave del brief:
  - formato: video | carrusel | imagen  (se detecta según la noticia)
  - intencion: informativo | accionable
        · informativo = solo aporta valor / dato / contexto, SIN CTA forzado
        · accionable  = invita a hacer algo (probar, aplicar, escribir), con CTA
  - El CTA solo aparece cuando la intención es accionable. No se fuerza.

NO escribe el guion final ni publica: entrega el ANDAMIAJE para grabar/montar.

Uso:
  python3 news_fetcher.py | python3 ranker.py | python3 generator.py
  python3 generator.py rankeadas.json --top 5
"""

import json
import sys

TOP_N = 5

# ---------------------------------------------------------------------------
# Detección de formato e intención
# ---------------------------------------------------------------------------

# Señales que sugieren cada formato de contenido.
VIDEO_HINTS = {"tutorial", "como", "guia", "paso", "trucos", "explica",
               "aprende", "estrategia", "estrategias"}
CARRUSEL_HINTS = {"tendencias", "tips", "razones", "claves", "lista", "top",
                  "mejores", "formas", "maneras", "errores"}
IMAGEN_HINTS = {"lanza", "lanzamiento", "nuevo", "anuncia", "record", "cifra",
                "dato", "alerta", "prohibe", "multa"}

# Señales de que el contenido invita a la acción (vs solo informar).
ACCIONABLE_HINTS = {"como", "guia", "tutorial", "aprende", "aplica", "prueba",
                    "estrategia", "estrategias", "trucos", "tips", "pasos",
                    "gratis", "descarga", "empieza"}


def _norm(text: str) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    return (text or "").lower().translate(tabla)


def _score_hints(texto_norm: str, hints: set) -> int:
    return sum(1 for h in hints if h in texto_norm)


def detectar_formato(noticia: dict) -> str:
    texto = _norm(f"{noticia.get('titulo', '')} {noticia.get('resumen', '')}")
    puntajes = {
        "video": _score_hints(texto, VIDEO_HINTS),
        "carrusel": _score_hints(texto, CARRUSEL_HINTS),
        "imagen": _score_hints(texto, IMAGEN_HINTS),
    }
    mejor = max(puntajes, key=puntajes.get)
    # Sin señales claras -> carrusel (formato versátil por defecto).
    return mejor if puntajes[mejor] > 0 else "carrusel"


def detectar_intencion(noticia: dict) -> str:
    texto = _norm(f"{noticia.get('titulo', '')} {noticia.get('resumen', '')}")
    return "accionable" if _score_hints(texto, ACCIONABLE_HINTS) > 0 else "informativo"


# ---------------------------------------------------------------------------
# Plantillas por formato
# ---------------------------------------------------------------------------

def _hook(noticia: dict) -> str:
    """Gancho de apertura sugerido a partir del titular."""
    return f"¿Ya viste esto? {noticia.get('titulo', '').strip()}"


def _cta(noticia: dict, intencion: str) -> str:
    """CTA solo si la intención es accionable; si no, cadena vacía."""
    if intencion != "accionable":
        return ""
    return "Guarda este contenido y aplícalo esta semana."


def _puntos_clave(noticia: dict) -> list:
    resumen = noticia.get("resumen", "")
    if resumen and resumen != "(sin resumen)":
        base = resumen
    else:
        base = noticia.get("titulo", "")
    return [
        f"Qué pasó: {base}",
        "Por qué importa para tu negocio (conéctalo con tu audiencia).",
        "Tu opinión/experiencia: qué harías o qué ya viste tú.",
    ]


def construir_brief(noticia: dict) -> dict:
    formato = detectar_formato(noticia)
    intencion = detectar_intencion(noticia)
    cta = _cta(noticia, intencion)

    brief = {
        "titulo_fuente": noticia.get("titulo", ""),
        "tema": noticia.get("tema", ""),
        "fuente": noticia.get("fuente", ""),
        "url": noticia.get("url", ""),
        "score": noticia.get("score"),
        "formato": formato,
        "intencion": intencion,
        "gancho": _hook(noticia),
        "puntos_clave": _puntos_clave(noticia),
        "cta": cta,  # vacío si es informativo
    }

    # Detalle específico por formato (el "molde" para montar).
    if formato == "carrusel":
        brief["sugerencia_slides"] = [
            "Portada: el gancho, texto grande.",
            *[f"Slide: {p}" for p in brief["puntos_clave"]],
            "Cierre: idea final" + (f" + CTA: {cta}" if cta else " (sin CTA, cierra con reflexión)."),
        ]
    elif formato == "video":
        brief["estructura_video"] = [
            "0-3s: gancho hablado (retén la atención).",
            "3-20s: desarrollo de los puntos clave.",
            "cierre: " + (cta if cta else "conclusión / dato que deje pensando."),
        ]
    else:  # imagen
        brief["sugerencia_imagen"] = {
            "texto_principal": noticia.get("titulo", ""),
            "texto_apoyo": "1 frase de contexto o dato clave.",
            "pie": cta if cta else "Fuente: " + noticia.get("fuente", ""),
        }

    return brief


def generar(noticias: list, top: int = TOP_N) -> list:
    """Genera briefs para las primeras `top` noticias (ya vienen rankeadas)."""
    return [construir_brief(n) for n in noticias[:top]]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv):
    ruta, top = None, TOP_N
    i = 1
    while i < len(argv):
        if argv[i] == "--top" and i + 1 < len(argv):
            top = int(argv[i + 1])
            i += 2
        else:
            ruta = argv[i]
            i += 1
    return ruta, top


def _load_input(ruta) -> list:
    if ruta:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    print("Uso: python3 generator.py rankeadas.json [--top 5]", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    ruta, top = _parse_args(sys.argv)
    noticias = _load_input(ruta)
    briefs = generar(noticias, top)

    print(f"Generados {len(briefs)} briefs (top {top})\n", file=sys.stderr)
    for i, b in enumerate(briefs, 1):
        cta_txt = b["cta"] if b["cta"] else "(sin CTA — informativo)"
        print(f"  {i}. [{b['formato']}/{b['intencion']}] {b['titulo_fuente'][:60]}",
              file=sys.stderr)
        print(f"     CTA: {cta_txt}", file=sys.stderr)
    print("", file=sys.stderr)

    print(json.dumps(briefs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
