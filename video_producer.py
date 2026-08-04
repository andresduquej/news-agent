"""
Video Producer — Sprint 3 del Agente de Contenido.

Produce el video final 9:16 (1080x1920): voz ElevenLabs + B-roll de Pexels +
ensamblado FFmpeg. Pipeline validado en Sprint 0 (test_video_pipeline.py).

Subtítulos completos sincronizados palabra por palabra (1 ago 2026): antes el
video quemaba `texto_pantalla`, un puñado de frases curadas por la IA (1 por
tramo) que se estiraban a lo largo de TODO el tramo — Andrés reportó que no
aparecían "todos los subtítulos" acorde a lo narrado, solo esas frases
sueltas. Fix: se dejó de pedirle texto a la IA para esto — ahora se usa
`voz_elevenlabs_con_timestamps()`, que además del audio devuelve el
alignment carácter-por-carácter que ElevenLabs ya calcula al generar la voz.
`_palabras_desde_alignment()` arma palabras con su tiempo real, y
`_agrupar_subtitulos()` las junta en bloques de `PALABRAS_POR_SUBTITULO`
(estilo TikTok/CapCut) — cubren el guion completo, sin huecos, con el
timing REAL de la narración (nunca una estimación).

Ritmo de corte según duración del tramo (30 jul 2026): antes cada tramo
(hook/obstaculo/ejecucion/cta) llevaba SIEMPRE una sola toma de B-roll, sin
importar cuánto durara — un tramo largo (7-9s) quedaba con la misma imagen
fija todo ese tiempo mientras el texto en pantalla ya había cambiado, se
sentía "descuadrado" (reportado por Andrés). Ahora `_tomas_por_tramo()`
calcula cuántas tomas le corresponden según su duración real (~1 cada 2.5s,
tope 5 por tramo) — todas de la MISMA query (coherencia temática) pero clips
DISTINTOS de Pexels (`broll_pexels(..., indice=k)` pide el resultado k-ésimo
de la búsqueda en vez de repetir siempre el primero).

Multi-B-roll por tramo (27 jul 2026): si `contenido` trae `broll_query_
<segmento>` (hook/obstaculo/ejecucion/cta, los genera generator_ia.py), el
video cambia de toma en cada tramo en vez de repetir un solo B-roll — los
límites de tiempo de cada tramo se calculan proporcionales a la duración
REAL de la voz ya generada (no un estimado), repartidos según la cantidad
de caracteres de texto de cada tramo.

Requiere ELEVENLABS_API_KEY y PEXELS_API_KEY en .env.
"""

import subprocess
import tempfile
from pathlib import Path

import config_store
import image_producer
import ranker_ia  # carga .env
import usage_store
from test_video_pipeline import (
    broll_pexels, ensamblar_con_overlays, ensamblar_multi_broll, voz_elevenlabs_con_timestamps,
)

BASE = Path(__file__).resolve().parent
OUT = BASE / "producciones"

SEGMENTOS_VIDEO = ("hook", "obstaculo", "ejecucion", "cta")
DURACION_TOMA_OBJETIVO = 2.5  # ritmo de corte dinámico (2-3s) pedido por Andrés para más retención
MAX_TOMAS_POR_TRAMO = 5  # tope para no disparar de más las llamadas a Pexels
PALABRAS_POR_SUBTITULO = 4  # tamaño del bloque de subtítulo (estilo TikTok/CapCut)


def _palabras_desde_alignment(alignment: dict) -> list:
    """Agrupa el alignment carácter-por-carácter de ElevenLabs en palabras —
    [(palabra, inicio_seg, fin_seg), ...], cortando en cada espacio."""
    chars = alignment["characters"]
    inicios = alignment["character_start_times_seconds"]
    fines = alignment["character_end_times_seconds"]
    palabras = []
    actual, ini, fin = "", None, None
    for ch, s, e in zip(chars, inicios, fines):
        if ch.isspace():
            if actual:
                palabras.append((actual, ini, fin))
                actual, ini, fin = "", None, None
            continue
        if ini is None:
            ini = s
        actual += ch
        fin = e
    if actual:
        palabras.append((actual, ini, fin))
    return palabras


