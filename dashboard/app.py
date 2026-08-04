import json
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import calendario_store
import calidad_video
import config_store
import errores as errores_mod
import evergreen_store
import fondo_producer
import generator
import generator_ia
import history_store
import image_producer
import investigacion
import llm_client
import matriz_viralidad
import metricas_store
import news_fetcher
import ranker
import ranker_ia
import referentes as referentes_mod
import resumen as resumen_mod
import series_store
import topics_store
import usage_store
import video_producer

app = FastAPI(title="Agente de Contenido — HAM Agencia")
app.mount("/assets", StaticFiles(directory=BASE / "assets"), name="assets")
(BASE / "producciones").mkdir(exist_ok=True)
app.mount("/producciones", StaticFiles(directory=BASE / "producciones"), name="producciones")


class TopicIn(BaseModel):
    name: str
    query: str = ""


class ToggleIn(BaseModel):
    active: bool


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/brands")
def brands():
    return json.loads((BASE / "brand_config.json").read_text())


@app.get("/api/topics")
def topics():
    return topics_store.load()


@app.post("/api/topics")
def topics_add(topic: TopicIn):
    return topics_store.add(topic.name, topic.query)


@app.delete("/api/topics/{name}")
def topics_remove(name: str):
    return topics_store.remove(name)


@app.patch("/api/topics/{name}")
def topics_toggle(name: str, body: ToggleIn):
    return topics_store.toggle(name, body.active)


@app.get("/api/news")
def news():
    noticias = []
    for t in topics_store.active_topics():
        noticias.extend(news_fetcher.fetch_topic(t["name"], t["query"]))
    rankeadas = ranker.rank(noticias)[:10]  # top 10, ya ordenadas por relevancia
    for n in rankeadas:
        n["formato_sugerido"] = generator.detectar_formato(n)
    return rankeadas


@app.get("/api/rank-ia")
def rank_ia():
    noticias = []
    for t in topics_store.active_topics():
        noticias.extend(news_fetcher.fetch_topic(t["name"], t["query"]))
    filtradas = ranker.rank(noticias)
    try:
        return ranker_ia.rank_ia(filtradas)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("rank_ia", str(e))
        return JSONResponse({"error": f"Error en el ranking con IA: {e}"}, status_code=502)


class InvestigarIn(BaseModel):
    tema: str
    perfil: str = ""


@app.post("/api/investigar")
def investigar(body: InvestigarIn):
    if not body.tema.strip():
        return JSONResponse({"error": "Escribí un tema para investigar"}, status_code=400)
    try:
        return investigacion.investigar(body.tema.strip(), body.perfil)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("investigar", str(e))
        return JSONResponse({"error": f"No se pudo investigar el tema: {e}"}, status_code=502)


@app.post("/api/referentes")
async def analizar_referentes(
    perfil: str = Form(""),
    links: str = Form("[]"),
    archivos: list[UploadFile] = File(default=[]),
):
    import tempfile

    try:
        urls = json.loads(links)
    except json.JSONDecodeError:
        urls = []
    fuentes = [{"tipo": "url", "valor": u.strip()} for u in urls if u.strip()]

    tmp_paths = []
    try:
        for archivo in archivos:
            if not archivo.filename:
                continue
            sufijo = Path(archivo.filename).suffix or ".mp4"
            tmp = tempfile.NamedTemporaryFile(suffix=sufijo, delete=False)
            tmp.write(await archivo.read())
            tmp.close()
            tmp_paths.append(tmp.name)
            fuentes.append({"tipo": "archivo", "valor": tmp.name})

        if not fuentes:
            return JSONResponse({"error": "Pasá al menos un link o subí un archivo de video"}, status_code=400)

        return referentes_mod.analizar_referentes(fuentes, perfil)
    except referentes_mod.ReferentesError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("referentes", str(e))
        return JSONResponse({"error": f"No se pudo analizar los referentes: {e}"}, status_code=502)
    finally:
        for p in tmp_paths:
            Path(p).unlink(missing_ok=True)


class ResumenIn(BaseModel):
    url: str
    titulo: str
    contexto: str = ""


@app.post("/api/resumen")
def resumen(body: ResumenIn):
    try:
        return resumen_mod.obtener_resumen(body.url, body.titulo, body.contexto)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("resumen", str(e))
        return JSONResponse({"error": f"No se pudo generar el resumen: {e}"}, status_code=502)


