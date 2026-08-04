"""
Generator IA — Sprint 3 del Agente de Contenido.

Genera el contenido final para una noticia según el formato y el perfil de
marca (brand_config.json): guión (video) / copy slide a slide (carrusel) /
headline+copy (imagen), más caption y hashtags — con el tono de la marca.

Estructura obligatoria (los 4 tramos del video son fijos por compatibilidad con el
resto del pipeline — multi-B-roll por tramo, overlays, variantes por segmento — pero
el CONTENIDO de cada tramo varía de patrón según lo que mejor calce, ver
`patrones_video_referentes.md` — 28 jul 2026, análisis de 75 reels reales del nicho):
  - video: HOOK (0-3s) -> OBSTÁCULO (3-15s) -> EJECUCIÓN (15-25s) -> CTA (últimos
    5s, opcional — puede quedar vacío si el contenido es solo informativo). El HOOK
    puede ser problema directo / afirmación audaz / pregunta / dato de impacto, no
    siempre "el resultado". El CTA favorece "comentá PALABRA y te lo mando" cuando
    hay un recurso para entregar — es el patrón con mejor respuesta real del nicho.
  - carrusel: slide 1 = hook/portada, slide 2 = obstáculo, slides intermedios =
    desarrollo (una idea por slide), penúltimo = resultado/prueba, último = CTA.

Usa el proveedor/modelo configurado para la tarea "generacion" en Configuración.
"""

import json
from pathlib import Path

import llm_client
import ranker_ia  # reutiliza la carga de .env

BASE = Path(__file__).resolve().parent

