"""
Image Producer — Sprint 3 del Agente de Contenido.

Renderiza imágenes estáticas y carruseles con HTML/CSS + Playwright headless,
100% fiel al branding de brand_config.json. Sin IA generativa: cero texto
alucinado, costo $0.

Formato: los carruseles SIEMPRE son cuadrados (1080x1080) — es el estándar
para posts de feed. Las imágenes sueltas eligen entre cuadrado (1080x1080) o
vertical (1080x1350, 4:5) vía `formato_imagen`.

Cada lámina de carrusel tiene un ROL (hook/obstaculo/desarrollo/resultado/cta)
y un tratamiento visual distinto — nada de la misma plantilla repetida. Ver
BEAT_STYLE para el diseño de cada una.
"""

import base64
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
OUT = BASE / "producciones"

DIMENSIONES = {
    "cuadrado": (1080, 1080),
    "vertical": (1080, 1350),
    "historia": (1080, 1920),  # 9:16 — Stories/Estados, distinto del vertical de feed
}
DIMENSION_CARRUSEL = (1080, 1080)  # siempre cuadrado, sin excepción

TIPO_LABEL = {"video": "NUEVO VIDEO", "carrusel": "NUEVO CARRUSEL", "imagen": "NUEVO POST"}

# Cada rol define: kicker (etiqueta editorial), tipo de fondo, tamaño de
# título y si el cuerpo se muestra como "pill" (estilo botón, para CTA).
BEAT_STYLE = {
    "hook": {"kicker": None, "fondo": "hook", "titulo_grande": True, "pill": False},
    "obstaculo": {"kicker": "EL PROBLEMA", "fondo": "obstaculo", "titulo_grande": False, "pill": False},
    "desarrollo": {"kicker": "PASO", "fondo": "desarrollo", "titulo_grande": False, "pill": False},
    "resultado": {"kicker": "EL RESULTADO", "fondo": "resultado", "titulo_grande": False, "pill": False},
    "cta": {"kicker": None, "fondo": "cta", "titulo_grande": True, "pill": True},
}

# blobs decorativos (radial-gradient) para dar profundidad — nada de fondo plano.
FONDOS = {
    "hook": (
        "background: linear-gradient(155deg, {primary} 0%, {secondary} 100%);"
        "background-image: radial-gradient(circle at 85% 12%, {accent}55 0%, transparent 42%),"
        "linear-gradient(155deg, {primary} 0%, {secondary} 100%);"
    ),
    "obstaculo": (
        "background: {secondary};"
        "background-image: radial-gradient(circle at 8% 90%, {primary}70 0%, transparent 50%),"
        "linear-gradient(0deg, {secondary} 0%, {secondary} 100%);"
        "border-top: 14px solid {accent};"
    ),
    "desarrollo": (
        "background: linear-gradient(160deg, {primary} 0%, {secondary} 100%);"
        "background-image: radial-gradient(circle at 90% 85%, {accent}40 0%, transparent 45%),"
        "linear-gradient(160deg, {primary} 0%, {secondary} 100%);"
    ),
    "resultado": (
        "background: {primary};"
        "background-image: radial-gradient(circle at 15% 10%, {accent}60 0%, transparent 45%),"
        "linear-gradient(0deg, {primary} 0%, {primary} 100%);"
    ),
    "cta": (
        "background: linear-gradient(135deg, {accent} 0%, {primary} 100%);"
        "background-image: radial-gradient(circle at 10% 95%, {secondary}50 0%, transparent 50%),"
        "linear-gradient(135deg, {accent} 0%, {primary} 100%);"
    ),
}

PLANTILLA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  {fondo_css}
  color: #fff; display: flex; flex-direction: column;
  justify-content: space-between; padding: 90px; position: relative; overflow: hidden;
}}
.paso-badge {{
  position: absolute; top: 90px; right: 90px;
  width: 96px; height: 96px; border-radius: 50%;
  background: {accent}; color: #0b0b0f;
  display: flex; align-items: center; justify-content: center;
  font-size: 40px; font-weight: 800;
}}
.kicker {{ font-size: 32px; font-weight: 700; letter-spacing: 4px;
  text-transform: uppercase; color: {accent}; }}
h1 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.12; }}
.body {{ font-size: 42px; line-height: 1.45; opacity: .94; }}
.pill {{
  display: inline-block; background: #fff; color: {primary};
  padding: 26px 44px; border-radius: 100px; font-size: 40px; font-weight: 800;
  box-shadow: 0 12px 32px rgba(0,0,0,.25);
}}
.flecha {{ margin-left: 14px; font-weight: 900; }}
.footer {{ display: flex; align-items: center; justify-content: space-between; }}
.brand {{ display: flex; align-items: center; gap: 24px; }}
.brand img {{ height: 100px; }}
.brand span {{ font-size: 34px; font-weight: 600; }}
.paginador {{ font-size: 30px; font-weight: 700; opacity: .7; }}
</style></head><body>
{paso_badge}
<div class="kicker">{kicker}</div>
<div>
  <h1>{titulo}</h1>
  <div style="height:36px"></div>
  {cuerpo_html}