class GenerarIn(BaseModel):
    noticia: dict
    formato: str
    perfil: str
    num_slides: int = 0
    duracion_seg: int = 0
    plataforma: str = ""
    ritmo_corte: str = "medio"
    musica: str = "upbeat"
    velocidad_narracion: str = "rapida"
    zoom_camara: bool = True


class VariantesSegmentoIn(BaseModel):
    contenido: dict
    perfil: str
    campo: str  # video: "hook"|"obstaculo"|"ejecucion"|"cta" — carrusel: índice de slide (string numérico) — imagen: se ignora
    n: int = 3


class ProducirIn(BaseModel):
    contenido: dict
    formato_imagen: str = "vertical"  # "cuadrado" | "vertical" — solo aplica a formato 'imagen'; los carruseles siempre son cuadrados
    mostrar_logo: bool = True
    logo_data_uri: str = ""  # PNG subido por el usuario (data-URI) — reemplaza el logo de marca solo para esta producción
    video_slides: list[int] = []  # solo carrusel: láminas (1-indexado) a producir como video corto en vez de imagen
    estilo_visual: str = "editorial"  # "editorial" | "prensa_ia" — ver image_producer.ESTILOS_VISUALES
    video_url: str = ""  # solo /api/producir-historia con formato 'video': ruta del video ya producido (para sacarle un frame real)
    texto_color: str = ""  # solo formato 'video': pisa el color del texto en pantalla (hex) — "" = default del skin
    fondo_texto: bool = True  # solo formato 'video': False = texto sin caja de fondo (solo con sombra)
    fuente_texto: str = ""  # solo formato 'video': "sans" | "serif" — "" = default del skin
    fondo_animado: bool = False  # solo imagen suelta/historia: mp4 con fondo en movimiento en vez de PNG estático
    fuente_fondo: str = "pexels"  # "pexels" (banco libre de derechos) | "ia" (Gemini + Ken Burns)
    fondo_query: str = ""  # búsqueda (pexels) o prompt (ia) del fondo — "" = usa el título de la pieza
    test_id: str = ""  # agrupa esta pieza con sus hermanas de un mismo test de variantes en /history
    test_variante: str = ""  # etiqueta de la variante dentro del test (ej. "Hook 2 · CTA 1")
    prediccion: str = ""  # expectativa del usuario antes de publicar (texto libre) — se compara luego contra el resultado real en /history


def _slug(texto: str) -> str:
    import re
    import time
    limpio = re.sub(r"[^a-z0-9]+", "-", texto.lower())[:40].strip("-")
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{limpio}"


@app.post("/api/generar")
def generar(body: GenerarIn):
    try:
        return generator_ia.generar_contenido(
            body.noticia, body.formato, body.perfil, body.num_slides, body.duracion_seg,
            body.plataforma, body.ritmo_corte, body.musica, body.velocidad_narracion,
            body.zoom_camara,
        )
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("generar", str(e))
        return JSONResponse({"error": f"No se pudo generar el contenido: {e}"}, status_code=502)


@app.post("/api/generar-variantes-segmento")
def generar_variantes_segmento(body: VariantesSegmentoIn):
    try:
        return {"variantes": generator_ia.generar_variantes_segmento(
            body.contenido, body.perfil, body.campo, body.n
        )}
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("generar_variantes_segmento", str(e))
        return JSONResponse({"error": f"No se pudieron generar variantes: {e}"}, status_code=502)