SCHEMAS = {
    "video": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Título gancho del video, máx 8 palabras"},
            "hook": {"type": "string",
                     "description": "[0-3s] Gancho que detiene el scroll — elegí el patrón que mejor "
                                    "calce con ESTA noticia, no siempre el mismo: (a) nombrar el "
                                    "problema/dolor exacto de la audiencia de entrada (ej. 'Tu "
                                    "contenido tiene buenas vistas pero no vende'), (b) una afirmación "
                                    "audaz que desafíe una creencia instalada (ej. 'Ya no necesitás "
                                    "pagar por edición'), (c) una pregunta directa que obligue a "
                                    "autoevaluarse, o (d) prometer un dato/resultado concreto ('Así "
                                    "bajamos el CAC un 40%'). Nunca fuerces la variante (d) si la "
                                    "noticia no tiene una cifra de impacto real."},
            "obstaculo": {"type": "string",
                          "description": "[3-15s] Exposición del caos, el problema técnico o el dolor "
                                         "puntual que tenía el cliente antes de la intervención. Si el "
                                         "hook ya fue tipo (a)/(b)/(c) de arriba, este tramo puede pasar "
                                         "directo a por qué importa en vez de re-explicar el mismo dolor"},
            "ejecucion": {"type": "string",
                          "description": "[15-25s] Demostración visual, rápida y al grano de la "
                                         "estrategia o arquitectura implementada para resolver eso — "
                                         "la SOLUCIÓN concreta y accionable al problema planteado antes, "
                                         "no una descripción abstracta"},
            "cta": {"type": "string",
                    "description": "[últimos 5s] NO todos los videos venden algo — juzgá según el "
                                   "contenido: (1) si hay un recurso/guía/plantilla real para entregar, "
                                   "'Comentá [PALABRA] y te lo mando' es lo más efectivo (genera "
                                   "comentarios reales, no solo clics); (2) si el contenido es "
                                   "informativo pero vale la pena que sigan la cuenta, un simple "
                                   "'Síguenos para más contenido así' alcanza — no fuerces un giveaway "
                                   "que no existe; (3) otras opciones puntuales: link en bio, DM, "
                                   "agendar una auditoría, pedir que guarden la pieza. Cadena vacía "
                                   "SOLO si de verdad no amerita ningún cierre (raro)"},
            "broll_query": {"type": "string",
                            "description": "2-4 palabras EN INGLÉS para buscar B-roll GENERAL — "
                                           "respaldo si falla alguna de las búsquedas específicas "
                                           "por tramo de abajo. Si la escena incluye una persona, "
                                           "agregá 'latin american' o 'hispanic' a la query (ej. "
                                           "'latin american woman working laptop') — la audiencia es "
                                           "LatAm, nunca dejes que el B-roll salga con gente que no "
                                           "represente a la audiencia"},
            "broll_query_hook": {"type": "string",
                                 "description": "2-4 palabras EN INGLÉS para el B-roll del tramo "
                                                "HOOK — visualmente distinto de los otros 3 tramos, "
                                                "coherente con lo que se dice en ESE momento. Si hay "
                                                "una persona en escena, agregá 'latin american'/"
                                                "'hispanic' a la query"},
            "broll_query_obstaculo": {"type": "string",
                                      "description": "2-4 palabras EN INGLÉS para el B-roll del "
                                                     "tramo OBSTÁCULO — distinto de los otros tramos. "
                                                     "Si hay una persona en escena, agregá 'latin "
                                                     "american'/'hispanic' a la query"},
            "broll_query_ejecucion": {"type": "string",
                                      "description": "2-4 palabras EN INGLÉS para el B-roll del "
                                                     "tramo EJECUCIÓN — distinto de los otros tramos. "
                                                     "Si hay una persona en escena, agregá 'latin "
                                                     "american'/'hispanic' a la query"},
            "broll_query_cta": {"type": "string",
                                "description": "2-4 palabras EN INGLÉS para el B-roll del tramo "
                                               "CTA — distinto de los otros tramos. Si hay una "
                                               "persona en escena, agregá 'latin american'/'hispanic' "
                                               "a la query"},
            "caption": {"type": "string", "description": "Caption para el post, 2-3 frases"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["titulo", "hook", "obstaculo", "ejecucion", "cta",
                     "broll_query", "broll_query_hook", "broll_query_obstaculo",
                     "broll_query_ejecucion", "broll_query_cta",
                     "caption", "hashtags"],
    },
    "carrusel": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Título del carrusel"},
            "slides": {
                "type": "array",
                "description": "Slide 1 = hook/portada, slide 2 = obstáculo, slides intermedios = "
                               "desarrollo (una idea por slide), penúltimo = resultado/prueba, "
                               "último = CTA.",
                "items": {
                    "type": "object",
                    "properties": {
                        "rol": {"type": "string",
                                "enum": ["hook", "obstaculo", "desarrollo", "resultado", "cta"],
                                "description": "Qué función cumple este slide en la estructura"},
                        "titular": {"type": "string", "description": "Titular corto del slide"},
                        "cuerpo": {"type": "string", "description": "Texto de apoyo, máx 25 palabras"},
                        "broll_query": {"type": "string",
                                        "description": "2-4 palabras EN INGLÉS para buscar B-roll en "
                                                        "Pexels, por si esta lámina se produce como "
                                                        "video corto en vez de imagen estática"},
                    },
                    "required": ["rol", "titular", "cuerpo", "broll_query"],
                },
            },
            "caption": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["titulo", "slides", "caption", "hashtags"],
    },
    "imagen": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Headline principal de la imagen, máx 12 palabras"},
            "cuerpo": {"type": "string", "description": "Texto de apoyo, máx 35 palabras"},
            "caption": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["titulo", "cuerpo", "caption", "hashtags"],
    },
}

DEFAULT_SLIDES = 10

VARIANTES_SCHEMA = {
    "type": "object",
    "properties": {
        "variantes": {
            "type": "array",
            "description": "Hooks alternativos, cada uno con un ángulo distinto "
                           "(dato duro, pregunta, contrarian, urgencia, curiosidad)",
            "items": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string", "description": "El hook/titular alternativo"},
                    "cuerpo": {"type": "string",
                               "description": "Solo si el formato lo requiere (slide de carrusel): "
                                              "texto de apoyo corto para ese hook. Vacío si no aplica."},
                    "angulo": {"type": "string", "description": "Nombre corto del ángulo usado, ej. 'dato duro'"},
                },
                "required": ["texto", "angulo"],
            },
        }
    },
    "required": ["variantes"],
}

