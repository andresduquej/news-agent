"""Sprint 0 — prueba de render HTML→imagen con Playwright.

Renderiza un slide 1080x1350 (4:5) con el branding de brand_config.json
y lo captura como PNG. Uso: .venv/bin/python test_playwright_render.py [perfil]
"""

import base64
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ margin: 0; box-sizing: border-box; }}
body {{
  width: 1080px; height: 1350px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  background: linear-gradient(160deg, {primary} 0%, {secondary} 100%);
  color: #fff; display: flex; flex-direction: column;
  justify-content: space-between; padding: 90px;
}}
.kicker {{ font-size: 34px; font-weight: 700; letter-spacing: 4px;
  text-transform: uppercase; color: {accent}; }}
h1 {{ font-size: 88px; font-weight: 800; line-height: 1.1; }}
.body {{ font-size: 42px; line-height: 1.45; opacity: .92; }}
.footer {{ display: flex; align-items: center; gap: 28px; }}
.footer img {{ height: 110px; }}
.footer span {{ font-size: 36px; font-weight: 600; }}
</style></head><body>
<div class="kicker">Noticia · IA</div>
<h1>La IA ya escribe el 40% del contenido de marcas en LatAm</h1>
<div class="body">Las agencias que automatizan su pipeline de contenido publican 5x más
sin subir costos. Esto es lo que significa para tu negocio.</div>
<div class="footer"><img src="{logo}"><span>{brand_name}</span></div>
</body></html>"""


def render(perfil: str = "andres_duque") -> Path:
    brand = json.loads((BASE / "brand_config.json").read_text())[perfil]
    html = HTML.format(
        primary=brand["primary_color"],
        secondary=brand["secondary_color"],
        accent=brand["accent_color"],
        brand_name=brand["brand_name"],
        logo="data:image/png;base64,"
        + base64.b64encode((BASE / brand["logo_url"]).read_bytes()).decode(),
    )
    out = BASE / f"test_render_{perfil}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(out))
        browser.close()
    return out


if __name__ == "__main__":
    perfil = sys.argv[1] if len(sys.argv) > 1 else "andres_duque"
    print(render(perfil))
