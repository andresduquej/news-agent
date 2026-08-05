"""Subtítulos por ORACIÓN completa, con la palabra activa resaltada
(karaoke — solo la palabra que se dice en ese instante cambia de color, no
acumulativo) quemados vía ffmpeg/libass.

Adaptado del mismo patrón ya validado en avatarhype-studio/subtitulos.py —
la diferencia es que acá NO se transcribe con Whisper: news_agent ya tiene
el timing real palabra por palabra desde el alignment de ElevenLabs
(`voz_elevenlabs_con_timestamps` en test_video_pipeline.py), así que este
módulo solo agrupa y renderiza, no transcribe.

Un bloque = una oración completa (corta SOLO en fin de oración: . ! ? …),
nunca a mitad de frase — pedido de Andrés: "separar las frases, y a medida
que separa las frases ese es el tiempo que permanece la escena del video"
(1 ago 2026). Antes se agrupaba por cantidad fija de palabras, lo que podía
cortar una oración a la mitad y quedar desalineado del sentido del texto.
"""
from __future__ import annotations

import os
import subprocess

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

_FIN_DE_ORACION = (".", "!", "?", "...", "…")
TOPE_SEGURIDAD_PALABRAS = 25  # ~10s de habla — evita un cartel eterno si el texto no tiene puntuación


def agrupar_oraciones(palabras: list) -> list:
    """`palabras`: [(texto, inicio_seg, fin_seg), ...] (ver
    video_producer._palabras_desde_alignment). Devuelve [[(texto,ini,fin),...], ...]
    — una lista de bloques, cada bloque es una oración completa."""
    bloques: list[list[tuple]] = []
    actual: list[tuple] = []
    for palabra in palabras:
        actual.append(palabra)
        termina_oracion = palabra[0].rstrip().endswith(_FIN_DE_ORACION)
        if termina_oracion or len(actual) >= TOPE_SEGURIDAD_PALABRAS:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def _hex_a_ass(hex_color: str) -> str:
    """#RRGGBB -> &H00BBGGRR (formato de color de ASS: BGR, sin alpha)."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}"


def _ass_tiempo(segundos: float) -> str:
    cs = round(max(segundos, 0) * 100)
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    s, cs = divmod(resto, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generar_ass(
    bloques: list, out_path: str,
    color_texto: str = "#FFFFFF", color_resaltado: str = "#3956FA",
    color_fondo: str = "#000000", con_fondo: bool = True,
    fuente: str = "Poppins", tamano: int = 105,
    video_w: int = 1080, video_h: int = 1920,
) -> str:
    """Genera el .ass con una línea de diálogo POR PALABRA dentro de cada
    oración (el bloque completo se ve siempre, solo cambia de color la
    palabra activa) — mismo patrón que avatarhype-studio/subtitulos.py.
    `bloques`: [[(texto,ini,fin), ...], ...] — ya agrupados por
    `agrupar_oraciones()` (el caller decide si agrupa sobre todo el guion de
    una o tramo por tramo, para poder mantener el B-roll y el texto
    sincronizados en los mismos límites)."""
    c_texto = _hex_a_ass(color_texto)
    c_resaltado = _hex_a_ass(color_resaltado)
    c_fondo = _hex_a_ass(color_fondo)
    border_style = 3 if con_fondo else 1  # 3 = caja opaca, 1 = solo contorno

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_w}\n"
        f"PlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{fuente},{tamano},{c_texto},{c_texto},"
        f"&H00000000,{c_fondo},-1,0,0,0,100,100,0,0,{border_style},2,0,2,60,60,{video_h // 4},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lineas = [header]
    for bloque in bloques:
        for i, palabra_activa in enumerate(bloque):
            partes = []
            for j, (texto, _, _) in enumerate(bloque):
                color = c_resaltado if j == i else c_texto
                partes.append(f"{{\\c{color}}}{texto}")
            texto_linea = " ".join(partes)
            inicio = _ass_tiempo(palabra_activa[1])
            # El fin de esta línea es el INICIO de la palabra siguiente (no el
            # fin real de la palabra activa) — si hay una micro-pausa entre
            # palabras en el alignment de ElevenLabs, usar el fin real dejaba
            # un hueco sin ninguna línea de diálogo activa: el cartel entero
            # desaparecía y volvía a aparecer con la palabra siguiente
            # (reportado por Andrés). Con esto el bloque queda SIEMPRE visible
            # de principio a fin de la oración, sin parpadeos.
            si_ultima = i == len(bloque) - 1
            fin = _ass_tiempo(bloque[i + 1][1] if not si_ultima else palabra_activa[2])
            lineas.append(f"Dialogue: 0,{inicio},{fin},Default,,0,0,0,,{texto_linea}\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lineas)
    return out_path


def quemar_subtitulos(video_in: str, ass_path: str, video_out: str) -> str:
    # ffmpeg interpreta ":" dentro del filtro como separador de opciones --
    # hay que escapar los ":" del path (ej. "/Users/andres/...") con "\:".
    ass_escapado = ass_path.replace(":", "\\:")
    fonts_escapado = FONTS_DIR.replace(":", "\\:")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_in,
         "-vf", f"subtitles={ass_escapado}:fontsdir={fonts_escapado}",
         "-c:a", "copy",
         video_out],
        check=True, capture_output=True,
    )
    return video_out