def _agrupar_subtitulos(palabras: list, n: int = PALABRAS_POR_SUBTITULO) -> list:
    """[(texto, inicio_seg, fin_seg), ...] agrupando de a `n` palabras — cubre
    TODO lo narrado (a diferencia del chip curado anterior), con el timing
    REAL de la voz ya generada, no una proporción estimada."""
    grupos = []
    for i in range(0, len(palabras), n):
        bloque = palabras[i:i + n]
        texto = " ".join(w for w, _, _ in bloque)
        grupos.append((texto, bloque[0][1], bloque[-1][2]))
    return grupos


def _tomas_por_tramo(duracion_seg: float) -> int:
    """Cuántas tomas de B-roll le corresponden a un tramo según su duración
    REAL — antes era siempre 1 por tramo, lo que dejaba tramos largos (7-9s)
    con una sola toma fija en pantalla todo ese tiempo mientras el texto en
    pantalla ya había cambiado, sensación de "descuadrado" reportada por el
    usuario. Ahora escala con el guion: más duración, más cortes."""
    return max(1, min(MAX_TOMAS_POR_TRAMO, round(duracion_seg / DURACION_TOMA_OBJETIVO)))


def _duracion_archivo(ruta: Path) -> float:
    return float(
        subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(ruta),
        ]).strip()
    )


def _limites_segmentos(contenido: dict, duracion_total: float) -> dict:
    """Reparte `duracion_total` (segundos REALES de la voz ya generada) entre
    los tramos con texto no vacío, proporcional a la cantidad de caracteres de
    cada uno — devuelve {campo: (inicio, fin)} para poder alinear captions y
    B-roll al tiempo real de la narración (nunca a un estimado hecho antes de
    generar la voz)."""
    partes = [(k, contenido.get(k, "")) for k in SEGMENTOS_VIDEO if (contenido.get(k) or "").strip()]
    total_chars = sum(len(t) for _, t in partes) or 1
    limites = {}
    inicio = 0.0
    for k, t in partes:
        dur = max(duracion_total * (len(t) / total_chars), 0.6)
        limites[k] = (inicio, inicio + dur)
        inicio += dur
    return limites


def _segmentos_por_duracion(contenido: dict, duracion_total: float) -> list:
    """Como `_limites_segmentos` pero devuelve [(campo, duracion_seg), ...] —
    formato que espera `ensamblar_multi_broll` (un clip por tramo, no ventanas)."""
    return [(k, fin - ini) for k, (ini, fin) in _limites_segmentos(contenido, duracion_total).items()]