@app.post("/api/producir-imagen")
def producir_imagen(body: ProducirIn):
    import os
    if body.video_slides:
        faltan = [k for k in ("ELEVENLABS_API_KEY", "PEXELS_API_KEY") if not os.environ.get(k)]
        if faltan:
            return JSONResponse(
                {"error": f"Faltan claves para las láminas de video: {', '.join(faltan)} — configuralas en /config"},
                status_code=503,
            )
    if body.fondo_animado and body.contenido.get("formato") != "carrusel":
        clave_necesaria = "GEMINI_API_KEY" if body.fuente_fondo == "ia" else "PEXELS_API_KEY"
        if not os.environ.get(clave_necesaria):
            return JSONResponse(
                {"error": f"Falta configurar {clave_necesaria} para el fondo animado — configurala en /config"},
                status_code=503,
            )
        try:
            slug = _slug(body.contenido.get("titulo", "contenido"))
            destino = fondo_producer.producir_imagen_animada(
                body.contenido, slug, body.formato_imagen, body.estilo_visual,
                body.fuente_fondo, body.fondo_query,
            )
            archivos = [f"/producciones/{slug}/{destino.name}"]
            history_store.registrar(slug, body.contenido, archivos, prediccion=body.prediccion)
            return {"archivos": archivos}
        except Exception as e:
            errores_mod.log("producir_imagen_animada", str(e))
            return JSONResponse({"error": f"No se pudo renderizar el fondo animado: {e}"}, status_code=502)
    try:
        slug = _slug(body.contenido.get("titulo", "contenido"))
        rutas = image_producer.producir_imagen(
            body.contenido, slug, body.formato_imagen, body.mostrar_logo, body.logo_data_uri,
            body.video_slides, body.estilo_visual,
        )
        avisos = []
        if body.video_slides and body.contenido.get("formato") == "carrusel":
            carpeta = BASE / "producciones" / slug
            slides = body.contenido["slides"]
            brand = image_producer.obtener_brand(body.contenido["perfil"])
            for i in body.video_slides:
                s = slides[i - 1]
                destino = carpeta / f"slide_{i:02d}.mp4"
                video_producer.producir_slide_video(s, brand, body.estilo_visual, destino)
                gate = calidad_video.evaluar(destino)
                if not gate["aprobado"]:
                    calidad_video.rechazar_archivo(destino)
                    errores_mod.log("gate_calidad_video", f"{slug} slide {i}: " + " | ".join(gate["motivos"]))
                    avisos.append(f"Lámina {i} rechazada por el chequeo de calidad: " + " ".join(gate["motivos"]))
                    continue
                rutas.append(destino)
            rutas.sort(key=lambda r: r.name)
        archivos = [f"/producciones/{slug}/{r.name}" for r in rutas]
        history_store.registrar(slug, body.contenido, archivos, prediccion=body.prediccion)
        return {"archivos": archivos, "avisos": avisos}
    except Exception as e:
        errores_mod.log("producir_imagen", str(e))
        return JSONResponse({"error": f"No se pudo renderizar: {e}"}, status_code=502)


@app.post("/api/producir-historia")
def producir_historia(body: ProducirIn):
    import os
    # si el formato es 'video' con video_url, gana el flujo de "frame real del
    # video" (ver producir_historia_con_frame) — fondo_animado no aplica ahí,
    # solo para historias de imagen/carrusel.
    if body.fondo_animado and not (body.contenido.get("formato") == "video" and body.video_url):
        clave_necesaria = "GEMINI_API_KEY" if body.fuente_fondo == "ia" else "PEXELS_API_KEY"
        if not os.environ.get(clave_necesaria):
            return JSONResponse(
                {"error": f"Falta configurar {clave_necesaria} para el fondo animado — configurala en /config"},
                status_code=503,
            )
        try:
            slug = _slug(body.contenido.get("titulo", "historia")) + "-historia"
            destino = fondo_producer.producir_historia_animada(
                body.contenido, slug, body.estilo_visual, body.fuente_fondo, body.fondo_query,
            )
            archivos = [f"/producciones/{slug}/{destino.name}"]
            history_store.registrar(slug, body.contenido, archivos)
            return {"archivos": archivos}
        except Exception as e:
            errores_mod.log("producir_historia_animada", str(e))
            return JSONResponse({"error": f"No se pudo generar la historia animada: {e}"}, status_code=502)
    try:
        slug = _slug(body.contenido.get("titulo", "historia")) + "-historia"
        if body.contenido.get("formato") == "video" and body.video_url:
            video_path = BASE / body.video_url.lstrip("/")
            frame = video_producer.extraer_frame_mejor_momento(
                video_path, body.contenido
            )
            ruta = image_producer.producir_historia_con_frame(
                body.contenido, slug, frame, body.mostrar_logo, body.logo_data_uri
            )
        else:
            ruta = image_producer.producir_historia(
                body.contenido, slug, body.mostrar_logo, body.logo_data_uri, body.estilo_visual
            )
        archivos = [f"/producciones/{slug}/{ruta.name}"]
        history_store.registrar(slug, body.contenido, archivos)
        return {"archivos": archivos}
    except Exception as e:
        errores_mod.log("producir_historia", str(e))
        return JSONResponse({"error": f"No se pudo generar la historia: {e}"}, status_code=502)