PLATAFORMA_INSTR = {
    "tiktok": "\n\nAdaptá el tono para TikTok: hook agresivo y directo desde el segundo 0, "
              "lenguaje coloquial, frases cortas, ritmo de cortes rápido.",
    "instagram": "\n\nAdaptá el tono para Instagram: hook de valor (aporta algo concreto desde "
                 "el primer segundo, sin gritar), redacción más pulida, se permite algo más de "
                 "desarrollo/duración.",
}

RITMO_CORTE_LABEL = {"alto": "alto (viral, corte cada 1-2s)", "medio": "medio",
                      "bajo": "bajo (educativo, corte cada 4-6s)"}
MUSICA_LABEL = {"upbeat": "upbeat/energética", "tension": "tensión/tambores",
                 "calma": "calma/ambiental"}
VELOCIDAD_LABEL = {"rapida": "rápida (energía)", "pausada": "pausada (autoridad)"}


def _instruccion_parametros(ritmo_corte: str, musica: str, velocidad_narracion: str,
                            zoom_camara: bool) -> str:
    """Traduce los parámetros de producción elegidos por el usuario en instrucciones
    de REDACCIÓN para el LLM (afecta el ritmo/tono del guion, no el render automático)."""
    partes = []
    if velocidad_narracion == "pausada":
        partes.append("Redactá con frases más largas y pausadas, tono de autoridad, sin apuro.")
    else:
        partes.append("Redactá con frases cortas y directas, ritmo ágil, tono con energía.")
    if ritmo_corte == "alto":
        partes.append("Pensá el guion en bloques muy cortos (1-2s c/u) aptos para cortes rápidos.")
    elif ritmo_corte == "bajo":
        partes.append("Pensá el guion en bloques más largos y explicativos (4-6s c/u), tono educativo.")
    if not partes:
        return ""
    return "\n\n" + " ".join(partes)


def _brand(perfil: str) -> dict:
    return json.loads((BASE / "brand_config.json").read_text())[perfil]


PALABRAS_POR_SEGUNDO = 2.7  # narración en español, ritmo natural


BEAT_DESC = {
    "hook": "HOOK (la portada): título de alto contraste o noticia de última hora que "
            "detiene el scroll de inmediato.",
    "obstaculo": "EL OBSTÁCULO (la agitación): exposición rápida del caos actual, el "
                 "error o el dolor específico del lector — que sienta 'eso me pasa a mí'.",
    "desarrollo": "EL DESARROLLO (la ejecución): una sola idea, paso, diagrama o dato "
                  "por lámina — directo al grano, sin saturar de texto.",
    "resultado": "EL RESULTADO (la prueba): el impacto real, dato duro de validación o "
                 "métrica que respalda lo anterior.",
    "cta": "CTA (la conversión): acción concreta e inmediata (ej. comentar una palabra "
           "clave para activar el bot, escribir al DM, agendar una auditoría). Si el "
           "contenido es puramente informativo, cierra con una conclusión de valor en "
           "vez de forzar una acción de venta.",
}


def _plan_beats(n: int) -> list:
    """Estructura de roles por cantidad de láminas (spec: Express/Corto/Medio/Expansión)."""
    if n <= 3:
        return ["hook", "desarrollo", "cta"]
    if n == 4:
        return ["hook", "obstaculo", "desarrollo", "cta"]
    if n == 5:
        return ["hook", "obstaculo", "desarrollo", "resultado", "cta"]
    # 6-9+: el desarrollo se expande en más pasos, resultado y cta siempre al final
    return ["hook", "obstaculo"] + ["desarrollo"] * (n - 4) + ["resultado", "cta"]


def _instruccion_slides(num_slides: int) -> str:
    n = max(3, min(10, int(num_slides))) if num_slides else DEFAULT_SLIDES
    plan = _plan_beats(n)
    laminas = "\n".join(
        f"- Lámina {i} (rol {rol}): {BEAT_DESC[rol]}"
        for i, rol in enumerate(plan, 1)
    )
    return (
        f"\n\nEl carrusel debe tener EXACTAMENTE {n} láminas, con esta estructura "
        f"exacta (respeta el rol de cada una en el mismo orden):\n{laminas}"
    )


