"""
LLM Client — capa única para llamar al modelo de IA que corresponda según
la tarea (ranking/generacion/resumen), configurado en config_store.

Soporta Gemini y Claude con salida JSON estructurada. Registra el gasto
(tokens + costo estimado) en usage_store y los fallos en errores.
"""

import base64
import json
import os
from pathlib import Path

import requests

import config_store
import errores
import usage_store

BASE = Path(__file__).resolve().parent

_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"


class LLMError(Exception):
    pass


def _extraer_json(texto: str) -> dict:
    """Parsea JSON de la respuesta; tolera que venga envuelto en ```json ... ```."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:]
        texto = texto.strip()
    return json.loads(texto)


def _asegurar_additional_properties_false(schema: dict) -> dict:
    """Copia el schema agregando additionalProperties:false en cada objeto (requerido por Claude)."""
    schema = dict(schema)
    if schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
        if "properties" in schema:
            schema["properties"] = {
                k: _asegurar_additional_properties_false(v)
                for k, v in schema["properties"].items()
            }
    if schema.get("type") == "array" and "items" in schema:
        schema["items"] = _asegurar_additional_properties_false(schema["items"])
    return schema


def _llamar_gemini(modelo: str, system: str, prompt: str, schema: dict) -> tuple:
    r = requests.post(
        GEMINI_API_URL.format(modelo=modelo),
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    texto = data["candidates"][0]["content"]["parts"][0]["text"]
    uso = data.get("usageMetadata", {})
    tokens_in = uso.get("promptTokenCount", 0)
    tokens_out = uso.get("candidatesTokenCount", 0)
    return json.loads(texto), tokens_in, tokens_out


def _llamar_gemini_imagenes(modelo: str, system: str, partes: list, schema: dict) -> tuple:
    """Como _llamar_gemini pero `partes` es una lista de ("texto", str) | ("imagen", bytes)
    intercalada — para analizar contenido visual (frames) sin transcripción."""
    contenido_parts = []
    for tipo, valor in partes:
        if tipo == "texto":
            contenido_parts.append({"text": valor})
        else:
            contenido_parts.append({
                "inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(valor).decode()}
            })
    r = requests.post(
        GEMINI_API_URL.format(modelo=modelo),
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": contenido_parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        },
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    texto = data["candidates"][0]["content"]["parts"][0]["text"]
    uso = data.get("usageMetadata", {})
    return json.loads(texto), uso.get("promptTokenCount", 0), uso.get("candidatesTokenCount", 0)


def _llamar_claude_imagenes(modelo: str, system: str, partes: list, schema: dict) -> tuple:
    import anthropic
    client = anthropic.Anthropic()
    schema_claude = _asegurar_additional_properties_false(schema)
    content = []
    for tipo, valor in partes:
        if tipo == "texto":
            content.append({"type": "text", "text": valor})
        else:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(valor).decode()},
            })
    response = client.messages.create(
        model=modelo, max_tokens=4096, system=system,
        output_config={"format": {"type": "json_schema", "schema": schema_claude}},
        messages=[{"role": "user", "content": content}],
    )
    texto = next(b.text for b in response.content if b.type == "text")
    return json.loads(texto), response.usage.input_tokens, response.usage.output_tokens


def _llamar_claude(modelo: str, system: str, prompt: str, schema: dict) -> tuple:
    import anthropic
    client = anthropic.Anthropic()
    schema_claude = _asegurar_additional_properties_false(schema)
    response = client.messages.create(
        model=modelo,
        max_tokens=4096,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema_claude}},
        messages=[{"role": "user", "content": prompt}],
    )
    texto = next(b.text for b in response.content if b.type == "text")
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    return json.loads(texto), tokens_in, tokens_out


def _llamar_openai(modelo: str, system: str, prompt: str, schema: dict) -> tuple:
    instrucciones_json = (
        f"{system}\n\nResponde ÚNICAMENTE con un JSON válido (sin markdown, sin "
        f"explicación) que cumpla exactamente este schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )
    r = requests.post(
        OPENAI_API_URL,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={
            "model": modelo,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": instrucciones_json},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    texto = data["choices"][0]["message"]["content"]
    uso = data.get("usage", {})
    return _extraer_json(texto), uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)


def _llamar_perplexity(modelo: str, system: str, prompt: str, schema: dict) -> tuple:
    instrucciones_json = (
        f"{system}\n\nResponde ÚNICAMENTE con un JSON válido (sin markdown, sin "
        f"explicación) que cumpla exactamente este schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )
    r = requests.post(
        PERPLEXITY_API_URL,
        headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"},
        json={
            "model": modelo,
            "messages": [
                {"role": "system", "content": instrucciones_json},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    texto = data["choices"][0]["message"]["content"]
    uso = data.get("usage", {})
    return _extraer_json(texto), uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)


def _listar_gemini() -> list:
    r = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        timeout=10,
    )
    r.raise_for_status()
    return sorted({
        m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and m["name"].removeprefix("models/").startswith("gemini")
    }, reverse=True)


def _listar_claude() -> list:
    import anthropic
    client = anthropic.Anthropic()
    return [m.id for m in client.models.list()]


def _listar_openai() -> list:
    r = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        timeout=10,
    )
    r.raise_for_status()
    excluidos = ("embedding", "audio", "realtime", "transcribe", "tts",
                "instruct", "moderation", "whisper", "dall-e", "davinci", "babbage")
    return sorted({
        m["id"] for m in r.json().get("data", [])
        if m["id"].startswith("gpt-") and not any(x in m["id"] for x in excluidos)
    }, reverse=True)


_LISTADORES = {"gemini": _listar_gemini, "claude": _listar_claude, "openai": _listar_openai}


def listar_modelos(proveedor: str) -> dict:
    """Modelos disponibles en vivo para `proveedor`. Nunca lanza excepción:
    si la consulta falla (sin key, sin red, endpoint caído) devuelve la
    lista de respaldo y registra el motivo en errores.log.
    """
    import config_store

    env_var = config_store.PROVEEDORES.get(proveedor, {}).get("env_var")
    if not env_var or not os.environ.get(env_var):
        return {"modelos": config_store.MODELOS_RESPALDO.get(proveedor, []),
                "en_vivo": False, "aviso": f"Falta configurar la clave de {proveedor}"}

    listador = _LISTADORES.get(proveedor)
    if not listador:
        # Sin endpoint de listado conocido (ej. Perplexity) — respaldo fijo.
        return {"modelos": config_store.MODELOS_RESPALDO.get(proveedor, []), "en_vivo": False}

    try:
        modelos = listador()
        if not modelos:
            raise LLMError("la API respondió sin modelos utilizables")
        return {"modelos": modelos, "en_vivo": True}
    except Exception as e:
        errores.log(f"listar_modelos.{proveedor}", str(e))
        return {"modelos": config_store.MODELOS_RESPALDO.get(proveedor, []),
                "en_vivo": False, "aviso": f"No se pudo consultar {proveedor} en vivo: {e}"}


def generar_json(tarea: str, system: str, prompt: str, schema: dict) -> dict:
    """Genera JSON estructurado usando el proveedor/modelo configurado para `tarea`.

    Registra tokens/costo en usage_store y errores en errores.log si falla.
    """
    conf = config_store.modelo_para(tarea)
    proveedor, modelo = conf["proveedor"], conf["modelo"]

    env_var = config_store.PROVEEDORES[proveedor]["env_var"]
    if not os.environ.get(env_var):
        raise LLMError(f"Falta configurar la clave de {proveedor} ({env_var}) en Configuración")

    try:
        if proveedor == "gemini":
            resultado, tokens_in, tokens_out = _llamar_gemini(modelo, system, prompt, schema)
        elif proveedor == "claude":
            resultado, tokens_in, tokens_out = _llamar_claude(modelo, system, prompt, schema)
        elif proveedor == "openai":
            resultado, tokens_in, tokens_out = _llamar_openai(modelo, system, prompt, schema)
        elif proveedor == "perplexity":
            resultado, tokens_in, tokens_out = _llamar_perplexity(modelo, system, prompt, schema)
        else:
            raise LLMError(f"Proveedor no soportado para tareas de IA: {proveedor}")
    except Exception as e:
        errores.log(f"llm_client.{tarea}", f"{proveedor}/{modelo}: {e}")
        raise

    usage_store.registrar_ia(tarea, proveedor, modelo, tokens_in, tokens_out)
    return resultado


def generar_json_imagenes(tarea: str, system: str, texto_prompt: str, visuales: list, schema: dict) -> dict:
    """Como generar_json, pero para contenido sin transcripción posible (video sin
    audio) — analiza frames en vez de texto. `visuales`: lista de (etiqueta,
    [jpeg_bytes, ...]) que se intercala después de `texto_prompt`. Solo Gemini y
    Claude soportan imágenes hoy; otros proveedores fallan con un error claro.
    """
    conf = config_store.modelo_para(tarea)
    proveedor, modelo = conf["proveedor"], conf["modelo"]

    env_var = config_store.PROVEEDORES[proveedor]["env_var"]
    if not os.environ.get(env_var):
        raise LLMError(f"Falta configurar la clave de {proveedor} ({env_var}) en Configuración")

    partes = [("texto", texto_prompt)]
    for etiqueta, frames in visuales:
        partes.append(("texto", f"\n\n--- {etiqueta} (sin audio — análisis visual de frames, en orden) ---"))
        for f in frames:
            partes.append(("imagen", f))

    try:
        if proveedor == "gemini":
            resultado, tokens_in, tokens_out = _llamar_gemini_imagenes(modelo, system, partes, schema)
        elif proveedor == "claude":
            resultado, tokens_in, tokens_out = _llamar_claude_imagenes(modelo, system, partes, schema)
        else:
            raise LLMError(
                f"El proveedor configurado para '{tarea}' ({proveedor}) no soporta "
                "análisis de imágenes todavía — elegí Gemini o Claude en Configuración "
                "para esta tarea."
            )
    except Exception as e:
        errores.log(f"llm_client.{tarea}", f"{proveedor}/{modelo}: {e}")
        raise

    usage_store.registrar_ia(tarea, proveedor, modelo, tokens_in, tokens_out)
    return resultado


MODELO_IMAGEN_GEMINI = "gemini-2.5-flash-image"


def generar_imagen(prompt: str, tarea: str = "fondo_animado", aspect_ratio: str = "") -> bytes:
    """Genera una imagen desde cero con Gemini (nano-banana) a partir de un
    prompt de texto — para fondos de imagen/historia con IA en vez de banco
    de stock. Fijo a Gemini (único proveedor de la app con generación de
    imagen); requiere GEMINI_API_KEY configurada, sea cual sea el proveedor
    elegido para las demás tareas. `aspect_ratio` (ej. "9:16", "4:5", "1:1")
    pisa el default cuadrado del modelo — sin esto, Gemini ignora cualquier
    proporción pedida en el texto del prompt (probado). Registra el gasto en
    usage_store."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise LLMError("Falta configurar la clave de Gemini (GEMINI_API_KEY) en Configuración")
    generation_config = {"imageConfig": {"aspectRatio": aspect_ratio}} if aspect_ratio else {}
    try:
        r = requests.post(
            GEMINI_API_URL.format(modelo=MODELO_IMAGEN_GEMINI),
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                **({"generationConfig": generation_config} if generation_config else {}),
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        partes = data["candidates"][0]["content"]["parts"]
        inline = next((p["inlineData"] for p in partes if "inlineData" in p), None)
        if not inline:
            raise LLMError("Gemini no devolvió una imagen para este prompt")
        imagen_bytes = base64.b64decode(inline["data"])
        uso = data.get("usageMetadata", {})
    except Exception as e:
        errores.log(f"llm_client.{tarea}", f"gemini/{MODELO_IMAGEN_GEMINI}: {e}")
        raise
    usage_store.registrar_ia(tarea, "gemini", MODELO_IMAGEN_GEMINI,
                             uso.get("promptTokenCount", 0), uso.get("candidatesTokenCount", 0))
    return imagen_bytes