@app.post("/api/producir-video")
def producir_video(body: ProducirIn):
    import os
    faltan = [k for k in ("ELEVENLABS_API_KEY", "PEXELS_API_KEY") if not os.environ.get(k)]
    if faltan:
        return JSONResponse(
            {"error": f"Faltan claves: {', '.join(faltan)} — configuralas en /config"},
            status_code=503,
        )
    try:
        slug = _slug(body.contenido.get("titulo", "video"))
        ruta = video_producer.producir_video(
            body.contenido, slug, body.estilo_visual,
            body.texto_color, body.fondo_texto, body.fuente_texto,
        )
        gate = calidad_video.evaluar(ruta, body.contenido)
        if not gate["aprobado"]:
            calidad_video.rechazar_archivo(ruta)
            errores_mod.log("gate_calidad_video", f"{slug}: " + " | ".join(gate["motivos"]))
            return JSONResponse(
                {"error": "El video no pasó el chequeo de calidad y fue rechazado: " + " ".join(gate["motivos"])},
                status_code=422,
            )
        archivos = [f"/producciones/{slug}/{ruta.name}"]
        history_store.registrar(slug, body.contenido, archivos, body.test_id, body.test_variante, body.prediccion)
        return {"archivos": archivos}
    except Exception as e:
        errores_mod.log("producir_video", str(e))
        return JSONResponse({"error": f"No se pudo producir el video: {e}"}, status_code=502)


@app.get("/api/history")
def history_list():
    return history_store.listar()


@app.delete("/api/history/{slug}")
def history_delete(slug: str):
    history_store.eliminar(slug)
    return {"ok": True}


@app.get("/history", response_class=HTMLResponse)
def history_page():
    return (Path(__file__).parent / "history.html").read_text()


# ---------------------------------------------------------------------------
# Banco evergreen: noticias/ángulos que no caducan, para días flojos
# ---------------------------------------------------------------------------

class EvergreenIn(BaseModel):
    noticia: dict
    nota: str = ""


@app.get("/api/evergreen")
def evergreen_listar():
    return evergreen_store.listar()


@app.post("/api/evergreen")
def evergreen_agregar(body: EvergreenIn):
    return evergreen_store.agregar(body.noticia, body.nota)