def producir_video(contenido: dict, slug: str, estilo_visual: str = "editorial",
                   texto_color: str = "", fondo_texto: bool = True, fuente_texto: str = "") -> Path:
    """Genera el video para un contenido de formato 'video'. Devuelve la ruta MP4.
    Quema subtítulos completos (todo lo narrado, en bloques de
    `PALABRAS_POR_SUBTITULO`) sincronizados al timing REAL de la voz —
    ElevenLabs devuelve el alignment carácter-por-carácter del audio ya
    generado, así que no hay que estimar nada (antes se usaba `texto_pantalla`,
    un puñado de frases curadas por la IA que se estiraban a lo largo de todo
    el tramo y no acompañaban lo que se iba diciendo). `texto_color`/
    `fondo_texto`/`fuente_texto` pisan el estilo del skin si el usuario los
    eligió (vacío/True/vacío = usar el default del skin).

    Si `contenido` trae `broll_query_<segmento>` por tramo, cambia de B-roll
    en cada tramo (sincronizado a la duración real de la voz); si no —
    contenido generado antes de esta feature — usa un solo B-roll para todo,
    como siempre.
    """
    carpeta = OUT / slug
    carpeta.mkdir(parents=True, exist_ok=True)

    voice_id = config_store.cargar_voz()["voice_id"]
    voz, alignment = voz_elevenlabs_con_timestamps(contenido["guion"], carpeta / "voz.mp3", voice_id)
    usage_store.registrar_voz(len(contenido["guion"]))

    brand = image_producer.obtener_brand(contenido["perfil"])
    duracion_voz = _duracion_archivo(voz)
    limites_segmentos = _limites_segmentos(contenido, duracion_voz)

    tiene_broll_por_tramo = any(contenido.get(f"broll_query_{s}") for s in SEGMENTOS_VIDEO)
    brolls = None
    if tiene_broll_por_tramo:
        brolls = []
        for campo, (ini, fin) in limites_segmentos.items():
            query = contenido.get(f"broll_query_{campo}") or contenido.get("broll_query", "technology vertical")
            dur_tramo = fin - ini
            n_tomas = _tomas_por_tramo(dur_tramo)
            dur_toma = dur_tramo / n_tomas
            for k in range(n_tomas):
                ruta = broll_pexels(query, carpeta / f"broll_{campo}_{k}.mp4", indice=k)
                brolls.append((ruta, dur_toma))
    else:
        broll = broll_pexels(contenido.get("broll_query", "technology vertical"), carpeta / "broll.mp4")

    palabras = _palabras_desde_alignment(alignment)
    overlays = []
    for i, (texto, ini, fin) in enumerate(_agrupar_subtitulos(palabras)):
        png = carpeta / f"caption_{i:02d}.png"
        png.write_bytes(image_producer.producir_caption_png(
            texto, estilo_visual, brand,
            texto_color=texto_color, fondo_activo=fondo_texto, fuente=fuente_texto,
        ))
        overlays.append((png, ini, fin))

    if brolls:
        salida = ensamblar_multi_broll(voz, brolls, carpeta / "video_9x16.mp4", 1080, 1920, overlays)
        for ruta, _ in brolls:
            ruta.unlink(missing_ok=True)
    else:
        salida = ensamblar_con_overlays(voz, broll, carpeta / "video_9x16.mp4", 1080, 1920, overlays)
    for png, _, _ in overlays:
        png.unlink(missing_ok=True)
    return salida


def producir_slide_video(slide: dict, brand: dict, estilo_visual: str, destino: Path) -> Path:
    """Produce una lámina de carrusel como video corto cuadrado (1080x1080) en
    vez de imagen estática — mismo diseño (skin) quemado encima del B-roll,
    para que se vea igual que su hermana imagen del mismo carrusel."""
    voice_id = config_store.cargar_voz()["voice_id"]
    texto = f"{slide.get('titular', '')}. {slide.get('cuerpo', '')}"
    voz = voz_elevenlabs(texto, destino.with_name(destino.stem + "_voz.mp3"), voice_id)
    usage_store.registrar_voz(len(texto))
    broll = broll_pexels(slide.get("broll_query") or "abstract technology background",
                         destino.with_name(destino.stem + "_broll.mp4"), orientation="square")
    overlay_png = destino.with_name(destino.stem + "_overlay.png")
    overlay_png.write_bytes(image_producer.producir_overlay_slide(brand, slide, estilo_visual))

    ensamblar_con_overlays(voz, broll, destino, 1080, 1080, [(overlay_png, 0, None)])
    for p in (voz, broll, overlay_png):
        p.unlink(missing_ok=True)
    return destino


def extraer_frame_mejor_momento(video_path: Path, contenido: dict = None) -> bytes:
    """Frame real del video ya producido, para usar como fondo de la historia
    en vez de un teaser genérico de color sólido — sin IA, $0, igual que el
    resto de producir_historia.

    NOTA: desde que el video quema subtítulos completos (cubren TODO lo
    narrado, sin huecos — ver `producir_video`), ya no existe un instante
    "libre de texto" que buscar: cualquier frame trae un subtítulo parcial
    quemado en la banda inferior. Por ahora se toma un punto fijo (30% del
    video) sin intentar evitarlo; si se ve mal como fondo de la historia,
    la solución real es recortar esa franja al componer el frame, no elegir
    otro instante (pendiente, no implementado)."""
    dur = float(
        subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(video_path),
        ]).strip()
    )
    t = dur * 0.3
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        ruta_tmp = Path(tmp.name)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video_path),
         "-frames:v", "1", "-q:v", "3", str(ruta_tmp)],
        check=True, capture_output=True,
    )
    data = ruta_tmp.read_bytes()
    ruta_tmp.unlink(missing_ok=True)
    return data
