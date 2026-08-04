"""
Tests del News Fetcher (librería estándar `unittest`, sin dependencias extra).

Cubre limpieza de texto/HTML y títulos, parseo de fecha, extracción de fuente
y estructura del JSON de salida (sin tocar internet, usando un feed simulado).

Correr:  python3 -m unittest test_news_fetcher -v
"""

import types
import unittest

import news_fetcher as nf


def make_entry(title, summary="", published_parsed=None, source_title=None, link=""):
    entry = types.SimpleNamespace(
        title=title,
        summary=summary,
        published_parsed=published_parsed,
        link=link,
    )
    if source_title is not None:
        entry.source = types.SimpleNamespace(title=source_title)
    return entry


class TestNewsFetcher(unittest.TestCase):

    def test_clean_text_quita_html_y_espacios(self):
        self.assertEqual(nf.clean_text("<p>Hola   <b>mundo</b></p>"), "Hola mundo")

    def test_clean_text_vacio(self):
        self.assertEqual(nf.clean_text(""), "")

    def test_clean_text_quita_simbolos_decorativos(self):
        self.assertEqual(nf.clean_text("📣 Tutorial de Ads ►"), "Tutorial de Ads")

    def test_clean_text_quita_codigo_de_video(self):
        self.assertEqual(
            nf.clean_text("Tutorial completo Pablo Escobar (D9MPcACAKF)"),
            "Tutorial completo Pablo Escobar",
        )

    def test_clean_title_quita_sufijo_fuente(self):
        entry = make_entry("IA revoluciona el marketing - El País")
        self.assertEqual(nf.clean_title(entry), "IA revoluciona el marketing")

    def test_extract_source_desde_campo_source(self):
        entry = make_entry("Titular - X", source_title="Xataka")
        self.assertEqual(nf.extract_source(entry), "Xataka")

    def test_extract_source_fallback_titulo(self):
        entry = make_entry("Titular importante - Forbes")
        self.assertEqual(nf.extract_source(entry), "Forbes")

    def test_parse_date_iso(self):
        entry = make_entry("t", published_parsed=(2026, 7, 21, 10, 30, 0, 0, 0, 0))
        self.assertEqual(nf.parse_date(entry), "2026-07-21")

    def test_parse_date_vacia(self):
        self.assertEqual(nf.parse_date(make_entry("t")), "")

    def test_fetch_topic_estructura(self):
        fake_feed = types.SimpleNamespace(
            entries=[
                make_entry(
                    "Noticia uno - Medio A",
                    summary="<p>Resumen uno</p>",
                    published_parsed=(2026, 7, 20, 8, 0, 0, 0, 0, 0),
                    source_title="Medio A",
                )
            ]
        )
        original_parse = nf.feedparser.parse
        nf.feedparser.parse = lambda url: fake_feed
        try:
            result = nf.fetch_topic("Ecommerce", "ecommerce")
        finally:
            nf.feedparser.parse = original_parse

        self.assertEqual(len(result), 1)
        n = result[0]
        self.assertEqual(
            set(n.keys()), {"titulo", "resumen", "fuente", "fecha", "tema", "url"}
        )
        self.assertEqual(n["titulo"], "Noticia uno")
        self.assertEqual(n["resumen"], "Resumen uno")
        self.assertEqual(n["fuente"], "Medio A")
        self.assertEqual(n["fecha"], "2026-07-20")
        self.assertEqual(n["tema"], "Ecommerce")


if __name__ == "__main__":
    unittest.main()