def _instruccion_duracion(duracion_seg: int) -> str:
    if not duracion_seg:
        return (
            "\n\nDuración total al narrar: ~30 segundos, repartidos aproximadamente "
            "10% hook, 40% obstáculo, 33% ejecución, 17% cta (0 si no aplica CTA)."
        )
    duracion_seg = max(10, min(90, int(duracion_seg)))
    palabras = round(duracion_seg * PALABRAS_POR_SEGUNDO)
    return (
        f"\n\nEl guion completo (hook+obstaculo+ejecucion+cta) debe durar EXACTAMENTE "
        f"~{duracion_seg} segundos al narrarlo (~{palabras} palabras), repartidos "
        f"proporcionalmente: ~10% hook, ~40% obstáculo, ~33% ejecución, ~17% cta "
        f"(0 si el contenido es solo informativo y no lleva cta)."
    )


def generar_contenido(noticia: dict, formato: str, perfil: str,
                      num_slides: int = 0, duracion_seg: int = 0, plataforma: str = "",
                      ritmo_corte: str = "medio", musica: str = "upbeat",
                      velocidad_narracion: str = "rapida", zoom_camara: bool = True) -> dict:
    """Genera el contenido final para `noticia` en `formato` con la voz de `perfil`.

    `num_slides` (solo carrusel): cantidad exacta de slides; 0 = 10 por defecto.
    `duracion_seg` (solo video): duración objetivo al narrar; 0 = ~30s por defecto.
    `plataforma`: "" (neutral) | "tiktok" | "instagram" — ajusta el tono/ritmo.
    `ritmo_corte`/`musica`/`velocidad_narracion`/`zoom_camara` (solo video): parámetros
    de producción — el LLM ajusta el guion en base a ellos y se devuelven como
    instrucciones para quien edita (el render automático no los aplica todavía).
    """
    if formato not in SCHEMAS:
        raise ValueError(f"Formato inválido: {formato}")
    brand = _brand(perfil)

    instrucciones_estructura = ""
    if formato == "carrusel":
        instrucciones_estructura = _instruccion_slides(num_slides)
    elif formato == "video":
        instrucciones_estructura = _instruccion_duracion(duracion_seg)
        instrucciones_estructura += _instruccion_parametros(
            ritmo_corte, musica, velocidad_narracion, zoom_camara
        )
    instrucciones_estructura += PLATAFORMA_INSTR.get(plataforma, "")

    system = (
        f"Eres el creador de contenido de {brand['brand_name']} para "
        f"{', '.join(brand['platforms'])}. Tono de voz: {brand['tone_of_voice']}. "
        f"Audiencia: {brand['target_audience']}. Escribes en español latino, directo "
        f"y sin relleno. No inventes datos que no estén en la noticia. "
        f"Hashtags base de la marca (inclúyelos y suma 3-5 específicos del tema): "
        f"{' '.join(brand['hashtags_base'])}. "
        f"CTA por defecto si aplica: {brand['cta_default']}. "
        f"Para el caption: usá emojis FUNCIONALES (separan ideas, enfatizan un punto), "
        f"nunca decorativos sueltos — es el patrón más consistente en cuentas del nicho "
        f"que funcionan bien."
    )

    prompt = (
        f"Crea el contenido en formato {formato.upper()} para esta noticia:\n\n"
        f"Título: {noticia['titulo']}\n"
        f"Resumen: {noticia.get('resumen', '')}\n"
        f"Tema: {noticia.get('tema', '')}\n"
        f"Fuente: {noticia.get('fuente', '')}\n"
        f"Justificación editorial: {noticia.get('justificacion', '')}"
        + instrucciones_estructura
    )
    contenido = llm_client.generar_json("generacion", system, prompt, SCHEMAS[formato])

    if formato == "video":
        partes = [contenido["hook"], contenido["obstaculo"], contenido["ejecucion"]]
        if contenido.get("cta"):
            partes.append(contenido["cta"])
        contenido["guion"] = " ".join(p.strip() for p in partes if p and p.strip())

    contenido["formato"] = formato
    contenido["perfil"] = perfil
    contenido["plataforma"] = plataforma or "general"
    if formato == "video":
        contenido["instrucciones_produccion"] = {
            "ritmo_corte": RITMO_CORTE_LABEL.get(ritmo_corte, ritmo_corte),
            "musica": MUSICA_LABEL.get(musica, musica),
            "velocidad_narracion": VELOCIDAD_LABEL.get(velocidad_narracion, velocidad_narracion),
            "zoom_camara": "sí, con movimiento" if zoom_camara else "estático, sin zoom",
        }
    contenido["noticia"] = {
        "titulo": noticia["titulo"],
        "url": noticia.get("url", ""),
        "tema": noticia.get("tema", ""),
    }
    return contenido


