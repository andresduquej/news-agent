"""
Exporter — guarda los briefs generados como archivos Markdown listos para
copiar/grabar. Sin dependencias extra, librería estándar, costo $0.

Crea una carpeta por fecha:  briefs/YYYY-MM-DD/
  - 01-<slug>.md, 02-<slug>.md, ...  (un archivo por brief)
  - index.md                          (resumen con enlaces a cada brief)

Uso:
  python3 news_fetcher.py | python3 ranker.py | python3 generator.py | python3 exporter.py
  python3 exporter.py briefs.json --dir briefs
"""

import json
import os
import re
import sys
from datetime import datetime

OUT_DIR = "briefs"


def slugify(texto: str, max_len: int = 40) -> str:
    tabla = str.maketrans("áéíóúü", "aeiouu")
    t = texto.lower().translate(tabla)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:max_len].strip("-") or "brief"


def brief_a_markdown(b: dict, indice: int) -> str:
    lineas = [
        f"# {indice:02d}. {b.get('titulo_fuente', '(sin título)')}",
        "",
        f"- **Tema:** {b.get('tema', '')}",
        f"- **Formato:** {b.get('formato', '')}",
        f"- **Intención:** {b.get('intencion', '')}",
        f"- **Score:** {b.get('score', '')}/5",
        f"- **Fuente:** {b.get('fuente', '')}",
    ]
    if b.get("url"):
        lineas.append(f"- **Enlace:** {b['url']}")
    lineas += ["", "## Gancho", b.get("gancho", ""), "", "## Puntos clave"]
    for p in b.get("puntos_clave", []):
        lineas.append(f"- {p}")

    # Detalle específico del formato.
    if b.get("sugerencia_slides"):
        lineas += ["", "## Slides sugeridos"]
        for s in b["sugerencia_slides"]:
            lineas.append(f"- {s}")
    if b.get("estructura_video"):
        lineas += ["", "## Estructura del video"]
        for s in b["estructura_video"]:
            lineas.append(f"- {s}")
    if b.get("sugerencia_imagen"):
        img = b["sugerencia_imagen"]
        lineas += [
            "", "## Imagen",
            f"- **Texto principal:** {img.get('texto_principal', '')}",
            f"- **Texto de apoyo:** {img.get('texto_apoyo', '')}",
            f"- **Pie:** {img.get('pie', '')}",
        ]

    cta = b.get("cta", "")
    lineas += ["", "## CTA", cta if cta else "_(sin CTA — contenido informativo)_", ""]
    return "\n".join(lineas)


def exportar(briefs: list, base_dir: str = OUT_DIR) -> str:
    fecha = datetime.now().strftime("%Y-%m-%d")
    carpeta = os.path.join(base_dir, fecha)
    os.makedirs(carpeta, exist_ok=True)

    index = [f"# Briefs del {fecha}", "", f"Total: {len(briefs)}", ""]
    for i, b in enumerate(briefs, 1):
        nombre = f"{i:02d}-{slugify(b.get('titulo_fuente', ''))}.md"
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(brief_a_markdown(b, i))
        cta_flag = "con CTA" if b.get("cta") else "informativo"
        index.append(
            f"{i}. [{b.get('formato', '')}/{cta_flag}] "
            f"[{b.get('titulo_fuente', '')[:60]}]({nombre}) — score {b.get('score', '')}/5"
        )

    ruta_index = os.path.join(carpeta, "index.md")
    with open(ruta_index, "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")

    # JSON estructurado: lo usan video_generator.py / image_generator.py /
    # carousel_generator.py para producir el contenido final.
    ruta_json = os.path.join(carpeta, "briefs.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(briefs, f, ensure_ascii=False, indent=2)

    return carpeta


def _parse_args(argv):
    ruta, base = None, OUT_DIR
    i = 1
    while i < len(argv):
        if argv[i] == "--dir" and i + 1 < len(argv):
            base = argv[i + 1]
            i += 2
        else:
            ruta = argv[i]
            i += 1
    return ruta, base


def _load_input(ruta) -> list:
    if ruta:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    print("Uso: python3 exporter.py briefs.json [--dir briefs]", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    ruta, base = _parse_args(sys.argv)
    briefs = _load_input(ruta)
    carpeta = exportar(briefs, base)
    print(f"Guardados {len(briefs)} briefs en: {carpeta}/", file=sys.stderr)
    print(f"Abre el índice: {os.path.join(carpeta, 'index.md')}", file=sys.stderr)


if __name__ == "__main__":
    main()