</div>
<div class="footer">
  <div class="brand">{logo_html}<span>{brand_name}</span></div>
  <div class="paginador">{paginador}</div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Skin "prensa_ia" — carrusel tipo prensa/newsletter (portada con badge y firma
# de autoridad, láminas numeradas sobre fondo oscuro, cierre con CTA en caja
# de acento). Tinta y papel quedan fijos — es la identidad del skin — el único
# color que cambia por marca es el acento (brand['accent_color']), igual que
# ya sucede con el skin "editorial".
# ---------------------------------------------------------------------------
ESTILOS_VISUALES = ("editorial", "prensa_ia", "listicle", "ilustracion", "sketch",
                    "mockup_telefono", "brutalista", "premium")

PRENSA_INK = "#141414"
PRENSA_PAPER = "#F8F5EF"
PRENSA_MUTED = "#6B6A63"
PRENSA_LINE = "#E4DFD2"
PRENSA_DARK_BG = "#0E0E0E"
PRENSA_DARK_LINE = "#333333"
PRENSA_DARK_MUTED = "#8C8A80"

PRENSA_KICKER = {"hook": "NOVEDADES", "obstaculo": "EL PROBLEMA", "resultado": "EL RESULTADO"}

_PRENSA_PORTADA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {paper}; color: {ink};
  display: flex; flex-direction: column;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
.badge {{
  align-self: flex-start; background: {accent}; color: {ink};
  font-size: 26px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase;
  padding: 14px 28px; margin-bottom: 44px;
}}
.paginador {{ position: absolute; top: 100px; right: 90px; font-size: 28px; font-weight: 700; color: {muted}; }}
h1 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.12; letter-spacing: -1px; margin-bottom: 32px; }}
.body {{ font-size: 38px; line-height: 1.5; color: #3d3b34; flex: 1; }}
.byline {{
  margin-top: auto; border-top: 2px solid {line}; padding-top: 28px;
  display: flex; align-items: center; gap: 20px; font-size: 28px; color: {muted};
}}
.byline .dot {{ width: 56px; height: 56px; border-radius: 50%; background: {ink}; flex: none; }}
.byline b {{ color: {ink}; font-weight: 700; }}
</style></head><body>
<div class="paginador">{paginador}</div>
<div class="badge">{kicker}</div>
<h1>{titulo}</h1>
<div class="body">{cuerpo}</div>
<div class="byline"><span class="dot"></span><span>{brand_name}</span></div>
</body></html>"""

_PRENSA_CONTENIDO = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {dark_bg}; color: #fff;
  display: flex; flex-direction: column;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
.kicker {{ font-size: 30px; font-weight: 800; letter-spacing: 4px; text-transform: uppercase;
  color: {accent}; margin-bottom: 24px; }}
h2 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.18; letter-spacing: -1px; margin-bottom: 28px; }}
.body {{ font-size: 36px; line-height: 1.5; color: #B8B6AC; flex: 1; }}
.footer {{ display: flex; align-items: center; justify-content: space-between;
  border-top: 2px solid {dark_line}; padding-top: 28px; font-size: 26px; color: {dark_muted}; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h2>{titulo}</h2>
<div class="body">{cuerpo}</div>
<div class="footer"><span>{brand_name}</span><span>{paginador}</span></div>
</body></html>"""

_PRENSA_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {paper}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
h1 {{ font-size: 62px; font-weight: 800; line-height: 1.2; letter-spacing: -1px; margin-bottom: 40px; }}
.cta-box {{ background: {accent}; color: {ink}; padding: 40px 44px; font-size: 38px;
  line-height: 1.45; font-weight: 600; }}
.brand {{ margin-top: 40px; font-size: 26px; color: {muted}; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_PRENSA_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {paper}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.badge {{ align-self: flex-start; background: {accent}; color: {ink}; font-size: 26px; font-weight: 800;
  letter-spacing: 3px; text-transform: uppercase; padding: 14px 28px; margin-bottom: 48px; }}
h1 {{ font-size: 74px; font-weight: 800; line-height: 1.15; letter-spacing: -1px; margin-bottom: 56px; }}
.pill {{ display: inline-block; background: {accent}; color: {ink}; padding: 28px 46px;
  border-radius: 100px; font-size: 38px; font-weight: 800; align-self: flex-start; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="badge">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_prensa(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                       paginador: str, paso_actual: int, paso_total: int) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _PRENSA_CTA.format(
            w=w, h=h, paper=PRENSA_PAPER, ink=PRENSA_INK, accent=accent, muted=PRENSA_MUTED,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    if rol == "hook":
        h1_size = 78 if len(titulo) <= 60 else 62
        return _PRENSA_PORTADA.format(
            w=w, h=h, paper=PRENSA_PAPER, ink=PRENSA_INK, accent=accent, muted=PRENSA_MUTED,
            line=PRENSA_LINE, kicker=PRENSA_KICKER["hook"], titulo=titulo, cuerpo=cuerpo,
            h1_size=h1_size, brand_name=brand["brand_name"], paginador=paginador,
        )
    # obstaculo / desarrollo / resultado
    kicker = PRENSA_KICKER.get(rol, "PASO")
    if rol == "desarrollo" and paso_total:
        kicker = f"PASO {paso_actual} DE {paso_total}"
    h1_size = 58 if len(titulo) <= 60 else 46
    return _PRENSA_CONTENIDO.format(
        w=w, h=h, dark_bg=PRENSA_DARK_BG, accent=accent, dark_line=PRENSA_DARK_LINE,
        dark_muted=PRENSA_DARK_MUTED, kicker=kicker, titulo=titulo, h1_size=h1_size,
        cuerpo=cuerpo, brand_name=brand["brand_name"], paginador=paginador,
    )


# ---------------------------------------------------------------------------
# Skin "listicle" — carrusel numerado 100% fondo negro (identidad de un solo
# tono, a diferencia de "prensa_ia" que alterna papel/oscuro): número grande
# de acento por lámina, footer con puntos de progreso + "DESLIZA PARA VER".
# ---------------------------------------------------------------------------
LISTICLE_BG = "#0B0B0C"
LISTICLE_FG = "#FFFFFF"
LISTICLE_MUTED = "#8A8A8F"
LISTICLE_LINE = "#232326"

LISTICLE_KICKER = {"hook": "GUÍA RÁPIDA", "obstaculo": "EL PROBLEMA", "resultado": "EL RESULTADO"}


def _listicle_dots(paginador: str, accent: str) -> str:
    """paginador viene como "i/N" — arma N puntitos, el i-ésimo en color de acento."""
    try:
        actual, total = (int(x) for x in paginador.split("/"))
    except (ValueError, AttributeError):
        return ""
    puntos = "".join(
        f'<span class="dot{" activo" if i == actual else ""}"></span>' for i in range(1, total + 1)
    )
    return f'<div class="dots" style="--accent:{accent}">{puntos}</div>'


_LISTICLE_PORTADA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
.kicker {{ font-size: 28px; font-weight: 800; letter-spacing: 4px; text-transform: uppercase;
  color: {accent}; margin-bottom: 40px; }}
h1 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.14; letter-spacing: -1px; }}
.body {{ font-size: 38px; line-height: 1.5; color: {muted}; margin-top: 32px; }}
.footer {{ margin-top: auto; display: flex; align-items: center; justify-content: space-between; }}
.swipe {{ font-size: 30px; font-weight: 700; color: {accent}; }}
.dots {{ display: flex; gap: 12px; }}
.dot {{ width: 14px; height: 14px; border-radius: 50%; background: {line}; }}
.dot.activo {{ background: var(--accent); width: 34px; border-radius: 8px; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="body">{cuerpo}</div>
<div class="footer">
  <span class="swipe">{swipe_texto}</span>
  {dots}
</div>
</body></html>"""

_LISTICLE_CONTENIDO = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
.numero {{ font-size: 140px; font-weight: 800; color: {accent}; line-height: 1; margin-bottom: 8px; }}
h2 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.16; letter-spacing: -1px;
  text-transform: uppercase; margin-bottom: 28px; }}
.body {{ font-size: 38px; line-height: 1.5; color: {muted}; flex: 1; }}
.footer {{ margin-top: auto; border-top: 2px solid {line}; padding-top: 28px;
  display: flex; align-items: center; justify-content: space-between; }}
.swipe {{ font-size: 28px; font-weight: 700; color: {muted}; }}
.dots {{ display: flex; gap: 12px; }}
.dot {{ width: 14px; height: 14px; border-radius: 50%; background: {line}; }}
.dot.activo {{ background: var(--accent); width: 34px; border-radius: 8px; }}
</style></head><body>
<div class="numero">{numero}.</div>
<h2>{titulo}</h2>
<div class="body">{cuerpo}</div>
<div class="footer">
  <span class="swipe">{swipe_texto}</span>
  {dots}
</div>
</body></html>"""

_LISTICLE_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
h1 {{ font-size: 66px; font-weight: 800; line-height: 1.18; letter-spacing: -1px; margin-bottom: 44px; }}
.cta-box {{ background: {accent}; color: {bg}; padding: 40px 44px; font-size: 38px;
  line-height: 1.4; font-weight: 800; }}
.brand {{ margin-top: 48px; font-size: 26px; color: {muted}; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_LISTICLE_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.kicker {{ font-size: 26px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase;
  color: {accent}; margin-bottom: 48px; }}
h1 {{ font-size: 74px; font-weight: 800; line-height: 1.15; letter-spacing: -1px; margin-bottom: 56px; }}
.pill {{ display: inline-block; background: {accent}; color: {bg}; padding: 28px 46px;
  border-radius: 100px; font-size: 38px; font-weight: 800; align-self: flex-start; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_listicle(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                         paginador: str, paso_actual: int, paso_total: int) -> str:
    accent = brand["accent_color"]
    dots = _listicle_dots(paginador, accent)
    if rol == "cta":
        return _LISTICLE_CTA.format(
            w=w, h=h, bg=LISTICLE_BG, fg=LISTICLE_FG, accent=accent, muted=LISTICLE_MUTED,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    if rol == "hook":
        h1_size = 82 if len(titulo) <= 60 else 64
        # el hint de swipe solo aplica si esto es parte de un carrusel real
        # (paginador viene con "i/N"); una imagen suelta no tiene nada más
        # que deslizar.
        swipe_texto = "DESLIZA PARA VER →" if paginador else ""
        return _LISTICLE_PORTADA.format(
            w=w, h=h, bg=LISTICLE_BG, fg=LISTICLE_FG, accent=accent, muted=LISTICLE_MUTED,
            line=LISTICLE_LINE, kicker=LISTICLE_KICKER["hook"], titulo=titulo, cuerpo=cuerpo,
            h1_size=h1_size, dots=dots, swipe_texto=swipe_texto,
        )
    # obstaculo / desarrollo / resultado — todos numerados en esta identidad,
    # con el número de orden real de la lámina (más simple y siempre correcto
    # que tratar de inferir un conteo separado por rol).
    actual, total = paginador.split("/") if "/" in paginador else ("1", "1")
    numero = actual
    swipe_texto = "" if actual == total else "DESLIZA PARA VER →"
    h1_size = 56 if len(titulo) <= 50 else 44
    return _LISTICLE_CONTENIDO.format(
        w=w, h=h, bg=LISTICLE_BG, fg=LISTICLE_FG, accent=accent, muted=LISTICLE_MUTED,
        line=LISTICLE_LINE, numero=numero, titulo=titulo, h1_size=h1_size, cuerpo=cuerpo,
        swipe_texto=swipe_texto, dots=dots,
    )


# ---------------------------------------------------------------------------
# Skin "ilustracion" — fondo pastel sólido, muy minimalista (casi sin
# bullets), con una ilustración editorial abstracta (pedestales/columnas
# ascendentes, tipo iconografía de producto) en vez de bullets o gráficos.
# ---------------------------------------------------------------------------
ILUSTRACION_BG = "#F4E3D7"
ILUSTRACION_INK = "#1E1B18"
ILUSTRACION_MUTED = "#7A7168"


def _ilustracion_pedestales(accent: str, n: int = 3) -> str:
    """Ilustración abstracta: N columnas de altura ascendente — evoca los
    pedestales/iconos de producto del patrón de referencia, sin depender de
    ningún asset externo."""
    alturas = [140, 200, 260][:n] if n <= 3 else [140 + i * (160 // n) for i in range(n)]
    columnas = "".join(
        f'<div class="columna" style="height:{alt}px"></div>' for alt in alturas
    )
    return f'<div class="pedestales" style="--accent:{accent}">{columnas}</div>'


_ILUSTRACION_SLIDE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
h1 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.14; letter-spacing: -1px; }}
.body {{ font-size: 36px; line-height: 1.5; color: {muted}; margin-top: 28px; max-width: 780px; }}
.pedestales {{ display: flex; align-items: flex-end; gap: 28px; margin-top: 64px; }}
.columna {{ width: 90px; background: var(--accent); border-radius: 18px 18px 0 0; }}
.paginador {{ position: absolute; top: 90px; right: 90px; font-size: 26px; font-weight: 700; color: {muted}; }}
</style></head><body>
<div class="paginador">{paginador}</div>
<h1>{titulo}</h1>
{cuerpo_html}
{pedestales}
</body></html>"""

_ILUSTRACION_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {ink}; color: {bg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px;
}}
h1 {{ font-size: 60px; font-weight: 800; line-height: 1.2; letter-spacing: -1px; margin-bottom: 40px; }}
.cta-box {{ background: {accent}; color: {ink}; padding: 40px 44px; font-size: 38px;
  line-height: 1.4; font-weight: 700; }}
.brand {{ margin-top: 40px; font-size: 26px; opacity: .65; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_ILUSTRACION_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.kicker {{ font-size: 26px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase;
  color: {muted}; margin-bottom: 48px; }}
h1 {{ font-size: 74px; font-weight: 800; line-height: 1.15; letter-spacing: -1px; margin-bottom: 56px; }}
.pill {{ display: inline-block; background: {accent}; color: {ink}; padding: 28px 46px;
  border-radius: 100px; font-size: 38px; font-weight: 800; align-self: flex-start; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_ilustracion(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                            paginador: str) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _ILUSTRACION_CTA.format(
            w=w, h=h, bg=ILUSTRACION_BG, ink=ILUSTRACION_INK, accent=accent,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    h1_size = 76 if len(titulo) <= 50 else 58
    cuerpo_html = f'<div class="body">{cuerpo}</div>' if cuerpo else ""
    # el hook no lleva pedestales (portada minimalista, casi sin elementos);
    # el resto de los roles sí, como firma visual del skin.
    pedestales = "" if rol == "hook" else _ilustracion_pedestales(accent)
    return _ILUSTRACION_SLIDE.format(
        w=w, h=h, bg=ILUSTRACION_BG, ink=ILUSTRACION_INK, muted=ILUSTRACION_MUTED,
        h1_size=h1_size, titulo=titulo, cuerpo_html=cuerpo_html, pedestales=pedestales,
        paginador=paginador,
    )


# ---------------------------------------------------------------------------
# Skin "sketch" — fondo blanco, tipografía editorial enorme, con una
# ilustración lineal tipo boceto a mano (SVG con trazo irregular) de un
# camino con bifurcaciones — variante más artística/"premium".
# ---------------------------------------------------------------------------
SKETCH_BG = "#FDFCFA"
SKETCH_INK = "#111111"
SKETCH_MUTED = "#767267"

_SKETCH_CAMINO_SVG = """<svg width="440" height="220" viewBox="0 0 440 220" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M20 210 C 90 150, 100 130, 140 110 C 170 95, 150 60, 190 30" stroke="{ink}" stroke-width="4" stroke-linecap="round" fill="none"/>
<path d="M140 110 C 190 130, 230 150, 260 205" stroke="{ink}" stroke-width="4" stroke-linecap="round" fill="none"/>
<path d="M140 110 C 160 95, 260 80, 420 40" stroke="{accent}" stroke-width="5" stroke-linecap="round" fill="none"/>
<circle cx="20" cy="210" r="8" fill="{ink}"/>
<circle cx="140" cy="110" r="9" fill="{ink}"/>
<circle cx="420" cy="40" r="10" fill="{accent}"/>
</svg>"""

_SKETCH_SLIDE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: Georgia, 'Times New Roman', serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px; position: relative; overflow: hidden;
}}
h1 {{ font-size: {h1_size}px; font-weight: 700; line-height: 1.16; letter-spacing: -0.5px; }}
.body {{ font-family: -apple-system, sans-serif; font-size: 34px; line-height: 1.55;
  color: {muted}; margin-top: 28px; max-width: 780px; }}
.ilustracion {{ margin-top: 56px; }}
.paginador {{ position: absolute; top: 90px; right: 90px; font-family: -apple-system, sans-serif;
  font-size: 26px; font-weight: 700; color: {muted}; }}
</style></head><body>
<div class="paginador">{paginador}</div>
<h1>{titulo}</h1>
{cuerpo_html}
{ilustracion}
</body></html>"""

_SKETCH_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: Georgia, 'Times New Roman', serif;
  background: {ink}; color: {bg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px;
}}
h1 {{ font-size: 58px; font-weight: 700; line-height: 1.22; margin-bottom: 40px; }}
.cta-box {{ font-family: -apple-system, sans-serif; background: {accent}; color: {ink};
  padding: 40px 44px; font-size: 36px; line-height: 1.4; font-weight: 700; }}
.brand {{ font-family: -apple-system, sans-serif; margin-top: 40px; font-size: 26px; opacity: .6; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_SKETCH_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: Georgia, 'Times New Roman', serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.kicker {{ font-family: -apple-system, sans-serif; font-size: 26px; font-weight: 800;
  letter-spacing: 3px; text-transform: uppercase; color: {muted}; margin-bottom: 48px; }}
h1 {{ font-size: 70px; font-weight: 700; line-height: 1.18; margin-bottom: 56px; }}
.pill {{ font-family: -apple-system, sans-serif; display: inline-block; background: {accent};
  color: {ink}; padding: 28px 46px; border-radius: 100px; font-size: 38px; font-weight: 800;
  align-self: flex-start; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_sketch(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                       paginador: str) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _SKETCH_CTA.format(
            w=w, h=h, bg=SKETCH_BG, ink=SKETCH_INK, accent=accent,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    h1_size = 72 if len(titulo) <= 50 else 54
    cuerpo_html = f'<div class="body">{cuerpo}</div>' if cuerpo else ""
    # el boceto del camino solo va en el hook — es el elemento distintivo de
    # portada, no se repite en cada lámina para no saturar.
    ilustracion = (
        f'<div class="ilustracion">{_SKETCH_CAMINO_SVG.format(ink=SKETCH_INK, accent=accent)}</div>'
        if rol == "hook" else ""
    )
    return _SKETCH_SLIDE.format(
        w=w, h=h, bg=SKETCH_BG, ink=SKETCH_INK, muted=SKETCH_MUTED,
        h1_size=h1_size, titulo=titulo, cuerpo_html=cuerpo_html, ilustracion=ilustracion,
        paginador=paginador,
    )


# ---------------------------------------------------------------------------
# Skin "mockup_telefono" — texto bold arriba (con fragmento resaltado tipo
# marcador) + mockup de teléfono debajo con grid de iconos de apps (bloques
# de color, sin logos reales de terceros).
# ---------------------------------------------------------------------------
MOCKUP_BG = "#111214"
MOCKUP_FG = "#FFFFFF"
MOCKUP_MUTED = "#9B9BA1"
MOCKUP_ICONOS = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6C5CE7", "#00B894", "#FD79A8",
                 "#0984E3", "#E17055", "#00CEC9"]


def _mockup_grid_apps() -> str:
    iconos = "".join(f'<div class="icono" style="background:{c}"></div>' for c in MOCKUP_ICONOS)
    return f'<div class="grid-apps">{iconos}</div>'


_MOCKUP_SLIDE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column;
  padding: 90px; position: relative; overflow: hidden;
}}
h1 {{ font-size: {h1_size}px; font-weight: 800; line-height: 1.18; letter-spacing: -1px;
  max-width: 780px; margin-top: 20px; }}
.marcador {{ background: {accent}; color: {bg}; padding: 0 10px; box-decoration-break: clone; }}
.body {{ font-size: 34px; line-height: 1.5; color: {muted}; margin-top: 24px; }}
.telefono {{ margin: 48px auto 0; width: 460px; height: 400px; background: #1C1D20;
  border: 10px solid #2C2D31; border-radius: 48px; padding: 34px 26px; position: relative; }}
.notch {{ position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
  width: 140px; height: 26px; background: #2C2D31; border-radius: 0 0 18px 18px; }}
.grid-apps {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; margin-top: 30px; }}
.icono {{ aspect-ratio: 1; border-radius: 22px; }}
.paginador {{ position: absolute; top: 90px; right: 90px; font-size: 26px; font-weight: 700; color: {muted}; }}
</style></head><body>
<div class="paginador">{paginador}</div>
<h1>{titulo_html}</h1>
{cuerpo_html}
{telefono}
</body></html>"""

_MOCKUP_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 100px 90px;
}}
h1 {{ font-size: 62px; font-weight: 800; line-height: 1.2; letter-spacing: -1px; margin-bottom: 40px; }}
.cta-box {{ background: {accent}; color: {bg}; padding: 40px 44px; font-size: 38px;
  line-height: 1.4; font-weight: 800; }}
.brand {{ margin-top: 40px; font-size: 26px; color: {muted}; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_MOCKUP_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.kicker {{ font-size: 26px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase;
  color: {accent}; margin-bottom: 48px; }}
h1 {{ font-size: 74px; font-weight: 800; line-height: 1.15; letter-spacing: -1px; margin-bottom: 56px; }}
.pill {{ display: inline-block; background: {accent}; color: {bg}; padding: 28px 46px;
  border-radius: 100px; font-size: 38px; font-weight: 800; align-self: flex-start; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _mockup_resaltar(titulo: str) -> str:
    """Resalta (marcador de color) la última palabra del título — evoca el
    fragmento subrayado en amarillo del patrón de referencia, sin depender
    de que la IA marque manualmente qué palabra resaltar."""
    palabras = titulo.rsplit(" ", 1)
    if len(palabras) < 2:
        return f'<span class="marcador">{titulo}</span>'
    return f'{palabras[0]} <span class="marcador">{palabras[1]}</span>'


def _slide_html_mockup(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                       paginador: str) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _MOCKUP_CTA.format(
            w=w, h=h, bg=MOCKUP_BG, fg=MOCKUP_FG, accent=accent, muted=MOCKUP_MUTED,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    h1_size = 66 if len(titulo) <= 50 else 50
    cuerpo_html = f'<div class="body">{cuerpo}</div>' if cuerpo else ""
    # el mockup de teléfono con grid de apps es la firma del skin — va en
    # todas las láminas de contenido, no solo la portada.
    telefono = f'<div class="telefono"><div class="notch"></div>{_mockup_grid_apps()}</div>'
    return _MOCKUP_SLIDE.format(
        w=w, h=h, bg=MOCKUP_BG, fg=MOCKUP_FG, accent=accent, muted=MOCKUP_MUTED,
        h1_size=h1_size, titulo_html=_mockup_resaltar(titulo), cuerpo_html=cuerpo_html,
        telefono=telefono, paginador=paginador,
    )


# ---------------------------------------------------------------------------
# Skin "brutalista" — inspirado en un design system "Kinetic Brutalism"
# (ui-ux-pro-max): fondo blanco, tinta negra, CERO border-radius en todo el
# skin (único con esquinas 100% rectas), bordes gruesos, mayúsculas enormes
# con tracking apretado. Sin fuentes externas (system-ui bold en vez de
# Lexend Mega, para no depender de red al renderizar).
# ---------------------------------------------------------------------------
BRUTAL_BG = "#FFFFFF"
BRUTAL_INK = "#0A0A0A"
BRUTAL_MUTED = "#5C5C5C"

BRUTAL_KICKER = {"hook": "ALERTA", "obstaculo": "EL PROBLEMA", "resultado": "EL RESULTADO"}

_BRUTAL_SLIDE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; border-radius: 0 !important; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column;
  padding: 80px; position: relative; overflow: hidden;
}}
.kicker {{ display: inline-block; background: {ink}; color: {bg}; align-self: flex-start;
  font-size: 26px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase;
  padding: 12px 22px; margin-bottom: 40px; }}
h1 {{ font-size: {h1_size}px; font-weight: 900; line-height: 1.02; letter-spacing: -2px;
  text-transform: uppercase; }}
.body {{ font-size: 34px; line-height: 1.45; color: {muted}; margin-top: 32px; max-width: 800px;
  border-left: 6px solid {accent}; padding-left: 24px; }}
.footer {{ margin-top: auto; border-top: 6px solid {ink}; padding-top: 24px;
  display: flex; justify-content: space-between; font-size: 28px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
{cuerpo_html}
<div class="footer"><span>{brand_name}</span><span>{paginador}</span></div>
</body></html>"""

_BRUTAL_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; border-radius: 0 !important; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {accent}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 90px; border: 14px solid {ink};
}}
h1 {{ font-size: 68px; font-weight: 900; line-height: 1.05; letter-spacing: -2px;
  text-transform: uppercase; margin-bottom: 40px; }}
.cta-box {{ background: {ink}; color: {bg}; padding: 36px 40px; font-size: 38px;
  line-height: 1.35; font-weight: 800; }}
.brand {{ margin-top: 40px; font-size: 26px; font-weight: 800; text-transform: uppercase; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_BRUTAL_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; border-radius: 0 !important; }}
body {{
  width: {w}px; height: {h}px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: {bg}; color: {ink};
  display: flex; flex-direction: column; justify-content: center;
  padding: 110px 80px;
}}
.kicker {{ display: inline-block; background: {ink}; color: {bg}; align-self: flex-start;
  font-size: 24px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase;
  padding: 12px 22px; margin-bottom: 48px; }}
h1 {{ font-size: 68px; font-weight: 900; line-height: 1.05; letter-spacing: -2px;
  text-transform: uppercase; margin-bottom: 56px; }}
.pill {{ display: inline-block; background: {accent}; color: {ink}; border: 6px solid {ink};
  padding: 26px 42px; font-size: 36px; font-weight: 900; align-self: flex-start;
  text-transform: uppercase; }}
.flecha {{ margin-left: 14px; font-weight: 900; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_brutalista(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str,
                           paginador: str) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _BRUTAL_CTA.format(
            w=w, h=h, bg=BRUTAL_BG, ink=BRUTAL_INK, accent=accent,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    kicker = BRUTAL_KICKER.get(rol, "PASO")
    h1_size = 84 if len(titulo) <= 40 else (66 if len(titulo) <= 60 else 52)
    cuerpo_html = f'<div class="body">{cuerpo}</div>' if cuerpo else ""
    return _BRUTAL_SLIDE.format(
        w=w, h=h, bg=BRUTAL_BG, ink=BRUTAL_INK, muted=BRUTAL_MUTED, accent=accent,
        kicker=kicker, h1_size=h1_size, titulo=titulo, cuerpo_html=cuerpo_html,
        brand_name=brand["brand_name"], paginador=paginador,
    )


# ---------------------------------------------------------------------------
# Skin "premium" — inspirado en un design system "Liquid Glass" (ui-ux-pro-
# max) adaptado a exportación estática (sin blur/animación): fondo casi
# negro cálido, serif liviana centrada (peso 300, tracking amplio) en vez
# de bold — la restricción/elegancia es la firma, no el volumen. Único skin
# centrado y con peso de texto liviano.
# ---------------------------------------------------------------------------
PREMIUM_BG = "#0C0A09"
PREMIUM_FG = "#F5F1EA"
PREMIUM_MUTED = "#B4A99A"

_PREMIUM_SLIDE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: ui-serif, Georgia, 'Times New Roman', serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 110px 100px; position: relative; overflow: hidden;
}}
.kicker {{ font-family: -apple-system, sans-serif; font-size: 24px; font-weight: 600;
  letter-spacing: 6px; text-transform: uppercase; color: {accent}; margin-bottom: 36px; }}
.linea {{ width: 90px; height: 2px; background: {accent}; margin: 36px auto; }}
h1 {{ font-size: {h1_size}px; font-weight: 300; line-height: 1.28; letter-spacing: 0.5px; }}
.body {{ font-family: -apple-system, sans-serif; font-size: 32px; line-height: 1.6;
  color: {muted}; margin-top: 8px; font-weight: 300; max-width: 720px; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="linea"></div>
{cuerpo_html}
</body></html>"""

_PREMIUM_CTA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: ui-serif, Georgia, 'Times New Roman', serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 100px;
}}
h1 {{ font-size: 54px; font-weight: 300; line-height: 1.3; margin-bottom: 44px; }}
.cta-box {{ font-family: -apple-system, sans-serif; border: 2px solid {accent}; color: {fg};
  padding: 38px 48px; font-size: 32px; line-height: 1.5; font-weight: 400; }}
.brand {{ font-family: -apple-system, sans-serif; margin-top: 44px; font-size: 24px;
  letter-spacing: 3px; text-transform: uppercase; color: {muted}; }}
</style></head><body>
<h1>{titulo}</h1>
<div class="cta-box">{cuerpo}</div>
<div class="brand">{brand_name}</div>
</body></html>"""

_PREMIUM_HISTORIA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px;
  font-family: ui-serif, Georgia, 'Times New Roman', serif;
  background: {bg}; color: {fg};
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 130px 100px;
}}
.kicker {{ font-family: -apple-system, sans-serif; font-size: 22px; font-weight: 600;
  letter-spacing: 5px; text-transform: uppercase; color: {accent}; margin-bottom: 48px; }}
h1 {{ font-size: 58px; font-weight: 300; line-height: 1.3; margin-bottom: 48px; }}
.linea {{ width: 90px; height: 2px; background: {accent}; margin: 0 auto 48px; }}
.pill {{ font-family: -apple-system, sans-serif; border: 2px solid {accent}; color: {fg};
  padding: 26px 40px; font-size: 32px; font-weight: 400; }}
.flecha {{ margin-left: 14px; }}
</style></head><body>
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="linea"></div>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</body></html>"""


def _slide_html_premium(brand: dict, titulo: str, cuerpo: str, w: int, h: int, rol: str) -> str:
    accent = brand["accent_color"]
    if rol == "cta":
        return _PREMIUM_CTA.format(
            w=w, h=h, bg=PREMIUM_BG, fg=PREMIUM_FG, accent=accent, muted=PREMIUM_MUTED,
            titulo=titulo, cuerpo=cuerpo, brand_name=brand["brand_name"],
        )
    kicker = PRENSA_KICKER.get(rol, "PASO") if rol in PRENSA_KICKER else "PASO"
    h1_size = 62 if len(titulo) <= 50 else 48
    cuerpo_html = f'<div class="body">{cuerpo}</div>' if cuerpo else ""
    return _PREMIUM_SLIDE.format(
        w=w, h=h, bg=PREMIUM_BG, fg=PREMIUM_FG, accent=accent, muted=PREMIUM_MUTED,
        kicker=kicker, h1_size=h1_size, titulo=titulo, cuerpo_html=cuerpo_html,
    )


_LOGO_DATA_URI_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|svg\+xml);base64,[A-Za-z0-9+/]+=*$")


def _logo_html(logo_data_uri: str) -> str:
    if not logo_data_uri or not _LOGO_DATA_URI_RE.match(logo_data_uri):
        return ""
    return f'<img src="{logo_data_uri}">'


def _brand(perfil: str) -> dict:
    return json.loads((BASE / "brand_config.json").read_text())[perfil]


def _logo_data_uri(brand: dict) -> str:
    data = (BASE / brand["logo_url"]).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def _render_html(html: str, destino: Path, page) -> Path:
    page.set_content(html)
    page.wait_for_load_state("networkidle")
    page.screenshot(path=str(destino))
    return destino


def _slide_html(brand: dict, logo: str, titulo: str, cuerpo: str,
                w: int, h: int, rol: str = "desarrollo", paginador: str = "",
                paso_actual: int = 0, paso_total: int = 0, estilo_visual: str = "editorial") -> str:
    """`logo` es un data-URI o cadena vacía (sin logo) — ver _logo_html.
    `estilo_visual` elige el skin — ver ESTILOS_VISUALES."""
    if estilo_visual == "prensa_ia":
        return _slide_html_prensa(brand, titulo, cuerpo, w, h, rol, paginador, paso_actual, paso_total)
    if estilo_visual == "listicle":
        return _slide_html_listicle(brand, titulo, cuerpo, w, h, rol, paginador, paso_actual, paso_total)
    if estilo_visual == "ilustracion":
        return _slide_html_ilustracion(brand, titulo, cuerpo, w, h, rol, paginador)
    if estilo_visual == "sketch":
        return _slide_html_sketch(brand, titulo, cuerpo, w, h, rol, paginador)
    if estilo_visual == "mockup_telefono":
        return _slide_html_mockup(brand, titulo, cuerpo, w, h, rol, paginador)
    if estilo_visual == "brutalista":
        return _slide_html_brutalista(brand, titulo, cuerpo, w, h, rol, paginador)
    if estilo_visual == "premium":
        return _slide_html_premium(brand, titulo, cuerpo, w, h, rol)

    estilo = BEAT_STYLE.get(rol, BEAT_STYLE["desarrollo"])
    fondo_css = FONDOS.get(estilo["fondo"], FONDOS["desarrollo"]).format(
        primary=brand["primary_color"], secondary=brand["secondary_color"],
        accent=brand["accent_color"],
    )
    h1_size = 96 if estilo["titulo_grande"] else (88 if len(titulo) <= 60 else 68)

    kicker = estilo["kicker"] or ""
    if rol == "desarrollo" and paso_total:
        kicker = f"PASO {paso_actual} DE {paso_total}"

    paso_badge = ""
    if rol == "desarrollo" and paso_total:
        paso_badge = f'<div class="paso-badge">{paso_actual}</div>'

    if estilo["pill"] and cuerpo:
        cuerpo_html = f'<div class="pill">{cuerpo}<span class="flecha">→</span></div>'
    elif cuerpo:
        cuerpo_html = f'<div class="body">{cuerpo}</div>'
    else:
        cuerpo_html = ""

    return PLANTILLA.format(
        w=w, h=h, fondo_css=fondo_css,
        primary=brand["primary_color"], accent=brand["accent_color"],
        brand_name=brand["brand_name"], logo_html=_logo_html(logo), kicker=kicker,
        titulo=titulo, cuerpo_html=cuerpo_html, h1_size=h1_size,
        paginador=paginador, paso_badge=paso_badge,
    )


def producir_imagen(contenido: dict, slug: str, formato_imagen: str = "vertical",
                    mostrar_logo: bool = True, logo_data_uri: str = "",
                    video_slides: list = None, estilo_visual: str = "editorial") -> list:
    """Renderiza imagen estática o carrusel según contenido['formato'].

    Cada slide de carrusel usa el tratamiento visual de su 'rol' (BEAT_STYLE)
    y siempre se renderiza cuadrado. `formato_imagen` ("cuadrado"|"vertical")
    solo aplica cuando contenido['formato'] == 'imagen'.
    `mostrar_logo=False` omite el logo por completo; `logo_data_uri` (un PNG
    subido por el usuario como data-URI) reemplaza el logo de la marca para
    esta producción puntual, sin tocar brand_config.json.
    `video_slides` (solo carrusel): números de lámina (1-indexado) que el
    usuario eligió producir como video corto en vez de imagen — se omiten
    acá, las produce video_producer.producir_slide_video() por separado.
    `estilo_visual` ("editorial"|"prensa_ia", ver ESTILOS_VISUALES): skin
    visual a usar. El acento sale siempre de brand['accent_color'] en ambos
    skins — nunca hay color fijo a mano.
    Devuelve la lista de rutas PNG generadas (1 para imagen, N para carrusel,
    menos las que van como video).
    """
    video_slides = set(video_slides or [])
    brand = _brand(contenido["perfil"])
    logo = "" if not mostrar_logo else (logo_data_uri or _logo_data_uri(brand))
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)

    es_carrusel = contenido["formato"] == "carrusel"
    w, h = DIMENSION_CARRUSEL if es_carrusel else DIMENSIONES.get(
        formato_imagen, DIMENSIONES["vertical"])

    rutas = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})

        if es_carrusel:
            slides = contenido["slides"]
            total_desarrollo = sum(1 for s in slides if s.get("rol") == "desarrollo")
            contador_desarrollo = 0
            for i, s in enumerate(slides, 1):
                rol = s.get("rol", "desarrollo")
                if rol == "desarrollo":
                    contador_desarrollo += 1
                if i in video_slides:
                    continue
                html = _slide_html(
                    brand, logo, s["titular"], s["cuerpo"], w, h, rol=rol,
                    paginador=f"{i}/{len(slides)}",
                    paso_actual=contador_desarrollo, paso_total=total_desarrollo,
                    estilo_visual=estilo_visual,
                )
                rutas.append(_render_html(html, carpeta / f"slide_{i:02d}.png", page))
        else:
            html = _slide_html(brand, logo, contenido["titulo"],
                               contenido.get("cuerpo", ""), w, h, rol="hook",
                               estilo_visual=estilo_visual)
            rutas.append(_render_html(html, carpeta / "imagen.png", page))

        browser.close()
    return rutas


_HISTORIA_CON_FRAME = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px; position: relative; overflow: hidden;
  font-family: -apple-system, 'Helvetica Neue', sans-serif; color: #fff;
  display: flex; flex-direction: column; justify-content: flex-end; padding: 110px 90px;
}}
.frame {{ position: absolute; inset: 0; background-image: url('{frame_data_uri}');
  background-size: cover; background-position: center; }}
.scrim {{ position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 35%, rgba(0,0,0,.78) 100%); }}
.content {{ position: relative; z-index: 1; }}
.kicker {{ font-size: 26px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase;
  color: {accent}; margin-bottom: 24px; }}
h1 {{ font-size: 62px; font-weight: 800; line-height: 1.16; letter-spacing: -1px; margin-bottom: 40px; }}
.pill {{ display: inline-block; background: {accent}; color: #0B0B0C; padding: 26px 42px;
  border-radius: 100px; font-size: 34px; font-weight: 800; align-self: flex-start; }}
.flecha {{ margin-left: 12px; font-weight: 900; }}
</style></head><body>
<div class="frame"></div><div class="scrim"></div>
<div class="content">
<div class="kicker">{kicker}</div>
<h1>{titulo}</h1>
<div class="pill">Ya está en el feed<span class="flecha">→</span></div>
</div>
</body></html>"""


def producir_historia_con_frame(contenido: dict, slug: str, frame_bytes: bytes,
                                mostrar_logo: bool = True, logo_data_uri: str = "") -> Path:
    """Como producir_historia() pero para formato 'video': usa un FRAME REAL
    del video ya producido como fondo (en vez de color sólido/gradiente del
    skin) con un scrim oscuro abajo para que el texto se lea bien. `logo_*`
    quedan sin usar por ahora (ningún skin de historia usa logo hoy —
    consistente con el resto), se aceptan solo para firma uniforme del
    endpoint. Sin IA: mismo texto/pill ya generado, costo $0 aparte del
    frame que ya existe."""
    brand = _brand(contenido["perfil"])
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    w, h = DIMENSIONES["historia"]
    kicker = TIPO_LABEL.get(contenido["formato"], "NUEVO POST")
    frame_data_uri = "data:image/jpeg;base64," + base64.b64encode(frame_bytes).decode()
    html = _HISTORIA_CON_FRAME.format(
        w=w, h=h, frame_data_uri=frame_data_uri, accent=brand["accent_color"],
        kicker=kicker, titulo=contenido["titulo"],
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        destino = _render_html(html, carpeta / "historia.png", page)
        browser.close()
    return destino


def _historia_html(brand: dict, contenido: dict, estilo_visual: str, logo: str = "") -> str:
    """Arma el HTML de la historia-teaser según el skin — factorizado de
    producir_historia() para poder reusarlo también en `producir_overlay_
    historia()` (misma plantilla, fondo transparente) sin duplicar el if/elif
    por skin. `logo` solo aplica al skin "editorial" (el resto de las
    historias no llevan logo, como siempre)."""
    w, h = DIMENSIONES["historia"]
    kicker = TIPO_LABEL.get(contenido["formato"], "NUEVO POST")

    if estilo_visual == "prensa_ia":
        html = _PRENSA_HISTORIA.format(
            w=w, h=h, paper=PRENSA_PAPER, ink=PRENSA_INK, accent=brand["accent_color"],
            kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "listicle":
        html = _LISTICLE_HISTORIA.format(
            w=w, h=h, bg=LISTICLE_BG, fg=LISTICLE_FG, accent=brand["accent_color"],
            kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "ilustracion":
        html = _ILUSTRACION_HISTORIA.format(
            w=w, h=h, bg=ILUSTRACION_BG, ink=ILUSTRACION_INK, muted=ILUSTRACION_MUTED,
            accent=brand["accent_color"], kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "sketch":
        html = _SKETCH_HISTORIA.format(
            w=w, h=h, bg=SKETCH_BG, ink=SKETCH_INK, muted=SKETCH_MUTED,
            accent=brand["accent_color"], kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "mockup_telefono":
        html = _MOCKUP_HISTORIA.format(
            w=w, h=h, bg=MOCKUP_BG, fg=MOCKUP_FG, accent=brand["accent_color"],
            kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "brutalista":
        html = _BRUTAL_HISTORIA.format(
            w=w, h=h, bg=BRUTAL_BG, ink=BRUTAL_INK, accent=brand["accent_color"],
            kicker=kicker, titulo=contenido["titulo"],
        )
    elif estilo_visual == "premium":
        html = _PREMIUM_HISTORIA.format(
            w=w, h=h, bg=PREMIUM_BG, fg=PREMIUM_FG, accent=brand["accent_color"],
            kicker=kicker, titulo=contenido["titulo"],
        )
    else:
        fondo_css = FONDOS["hook"].format(
            primary=brand["primary_color"], secondary=brand["secondary_color"],
            accent=brand["accent_color"],
        )
        cuerpo_html = '<div class="pill">Ya está en el feed<span class="flecha">→</span></div>'
        html = PLANTILLA.format(
            w=w, h=h, fondo_css=fondo_css,
            primary=brand["primary_color"], accent=brand["accent_color"],
            brand_name=brand["brand_name"], logo_html=_logo_html(logo), kicker=kicker,
            titulo=contenido["titulo"], cuerpo_html=cuerpo_html, h1_size=90,
            paginador="", paso_badge="",
        )
    return html


def producir_historia(contenido: dict, slug: str, mostrar_logo: bool = True,
                      logo_data_uri: str = "", estilo_visual: str = "editorial") -> Path:
    """Genera una historia (9:16, Stories/Estados) anunciando el contenido que
    ya se publicó en el feed (video/carrusel/post) — un teaser, no un remix.

    Sin IA: reutiliza el título ya generado, costo $0. Pensada para usarse
    junto con la pieza principal ("generar en conjunto"), no en su lugar.
    """
    brand = _brand(contenido["perfil"])
    logo = "" if not mostrar_logo else (logo_data_uri or _logo_data_uri(brand))
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)
    w, h = DIMENSIONES["historia"]
    html = _historia_html(brand, contenido, estilo_visual, logo)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        destino = _render_html(html, carpeta / "historia.png", page)
        browser.close()
    return destino


def producir_overlay_historia(brand: dict, contenido: dict, estilo_visual: str) -> bytes:
    """Como producir_overlay_slide() pero para la historia-teaser: mismo
    diseño de `_historia_html()`, fondo forzado a transparente, para componer
    encima de un fondo animado (Pexels o IA) en vez del color/gradiente
    sólido del skin. Sin logo (igual que producir_historia con logo
    desactivado — consistente con el resto de los overlays de video)."""
    w, h = DIMENSIONES["historia"]
    html = _forzar_fondo_transparente(_historia_html(brand, contenido, estilo_visual))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        png_bytes = page.screenshot(omit_background=True)
        browser.close()
    return png_bytes


# ---------------------------------------------------------------------------
# Overlays de texto para VIDEO — reutiliza las mismas plantillas de skin
# (fondo transparente en vez de sólido) para que un video se vea con la
# misma identidad visual que sus láminas estáticas hermanas. Ver
# video_producer.py para cómo se componen sobre el video con FFmpeg.
# ---------------------------------------------------------------------------

def obtener_brand(perfil: str) -> dict:
    """Wrapper público de _brand — para módulos que ya tienen el perfil y
    necesitan el dict de marca sin duplicar la carga de brand_config.json."""
    return _brand(perfil)


def _forzar_fondo_transparente(html: str) -> str:
    """Override CSS inyectado antes de </head> — deja el <body> transparente
    sin tocar cada plantilla de skin individualmente (cubre `background` y
    `background-image`, que es como algunos skins arman blobs/gradientes)."""
    return html.replace(
        "</head>",
        "<style>body{background:transparent!important;background-image:none!important;}</style></head>",
    )


def producir_overlay_slide(brand: dict, slide: dict, estilo_visual: str,
                           w: int = 1080, h: int = 1080) -> bytes:
    """Renderiza UNA lámina de carrusel como PNG transparente (mismo diseño
    que su versión estática, sin logo) — se compone sobre el B-roll+voz en
    `video_producer.producir_slide_video()` para que la lámina-video se vea
    igual que sus hermanas imagen. Devuelve los bytes del PNG (con alfa)."""
    rol = slide.get("rol", "hook")
    html = _slide_html(
        brand, "", slide.get("titular", ""), slide.get("cuerpo", ""),
        w, h, rol=rol, estilo_visual=estilo_visual,
    )
    html = _forzar_fondo_transparente(html)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        png_bytes = page.screenshot(omit_background=True)
        browser.close()
    return png_bytes


# Estilo de "chip" de caption por skin — no es la lámina completa (eso sería
# demasiado grande sobre un video en movimiento), es una etiqueta chica con
# la identidad de color/tipografía/forma de cada skin, para el texto en
# pantalla del video completo (formato "video", no las láminas de carrusel).
_CAPTION_TABLA = {
    "brutalista": {"font": "sans", "weight": "900", "uppercase": True, "radius": "0"},
    "premium": {"font": "serif", "weight": "300", "uppercase": False, "radius": "0", "outline": True},
    "sketch": {"font": "serif", "weight": "700", "uppercase": False, "radius": "0", "transparente": True},
    "prensa_ia": {"font": "sans", "weight": "800", "uppercase": True, "radius": "8px", "invertido": True},
    "listicle": {"font": "sans", "weight": "800", "uppercase": False, "radius": "32px", "acento_bg": True},
    "ilustracion": {"font": "sans", "weight": "700", "uppercase": False, "radius": "24px"},
    "mockup_telefono": {"font": "sans", "weight": "800", "uppercase": False, "radius": "8px", "acento_bg": True},
    "editorial": {"font": "sans", "weight": "800", "uppercase": False, "radius": "32px", "acento_bg": True},
}

_CAPTION_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: {w}px; height: {h}px; background: transparent;
  display: flex; align-items: flex-end; justify-content: center; padding-bottom: 150px;
}}
.chip {{
  font-family: {font_family}; font-weight: {weight}; font-size: 56px; line-height: 1.3;
  background: {bg}; color: {fg}; border: {border}; border-radius: {radius};
  padding: 24px 40px; max-width: 880px; text-align: center; text-transform: {texttransform};
  text-shadow: {sombra};
}}
</style></head><body><div class="chip">{texto}</div></body></html>"""


def producir_caption_png(texto: str, estilo_visual: str, brand: dict,
                         w: int = 1080, h: int = 1920, texto_color: str = "",
                         fondo_activo: bool = True, fuente: str = "") -> bytes:
    """PNG transparente con el texto en pantalla estilizado según el skin —
    para overlays cortos sobre el video completo (no láminas de carrusel,
    ver producir_overlay_slide para eso).

    Overrides opcionales del usuario (si no se pasan, manda el default del
    skin — igual que siempre):
    `texto_color` (hex, ej "#FF00AA") pisa el color del texto; `fondo_activo
    =False` deja el texto SIN caja de fondo (solo texto con sombra, para que
    se lea sobre cualquier B-roll); `fuente` ("sans"|"serif") pisa la
    tipografía del skin.
    """
    accent = brand["accent_color"]
    cfg = _CAPTION_TABLA.get(estilo_visual, _CAPTION_TABLA["editorial"])
    fuente_final = fuente or cfg["font"]
    font_family = "ui-serif, Georgia, 'Times New Roman', serif" if fuente_final == "serif" \
        else "-apple-system, 'Helvetica Neue', sans-serif"

    if cfg.get("acento_bg"):
        bg, fg = accent, "#0B0B0C"
    elif cfg.get("invertido"):
        bg, fg = "#141414", "#FFFFFF"
    elif cfg.get("transparente"):
        bg, fg = "transparent", "#111111"
    else:
        bg, fg = "#FFFFFF", "#0B0B0C"
    border = f"3px solid {accent}" if cfg.get("outline") else "none"
    sombra = "none"

    if not fondo_activo:
        # Sin caja: texto suelto con sombra oscura para que se lea sobre
        # cualquier B-roll — blanco por defecto (el color del skin era para
        # texto SOBRE una chapa de color, no directo sobre video).
        bg, border = "transparent", "none"
        fg = texto_color or "#FFFFFF"
        sombra = "0 2px 10px rgba(0,0,0,.85), 0 0 4px rgba(0,0,0,.9)"
    elif texto_color:
        fg = texto_color

    html = _CAPTION_HTML.format(
        w=w, h=h, font_family=font_family, weight=cfg["weight"], bg=bg, fg=fg,
        border=border, radius=cfg["radius"], texttransform="uppercase" if cfg["uppercase"] else "none",
        sombra=sombra, texto=texto,
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        png_bytes = page.screenshot(omit_background=True)
        browser.close()
    return png_bytes