SEGMENTO_LABEL_VIDEO = {
    "hook": "hook (0-3s, el resultado que engancha)",
    "obstaculo": "obstáculo (3-15s, el problema/dolor)",
    "ejecucion": "ejecución (15-25s, la demostración)",
    "cta": "cta (últimos 5s, el llamado a la acción)",
}


def generar_variantes_segmento(contenido: dict, perfil: str, campo, n: int = 3) -> list:
    """Genera `n` alternativas (ángulos distintos) para UN segmento puntual de
    una pieza ya generada, sin tocar el resto.

    `campo` según formato:
    - "video": uno de "hook"|"obstaculo"|"ejecucion"|"cta".
    - "carrusel": índice de slide (int o str numérico), 0-indexado.
    - "imagen": se ignora (solo hay un titular).
    """
    brand = _brand(perfil)
    formato = contenido.get("formato")
    n = max(2, min(4, int(n))) if n else 3

    if formato == "video":
        if campo not in SEGMENTO_LABEL_VIDEO:
            raise ValueError(f"Campo inválido para video: {campo}")
        texto_actual = contenido.get(campo, "")
        contexto = "\n".join(
            f"{SEGMENTO_LABEL_VIDEO[k].split(' (')[0].capitalize()}: {contenido[k]}"
            for k in ("hook", "obstaculo", "ejecucion", "cta")
            if k != campo and contenido.get(k)
        )
        etiqueta_segmento = SEGMENTO_LABEL_VIDEO[campo]
    elif formato == "carrusel":
        idx = int(campo)
        slides = contenido["slides"]
        slide = slides[idx]
        texto_actual = slide.get("titular", "")
        vecinos = []
        if idx > 0:
            vecinos.append(f"Slide anterior: {slides[idx - 1].get('titular', '')}")
        if idx < len(slides) - 1:
            vecinos.append(f"Slide siguiente: {slides[idx + 1].get('titular', '')}")
        contexto = f"Cuerpo de este slide: {slide.get('cuerpo', '')}\n" + "\n".join(vecinos)
        etiqueta_segmento = f"slide {idx + 1} de {len(slides)} (rol: {slide.get('rol', '')})"
    elif formato == "imagen":
        texto_actual = contenido.get("titulo", "")
        contexto = f"Cuerpo: {contenido.get('cuerpo', '')}"
        etiqueta_segmento = "titular"
    else:
        raise ValueError(f"Formato inválido: {formato}")

    system = (
        f"Eres el creador de contenido de {brand['brand_name']}. Tono de voz: "
        f"{brand['tone_of_voice']}. Audiencia: {brand['target_audience']}. "
        f"Escribes en español latino, directo y sin relleno."
    )
    prompt = (
        f"Este es el texto ACTUAL del segmento '{etiqueta_segmento}' de una pieza ya escrita:\n"
        f"\"{texto_actual}\"\n\n"
        f"Contexto del resto de la pieza (NO lo cambies, solo sirve de referencia para que la "
        f"alternativa siga encajando con lo que viene antes/después):\n{contexto}\n\n"
        f"Generá {n} alternativas para ESE segmento puntual, cada una con un ÁNGULO distinto "
        f"entre sí (ej. dato duro, pregunta directa, contrarian, urgencia, curiosidad) — ninguna "
        f"repite la actual ni entre sí. Mismo tema, mismo tono de marca, y tiene que seguir "
        f"encajando con el resto de la pieza (no contradecirla)."
        + ("\n\nIncluí también un 'cuerpo' corto de apoyo para cada alternativa (equivalente al "
           "de ese slide)." if formato == "carrusel" else "")
    )
    resultado = llm_client.generar_json("generacion", system, prompt, VARIANTES_SCHEMA)
    return resultado["variantes"][:n]
