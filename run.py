"""
run.py — Un solo comando para levantar el Agente de Contenido.

Arranca el servidor del dashboard y abre el navegador automáticamente.
Reemplaza al run.py viejo (pipeline de briefs en Markdown sin IA/dashboard,
de la época Beta $0 — superado desde que existe el dashboard con IA).

Uso:
    python3 run.py                # arranca en :8765 y abre el navegador
    python3 run.py --port 9000    # otro puerto
    python3 run.py --no-browser   # no abrir el navegador automáticamente
"""

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "dashboard"))


def _abrir_navegador(url: str, espera: float = 1.5) -> None:
    time.sleep(espera)
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente de Contenido — dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}"

    if not args.no_browser:
        threading.Thread(target=_abrir_navegador, args=(url,), daemon=True).start()

    print(f"\nAgente de Contenido — {url}", file=sys.stderr)
    print("(Ctrl+C para detener)\n", file=sys.stderr)

    import uvicorn
    from app import app as dashboard_app  # dashboard/app.py, ya en sys.path

    uvicorn.run(dashboard_app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
