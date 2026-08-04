"""
Tests del Generator (librería estándar `unittest`, sin dependencias extra).

Correr:  python3 -m unittest test_generator -v
"""

import unittest

import generator as gen


def noticia(titulo="t", resumen="r", tema="Ecommerce", score=3):
    return {"titulo": titulo, "resumen": resumen, "fuente": "X",
            "fecha": "2026-07-21", "tema": tema, "url": "u", "score": score}


class TestGenerator(unittest.TestCase):

    def test_formato_video_por_tutorial(self):
        n = noticia(titulo="Cómo hacer campañas: guía paso a paso")
        self.assertEqual(gen.detectar_formato(n), "video")

    def test_formato_carrusel_por_tendencias(self):
        n = noticia(titulo="6 tendencias de ecommerce que debes conocer")
        self.assertEqual(gen.detectar_formato(n), "carrusel")

    def test_formato_imagen_por_lanzamiento(self):
        n = noticia(titulo="Meta lanza nueva herramienta", resumen="anuncio record")
        self.assertEqual(gen.detectar_formato(n), "imagen")

    def test_formato_default_carrusel_sin_senales(self):
        n = noticia(titulo="Reporte", resumen="texto neutro")
        self.assertEqual(gen.detectar_formato(n), "carrusel")

    def test_intencion_accionable(self):
        n = noticia(titulo="Guía: cómo aplicar esta estrategia gratis")
        self.assertEqual(gen.detectar_intencion(n), "accionable")

    def test_intencion_informativa(self):
        n = noticia(titulo="Meta reporta cifras del trimestre", resumen="datos")
        self.assertEqual(gen.detectar_intencion(n), "informativo")

    def test_informativo_no_lleva_cta(self):
        n = noticia(titulo="Meta reporta cifras del trimestre", resumen="datos")
        brief = gen.construir_brief(n)
        self.assertEqual(brief["intencion"], "informativo")
        self.assertEqual(brief["cta"], "")

    def test_accionable_lleva_cta(self):
        n = noticia(titulo="Cómo aplicar esta estrategia gratis")
        brief = gen.construir_brief(n)
        self.assertEqual(brief["intencion"], "accionable")
        self.assertNotEqual(brief["cta"], "")

    def test_brief_tiene_campos_clave(self):
        brief = gen.construir_brief(noticia())
        for campo in ("formato", "intencion", "gancho", "puntos_clave", "cta"):
            self.assertIn(campo, brief)

    def test_generar_respeta_top_n(self):
        datos = [noticia(titulo=f"n{i}") for i in range(10)]
        briefs = gen.generar(datos, top=5)
        self.assertEqual(len(briefs), 5)

    def test_generar_conserva_tema_y_score(self):
        briefs = gen.generar([noticia(tema="TikTok Ads", score=4)], top=1)
        self.assertEqual(briefs[0]["tema"], "TikTok Ads")
        self.assertEqual(briefs[0]["score"], 4)


if __name__ == "__main__":
    unittest.main()
