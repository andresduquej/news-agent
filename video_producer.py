"""
Video Producer — Sprint 3 del Agente de Contenido.

Produce el video final 9:16 (1080x1920): voz ElevenLabs + B-roll de Pexels +
ensamblado FFmpeg. Pipeline validado en Sprint 0 (test_video_pipeline.py).

Subtítulos por ORACIÓN con palabra activa resaltada (1 ago 2026): antes se
agrupaba en bloques de `PALABRAS_POR_SUBTITULO` palabras fijas — cortaba a
mitad de frase, sin relación con el sentido del texto. Andrés pidió separar
por frases reales ("a medida que separa las frases, ese es el tiempo que
permanece la escena del video") y que se note la palabra que se está
diciendo en cada instante — mismo patrón ya resuelto en
avatarhype-studio/subtitulos.py, portado acá. Fix: `subtitulos_ass.py`
agrupa las palabras (con su timing real del alignment de ElevenLabs) en
oraciones completas (corta en . ! ? …, con tope de seguridad para texto sin
puntuación) y genera un .ass con libass — dentro de cada oración se resalta
SOLO la palabra activa, coloreada con el acento de marca, mientras el resto
del bloque queda en su color base. Se quema con el filtro `subtitles` de
ffmpeg como post-proceso, ya no con PNGs vía Playwright.

Ritmo de corte por ORACIÓN (1 ago 2026, reemplaza el corte por duración fija
del 30 jul): el B-roll cambia de toma en cada oración — mismo límite que los
subtítulos — en vez de una duración fija (~2.5s) desacoplada del texto. La
duración de cada toma es la duración REAL de esa oración en el audio.

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
import subtitulos_ass
import usage_store
from test_video_pipeline import (
    broll_pexels, ensamblar_multi_broll, ensamblar_con_overlays, voz_elevenlabs_con_timestamps,
)

BASE = Path(__file__).resolve().parent
OUT = BASE / "producciones"

SEGMENTOS_VIDEO = ("hook", "obstaculo", "ejecucion", "cta")
MAX_TOMAS_POR_TRAMO = 8  # tope para no disparar de más las llamadas a Pexels si el tramo tiene muchas oraciones cortas


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


def _oraciones_por_tramo(contenido: dict, palabras: list) -> dict:
    """Reparte `palabras` (alignment global, EN ORDEN — el mismo orden en que
    se concatenó "guion" = hook+obstaculo+ejecucion+cta) entre los tramos
    según su cantidad de palabras, y agrupa cada porción en oraciones
    completas. Devuelve {tramo: [(texto, ini, fin), ...]} — cada oración ya
    asociada a la query de B-roll de su tramo."""
    resultado = {}
    cursor = 0
    for campo in SEGMENTOS_VIDEO:
        texto = (contenido.get(campo) or "").strip()
        if not texto:
            continue
        n_palabras = len(texto.split())
        palabras_campo = palabras[cursor:cursor + n_palabras]
        cursor += n_palabras
        if palabras_campo:
            resultado[campo] = subtitulos_ass.agrupar_oraciones(palabras_campo)
    return resultado


def _duracion_archivo(ruta: Path) -> float:
    return float(
        subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(ruta),
        ]).strip()
    )


def _limites_oraciones_sin_huecos(oraciones_por_tramo: dict, duracion_audio: float) -> dict:
    """Cada oración por sí sola solo cubre desde el inicio de su primera
    palabra hasta el fin de su última — sumar esas duraciones para decidir
    cuánto dura cada toma de B-roll pierde las micro-pausas ENTRE oraciones
    (y entre tramos), así que la suma total quedaba por debajo de la
    duración real del audio y el video se cortaba antes de que terminara la
    narración (reportado por Andrés). Fix: el fin efectivo de cada oración
    es el INICIO de la oración siguiente (mismo criterio que ya se usa para
    que los subtítulos no parpadeen); la última oración de todo el guion se
    extiende hasta la duración REAL del archivo de audio (cubre también
    cualquier silencio final que deje ElevenLabs). Devuelve
    {tramo: [(ini, fin_efectivo), ...]}."""
    flat = [(campo, oracion) for campo in SEGMENTOS_VIDEO for oracion in oraciones_por_tramo.get(campo, [])]
    resultado = {campo: [] for campo in oraciones_por_tramo}
    for i, (campo, oracion) in enumerate(flat):
        ini = oracion[0][1]
        fin = flat[i + 1][1][0][1] if i + 1 < len(flat) else duracion_audio
        resultado[campo].append((ini, fin))
    return resultado


def _tomas_broll_desde_limites(limites: list) -> list:
    """[(ini, fin), ...] — una toma de B-roll por oración, salvo que el tramo
    tenga más oraciones que `MAX_TOMAS_POR_TRAMO` (texto muy fragmentado):
    ahí agrupa oraciones consecutivas en la misma toma para no disparar de
    más las llamadas a Pexels. `limites` ya viene sin huecos (ver
    `_limites_oraciones_sin_huecos`) — agrupar solo une límites contiguos,
    nunca reintroduce un hueco."""
    if len(limites) <= MAX_TOMAS_POR_TRAMO:
        return limites
    tomas = []
    paso = len(limites) / MAX_TOMAS_POR_TRAMO
    for k in range(MAX_TOMAS_POR_TRAMO):
        grupo = limites[round(k * paso):round((k + 1) * paso)] or limites[-1:]
        tomas.append((grupo[0][0], grupo[-1][1]))
    return tomas


def producir_video(contenido: dict, slug: str, estilo_visual: str = "editorial",
                   texto_color: str = "", fondo_texto: bool = True, fuente_texto: str = "") -> Path:
    """Genera el video para un contenido de formato 'video'. Devuelve la ruta MP4.
    Quema subtítulos por ORACIÓN completa (nunca corta a mitad de frase),
    con la palabra que se está diciendo en cada instante resaltada con el
    acento de marca — timing REAL del alignment de ElevenLabs, sin estimar
    nada. El B-roll cambia de toma en los mismos límites de oración (mismo
    "tiempo que permanece la escena" que pidió Andrés). `texto_color` pisa el
    color BASE del texto (el resaltado de la palabra activa sigue siendo el
    acento de marca); `fondo_texto` activa/desactiva la caja de fondo;
    `fuente_texto` no se usa por ahora — libass necesita una fuente
    instalada localmente y solo tenemos Poppins en fonts/.

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
    palabras = _palabras_desde_alignment(alignment)
    oraciones_por_tramo = _oraciones_por_tramo(contenido, palabras)
    duracion_audio = _duracion_archivo(voz)
    limites_por_tramo = _limites_oraciones_sin_huecos(oraciones_por_tramo, duracion_audio)

    tiene_broll_por_tramo = any(contenido.get(f"broll_query_{s}") for s in SEGMENTOS_VIDEO)
    brolls = None
    if tiene_broll_por_tramo:
        brolls = []
        for campo in SEGMENTOS_VIDEO:
            limites = limites_por_tramo.get(campo)
            if not limites:
                continue
            query = contenido.get(f"broll_query_{campo}") or contenido.get("broll_query", "technology vertical")
            for k, (ini, fin) in enumerate(_tomas_broll_desde_limites(limites)):
                ruta = broll_pexels(query, carpeta / f"broll_{campo}_{k}.mp4", indice=k,
                                    perfil=contenido.get("perfil", ""))
                brolls.append((ruta, max(fin - ini, 0.4)))
    else:
        broll = broll_pexels(contenido.get("broll_query", "technology vertical"), carpeta / "broll.mp4",
                             perfil=contenido.get("perfil", ""))

    bloques = [oracion for campo in SEGMENTOS_VIDEO for oracion in oraciones_por_tramo.get(campo, [])]
    ass_path = carpeta / "subtitulos.ass"
    subtitulos_ass.generar_ass(
        bloques, str(ass_path),
        color_texto=texto_color or "#FFFFFF", color_resaltado=brand["accent_color"],
        con_fondo=fondo_texto,
    )

    sin_subtitulos = carpeta / "_sin_subtitulos.mp4"
    if brolls:
        ensamblar_multi_broll(voz, brolls, sin_subtitulos, 1080, 1920)
        for ruta, _ in brolls:
            ruta.unlink(missing_ok=True)
    else:
        ensamblar_con_overlays(voz, broll, sin_subtitulos, 1080, 1920)

    salida = carpeta / "video_9x16.mp4"
    subtitulos_ass.quemar_subtitulos(str(sin_subtitulos), str(ass_path), str(salida))
    sin_subtitulos.unlink(missing_ok=True)
    ass_path.unlink(missing_ok=True)
    return salida


def producir_slide_video(slide: dict, brand: dict, estilo_visual: str, destino: Path,
                         perfil: str = "") -> Path:
    """Produce una lámina de carrusel como video corto cuadrado (1080x1080) en
    vez de imagen estática — mismo diseño (skin) quemado encima del B-roll,
    para que se vea igual que su hermana imagen del mismo carrusel."""
    voice_id = config_store.cargar_voz()["voice_id"]
    texto = f"{slide.get('titular', '')}. {slide.get('cuerpo', '')}"
    voz = voz_elevenlabs(texto, destino.with_name(destino.stem + "_voz.mp3"), voice_id)
    usage_store.registrar_voz(len(texto))
    broll = broll_pexels(slide.get("broll_query") or "abstract technology background",
                         destino.with_name(destino.stem + "_broll.mp4"), orientation="square",
                         perfil=perfil)
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
