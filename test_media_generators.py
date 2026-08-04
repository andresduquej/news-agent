"""
Tests de video_generator.py, image_generator.py y carousel_generator.py.

No llaman a `say`/`ffmpeg` de verdad (mockeados con monkeypatch de subprocess):
validan la lógica de selección de briefs, nombres de archivo y estructura,
sin depender de binarios externos ni tocar el sistema.

Correr:  python3 -m unittest test_media_generators -v
"""

import os
import tempfile
import unittest
from unittest.mock import patch

import video_generator as vg
import image_generator as ig
import carousel_generator as cg


def brief(titulo="Cómo vender más", formato="video", cta="Aplícalo ya"):
    return {
        "titulo_fuente": titulo, "tema": "Ventas", "fuente": "X", "url": "u",
        "score": 4, "formato": formato, "intencion": "accionable",
        "gancho": f"¿Ya viste esto? {titulo}",
        "puntos_clave": ["Punto uno", "Punto dos"],
        "cta": cta,
        "estructura_video": ["0-3s: gancho", "cierre"],
        "sugerencia_imagen": {
            "texto_principal": titulo, "texto_apoyo": "Apoyo", "pie": cta,
        },
        "sugerencia_slides": ["Portada", "Slide 1", "Slide 2", "Cierre"],
    }


class TestVideoGenerator(unittest.TestCase):

    def test_guion_incluye_gancho_puntos_y_cierre(self):
        b = brief()
        frases = vg._guion_desde_brief(b)
        self.assertEqual(frases[0], b["gancho"])
        self.assertIn("Punto uno", frases)
        self.assertEqual(frases[-1], b["cta"])

    def test_guion_usa_cierre_generico_si_no_hay_cta(self):
        b = brief(cta="")
        frases = vg._guion_desde_brief(b)
        self.assertTrue(frases[-1])

    def test_slugify_normaliza(self):
        self.assertEqual(vg._slugify("¡Cómo Vender Más!"), "como-vender-mas")

    def test_generar_para_briefs_filtra_solo_video(self):
        briefs = [brief(formato="video"), brief(formato="carrusel"), brief(formato="imagen")]
        with patch.object(vg, "generar_video", return_value="ok.mp4") as mock_gen:
            rutas = vg.generar_para_briefs(briefs, base_dir="ignorado")
        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(rutas, ["ok.mp4"])


class TestImageGenerator(unittest.TestCase):

    def test_generar_para_briefs_filtra_solo_imagen(self):
        briefs = [brief(formato="video"), brief(formato="imagen"), brief(formato="carrusel")]
        with patch.object(ig, "generar_imagen", return_value="ok.png") as mock_gen:
            rutas = ig.generar_para_briefs(briefs, base_dir="ignorado")
        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(rutas, ["ok.png"])

    def test_generar_imagen_crea_png_real(self):
        b = brief(formato="imagen")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = ig.generar_imagen(b, tmp, 1)
            self.assertTrue(ruta.endswith(".png"))
            self.assertTrue(os.path.isfile(ruta))


class TestCarouselGenerator(unittest.TestCase):

    def test_generar_para_briefs_filtra_solo_carrusel(self):
        briefs = [brief(formato="video"), brief(formato="carrusel"), brief(formato="imagen")]
        with patch.object(cg, "generar_carrusel", return_value="carpeta/") as mock_gen:
            rutas = cg.generar_para_briefs(briefs, base_dir="ignorado")
        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(rutas, ["carpeta/"])

    def test_generar_carrusel_crea_una_imagen_por_slide(self):
        b = brief(formato="carrusel")
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = cg.generar_carrusel(b, tmp, 1)
            archivos = os.listdir(carpeta)
            self.assertEqual(len(archivos), len(b["sugerencia_slides"]))


if __name__ == "__main__":
    unittest.main()