@app.delete("/api/evergreen/{entry_id}")
def evergreen_eliminar(entry_id: str):
    if not evergreen_store.eliminar(entry_id):
        return JSONResponse({"error": "No existe ese registro"}, status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Calendario: planificador de contenido semanal (qué publicar cada día)
# ---------------------------------------------------------------------------

@app.get("/calendario", response_class=HTMLResponse)
def calendario_page():
    return (Path(__file__).parent / "calendario.html").read_text()


@app.get("/api/calendario/config")
def calendario_config():
    config = calendario_store.cargar_config()
    config["canales_disponibles"] = calendario_store.CANALES_DISPONIBLES
    return config


class CalendarioConfigIn(BaseModel):
    canales: list[str]
    objetivo_semanal: dict[str, int]


@app.put("/api/calendario/config")
def calendario_guardar_config(body: CalendarioConfigIn):
    return calendario_store.guardar_config(body.canales, body.objetivo_semanal)


@app.get("/api/calendario")
def calendario_semana(semana: str = ""):
    lunes = calendario_store.lunes_de(semana) if semana else calendario_store.semana_actual()
    return {"lunes": lunes, "slots": calendario_store.listar_semana(lunes)}


class CalendarioGenerarIn(BaseModel):
    semana: str = ""
    forzar: bool = False


@app.post("/api/calendario/generar")
def calendario_generar(body: CalendarioGenerarIn):
    lunes = calendario_store.lunes_de(body.semana) if body.semana else calendario_store.semana_actual()
    return {"lunes": lunes, "slots": calendario_store.generar_semana(lunes, body.forzar)}


class CalendarioSlotIn(BaseModel):
    fecha: str
    formato: str
    canal: str
    tema: str = ""


@app.post("/api/calendario/slots")
def calendario_agregar_slot(body: CalendarioSlotIn):
    return calendario_store.agregar_slot(body.fecha, body.formato, body.canal, body.tema)


class CalendarioSlotEditIn(BaseModel):
    fecha: str = None
    formato: str = None
    canal: str = None
    tema: str = None
    estado: str = None
    slug: str = None


@app.patch("/api/calendario/slots/{slot_id}")
def calendario_editar_slot(slot_id: str, body: CalendarioSlotEditIn):
    cambios = {k: v for k, v in body.model_dump().items() if v is not None}
    slot = calendario_store.editar_slot(slot_id, cambios)
    if not slot:
        return JSONResponse({"error": "No existe ese slot"}, status_code=404)
    return slot


@app.delete("/api/calendario/slots/{slot_id}")
def calendario_eliminar_slot(slot_id: str):
    if not calendario_store.eliminar_slot(slot_id):
        return JSONResponse({"error": "No existe ese slot"}, status_code=404)
    return {"ok": True}


class SerieIn(BaseModel):
    nombre: str
    dia_semana: int
    tema: str = ""
    formato: str = ""
    canal: str = ""


class SerieEditIn(BaseModel):
    nombre: str = None
    dia_semana: int = None
    tema: str = None
    formato: str = None
    canal: str = None
    activa: bool = None


@app.get("/api/series")
def series_listar():
    return {"series": series_store.listar(), "dias_semana": series_store.DIAS_SEMANA}


@app.post("/api/series")
def series_crear(body: SerieIn):
    return series_store.crear(body.nombre, body.dia_semana, body.tema, body.formato, body.canal)


@app.patch("/api/series/{serie_id}")
def series_editar(serie_id: str, body: SerieEditIn):
    cambios = {k: v for k, v in body.model_dump().items() if v is not None}
    serie = series_store.editar(serie_id, cambios)
    if not serie:
        return JSONResponse({"error": "No existe esa serie"}, status_code=404)
    return serie


@app.delete("/api/series/{serie_id}")
def series_eliminar(serie_id: str):
    if not series_store.eliminar(serie_id):
        return JSONResponse({"error": "No existe esa serie"}, status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Métricas: qué resultado dio cada pieza publicada (registro manual)
# ---------------------------------------------------------------------------

class MetricasIn(BaseModel):
    likes: int = 0
    comentarios: int = 0
    guardados: int = 0
    compartidos: int = 0
    alcance: int = 0


@app.get("/api/metricas")
def metricas_listar():
    return metricas_store.listar()


@app.put("/api/metricas/{slug}")
def metricas_registrar(slug: str, body: MetricasIn):
    return metricas_store.registrar(
        slug, body.likes, body.comentarios, body.guardados, body.compartidos, body.alcance
    )


@app.delete("/api/metricas/{slug}")
def metricas_eliminar(slug: str):
    if not metricas_store.eliminar(slug):
        return JSONResponse({"error": "No existe ese registro"}, status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Matriz de viralidad: detecta patrones en piezas propias con métricas
# cargadas, y simula si un guion nuevo va a funcionar antes de producirlo.
# ---------------------------------------------------------------------------

@app.get("/api/matriz")
def matriz_obtener(perfil: str = ""):
    return matriz_viralidad.obtener_matriz(perfil) or {}


class MatrizGenerarIn(BaseModel):
    perfil: str = ""


@app.post("/api/matriz/generar")
def matriz_generar(body: MatrizGenerarIn):
    try:
        return matriz_viralidad.generar_matriz(body.perfil)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("matriz_generar", str(e))
        return JSONResponse({"error": f"No se pudo generar la matriz: {e}"}, status_code=502)


class MatrizSimularIn(BaseModel):
    perfil: str = ""
    texto: str


@app.post("/api/matriz/simular")
def matriz_simular(body: MatrizSimularIn):
    try:
        return matriz_viralidad.simular_guion(body.texto, body.perfil)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    except llm_client.LLMError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        errores_mod.log("matriz_simular", str(e))
        return JSONResponse({"error": f"No se pudo simular: {e}"}, status_code=502)


# ---------------------------------------------------------------------------
# Configuración: claves API, modelo de IA por tarea, marcas, gastos, errores
# ---------------------------------------------------------------------------

class ClaveIn(BaseModel):
    proveedor: str
    valor: str


class ModeloIn(BaseModel):
    tarea: str
    proveedor: str
    modelo: str


class MarcaIn(BaseModel):
    brand_name: str
    primary_color: str
    secondary_color: str
    accent_color: str
    tone_of_voice: str
    target_audience: str
    cta_default: str
    hashtags_base: list


class VozIn(BaseModel):
    voice_id: str
    nombre: str


@app.get("/api/config/voces")
def config_voces():
    import os
    actual = config_store.cargar_voz()
    if not os.environ.get("ELEVENLABS_API_KEY"):
        return {"actual": actual, "disponibles": [], "error": "Falta configurar ELEVENLABS_API_KEY"}
    try:
        import requests
        r = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            timeout=20,
        )
        r.raise_for_status()
        voces = [
            {
                "voice_id": v["voice_id"],
                "nombre": v["name"],
                "preview_url": v.get("preview_url"),
                "categoria": v.get("category", ""),
                "genero": v.get("labels", {}).get("gender", ""),
                "acento": v.get("labels", {}).get("accent", ""),
                "descripcion": v.get("labels", {}).get("description", ""),
            }
            for v in r.json().get("voices", [])
        ]
        return {"actual": actual, "disponibles": voces}
    except Exception as e:
        errores_mod.log("config_voces", str(e))
        return JSONResponse({"error": f"No se pudieron listar las voces: {e}"}, status_code=502)


@app.post("/api/config/voces")
def config_set_voz(body: VozIn):
    return config_store.set_voz(body.voice_id, body.nombre)


@app.get("/api/config/claves")
def config_claves():
    return config_store.listar_claves()


@app.post("/api/config/claves")
def config_guardar_clave(body: ClaveIn):
    try:
        config_store.guardar_clave(body.proveedor, body.valor)
        return {"ok": True}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.delete("/api/config/claves/{proveedor}")
def config_borrar_clave(proveedor: str):
    try:
        config_store.borrar_clave(proveedor)
        return {"ok": True}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/config/modelos")
def config_modelos():
    return {"tareas": config_store.cargar_ia_config(), "proveedores": config_store.PROVEEDORES_IA}


@app.get("/api/config/modelos/{proveedor}")
def config_modelos_proveedor(proveedor: str):
    if proveedor not in config_store.PROVEEDORES_IA:
        return JSONResponse({"error": f"Proveedor inválido: {proveedor}"}, status_code=400)
    return llm_client.listar_modelos(proveedor)


@app.post("/api/config/modelos")
def config_set_modelo(body: ModeloIn):
    try:
        return config_store.set_tarea(body.tarea, body.proveedor, body.modelo)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.put("/api/config/marcas/{perfil}")
def config_guardar_marca(perfil: str, body: MarcaIn):
    ruta = BASE / "brand_config.json"
    marcas = json.loads(ruta.read_text())
    if perfil not in marcas:
        return JSONResponse({"error": f"Perfil desconocido: {perfil}"}, status_code=404)
    marcas[perfil].update(body.model_dump())
    ruta.write_text(json.dumps(marcas, ensure_ascii=False, indent=2))
    return marcas[perfil]


@app.get("/api/config/gastos")
def config_gastos(herramienta: str = "", tarea: str = "", limite: int = 5):
    return usage_store.resumen(herramienta, tarea, limite)


@app.delete("/api/config/gastos/{entry_id}")
def config_borrar_gasto(entry_id: str):
    if not usage_store.eliminar(entry_id):
        return JSONResponse({"error": "No existe ese registro"}, status_code=404)
    return {"ok": True}


@app.delete("/api/config/gastos")
def config_vaciar_gastos():
    usage_store.eliminar_todo()
    return {"ok": True}


@app.get("/api/config/gastos/exportar")
def config_exportar_gastos():
    return Response(
        content=usage_store.exportar_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gastos.csv"},
    )


@app.get("/api/config/errores")
def config_errores():
    return errores_mod.listar()


@app.delete("/api/config/errores")
def config_limpiar_errores():
    errores_mod.limpiar()
    return {"ok": True}


@app.get("/config", response_class=HTMLResponse)
def config_page():
    return (Path(__file__).parent / "config.html").read_text()


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "index.html").read_text()
