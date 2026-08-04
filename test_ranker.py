"""
Tests del Ranker (librería estándar `unittest`, sin dependencias extra).

Correr:  python3 -m unittest test_ranker -v
"""

import unittest
from datetime import datetime, timezone

import ranker as rk


HOY = datetime(2026, 7, 21, tzinfo=timezone.utc)


def noticia(titulo="t", resumen="r", fecha="2026-07-21", tema="Ecommerce"):
    return {"titulo": titulo, "resumen": resumen, "fuente": "X",
            "fecha": fecha, "tema": tema, "url": ""}


class TestRanker(unittest.TestCase):

    def test_normalize_quita_tildes_y_minusculas(self):
        self.assertEqual(rk.normalize("Automatización IA"), "automatizacion ia")

    def test_days_since_hoy(self):
        self.assertEqual(rk.days_since("2026-07-21", HOY), 0)

    def test_days_since_una_semana(self):
        self.assertEqual(rk.days_since("2026-07-14", HOY), 7)

    def test_days_since_fecha_invalida(self):
        self.assertIsNone(rk.days_since("no-fecha", HOY))

    def test_count_hooks_detecta_y_tope(self):
        texto = rk.normalize("Nuevo lanzamiento gratis viral de IA record")
        hooks = rk.count_hooks(texto)
        self.assertLessEqual(len(hooks), rk.MAX_HOOKS_COUNTED)

    def test_score_alto_para_fresca_con_ganchos(self):
        n = noticia(titulo="Nuevo lanzamiento gratis de IA", fecha="2026-07-21")
        r = rk.score_news(n, HOY)
        self.assertEqual(r["score"], 5)
        self.assertIn("de hoy", r["motivo"])

    def test_score_bajo_para_vieja_sin_ganchos(self):
        n = noticia(titulo="Reporte trimestral", resumen="(sin resumen)",
                    fecha="2026-06-01")
        r = rk.score_news(n, HOY)
        self.assertLessEqual(r["score"], 2)

    def test_score_en_rango_1_a_5(self):
        for n in [noticia(), noticia(titulo="", resumen="", fecha=""),
                  noticia(titulo="IA viral record millones")]:
            r = rk.score_news(n, HOY)
            self.assertIn(r["score"], {1, 2, 3, 4, 5})

    def test_rank_ordena_descendente(self):
        datos = [
            noticia(titulo="Reporte", resumen="(sin resumen)", fecha="2026-05-01"),
            noticia(titulo="Nuevo lanzamiento gratis de IA", fecha="2026-07-21"),
        ]
        ordenadas = rk.rank(datos, HOY)
        self.assertGreaterEqual(ordenadas[0]["score"], ordenadas[1]["score"])
        self.assertEqual(ordenadas[0]["titulo"], "Nuevo lanzamiento gratis de IA")

    def test_rank_conserva_campos_originales(self):
        ordenadas = rk.rank([noticia(tema="TikTok Ads")], HOY)
        n = ordenadas[0]
        self.assertEqual(n["tema"], "TikTok Ads")
        self.assertIn("score", n)
        self.assertIn("motivo", n)


if __name__ == "__main__":
    unittest.main()
