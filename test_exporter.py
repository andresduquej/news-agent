"""
Tests del Exporter (librería estándar `unittest`, sin dependencias extra).

Correr:  python3 -m unittest test_exporter -v
"""

import os
import tempfile
import unittest

import exporter as ex


def brief(titulo="Cómo hacer campañas", formato="video", intencion="accionable",
          cta="Guarda esto.", score=4):
    return {
        "titulo_fuente": titulo, "tema": "Meta Ads", "fuente": "X", "url": "u",
        "score": score, "formato": formato, "intencion": intencion,
        "gancho": "gancho", "puntos_clave": ["a", "b"], "cta": cta,
        "estructura_video": ["0-3s: gancho", "cierre"],
    }


class TestExporter(unittest.TestCase):

    def test_slugify_normaliza(self):
        self.assertEqual(ex.slugify("Cómo Hacer Ads 2026!"), "como-hacer-ads-2026")

    def test_slugify_vacio_da_fallback(self):
        self.assertEqual(ex.slugify("!!!"), "brief")

    def test_markdown_incluye_titulo_y_cta(self):
        md = ex.brief_a_markdown(brief(), 1)
        self.assertIn("Cómo hacer campañas", md)
        self.assertIn("Guarda esto.", md)

    def test_markdown_informativo_sin_cta(self):
        md = ex.brief_a_markdown(brief(intencion="informativo", cta=""), 2)
        self.assertIn("sin CTA", md)

    def test_exportar_crea_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = ex.exportar([brief(), brief(titulo="Otra")], base_dir=tmp)
            archivos = sorted(os.listdir(carpeta))
            self.assertIn("index.md", archivos)
            md_files = [a for a in archivos if a.endswith(".md") and a != "index.md"]
            self.assertEqual(len(md_files), 2)

    def test_index_lista_todos(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = ex.exportar([brief(), brief(titulo="Otra")], base_dir=tmp)
            with open(os.path.join(carpeta, "index.md"), encoding="utf-8") as f:
                contenido = f.read()
            self.assertIn("Total: 2", contenido)


if __name__ == "__main__":
    unittest.main()
