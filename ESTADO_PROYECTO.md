# Estado del proyecto — Agente de Contenido

> Si estás retomando esto en un chat nuevo: decile a Claude "seguí con el
> Agente de Contenido, mirá `news_agent/ESTADO_PROYECTO.md`" y con eso alcanza.
> Esta info también vive en la memoria persistente de Claude Code (se carga
> sola), pero tenerla acá también sirve como respaldo y para vos.

Última actualización: 30 jul 2026.

## Qué es

App local (FastAPI + dashboard HTML/JS, sin build) que busca noticias o
investiga un tema, las rankea, y genera contenido final (guion de video,
carrusel de imágenes, o imagen suelta) con la marca/voz de Andrés Duque o HAM
Agencia. Corre en `http://localhost:8765`.

**Arrancar:** `cd news_agent && ./.venv/bin/python run.py`

## Cómo está armado (mapa de archivos)

```
news_agent/
├── run.py                 # un solo comando: levanta el server + abre navegador
├── dashboard/
│   ├── app.py              # todos los endpoints FastAPI
│   ├── index.html          # dashboard principal (barrido + investigación + referentes)
│   ├── config.html         # /config — claves, modelos, voz, marcas, gastos, errores
│   ├── history.html        # /history — todo lo producido + matriz de viralidad
│   └── calendario.html     # /calendario — planificador semanal + series recurrentes
├── news_fetcher.py, ranker.py, ranker_ia.py   # Modo 1: barrido de noticias (4 puntajes: Novedad/Prueba/Conflicto/Acción)
├── investigacion.py                            # Modo 2: investigación puntual (Perplexity, mismos 4 puntajes)
├── referentes.py            # Modo 3: ideas por referentes (yt-dlp + whisper.cpp local + IA, analiza video Y caption)
├── calendario_store.py      # calendario.jsonl + calendario_config.json (canales/objetivo)
├── series_store.py          # series.jsonl — series recurrentes (ej. "Lunes de IA")
├── generator_ia.py         # arma el guion/carrusel/imagen final (estructura por rol)
├── image_producer.py       # Playwright → PNG (imagen/carrusel/historia), 7 skins visuales
├── fondo_producer.py       # imagen/historia como MP4 con fondo animado (Pexels o IA + Ken Burns)
├── video_producer.py       # voz ElevenLabs + B-roll Pexels + FFmpeg → mp4
├── calidad_video.py         # gate de calidad bloqueante (FFmpeg freezedetect) antes de entregar video
├── matriz_viralidad.py      # matriz_viralidad.json — patrones de piezas propias + simulador
├── llm_client.py           # capa única multi-LLM (Gemini/Claude/OpenAI/Perplexity) + generar_imagen()
├── config_store.py         # claves (.env) + qué modelo usa cada tarea (ia_config.json)
├── usage_store.py          # gastos.jsonl — tokens/USD por llamada
├── errores.py              # errores.jsonl — log de fallos
├── history_store.py        # history.jsonl — todo lo producido, agrupa tests de variantes, predicción vs. real
├── metricas_store.py        # metricas.jsonl — resultado real cargado a mano por pieza
├── evergreen_store.py       # evergreen.jsonl — banco de noticias/ángulos que no caducan
├── topics_store.py         # temas del Modo 1 (topics.json)
├── plantillas_referentes.md         # patrones visuales de carrusel (de capturas de pantalla)
├── patrones_video_referentes.md     # patrones de guion/copy de video (75 reels reales analizados)
└── brand_config.json       # perfiles de marca (colores, tono, hashtags, logo)
```

## Flujo real en el dashboard (importante — NO es automático)

1. **Buscar** (Modo 1: "Buscar noticias" o "TOP 5 con IA"), **Investigar**
   (Modo 2: escribís un tema) o **Ideas por referentes** (Modo 3: pegás
   links/subís videos de la competencia) → aparece SOLO la lista, nada se
   genera todavía. Top 5 llevan badge "DESTACADA" + estrellitas (no números).
2. Elegís UNA noticia/ángulo, el formato (video/carrusel/imagen) y sus
   parámetros (slides, duración) → clic en **"Crear contenido"** → recién ahí
   se genera el guion/copy de ESA pieza (llamada a IA).
3. Revisás el guion, elegís logo (marca / personalizado / ninguno), formato de
   imagen (cuadrado/vertical), si también querés una **historia (9:16)** de
   aviso → clic en **"Generar carrusel"/"Producir video"/"Generar imagen"** →
   ahí se renderizan los archivos finales.

Aparte de ese flujo principal, `/calendario` es un planificador semanal
independiente (qué publicar cada día, por canal) — no genera contenido, es
solo organización. Ver detalle en el roadmap más abajo.

Cada carrusel es sobre **un solo tema** — todas las láminas desarrollan la
misma noticia/ángulo de principio a fin, nunca mezcla temas distintos.

## Carrusel con láminas de video (26 jul 2026)

Inspirado en cuentas que mezclan imagen fija + un clip corto dentro del mismo
carrusel (ej. demos de producto). Antes de "Generar carrusel", cada lámina
del output tiene un checkbox **"🎥 Video"** — el usuario elige cuáles quiere
como video corto (1080×1080, voz ElevenLabs + B-roll Pexels vía
`video_producer.producir_slide_video()`) y cuáles quedan como imagen estática
(igual que siempre). El resto de las láminas NO se toca — cambio quirúrgico,
no todo-o-nada. `generator_ia.py` ahora pide `broll_query` (inglés) para
TODAS las láminas del carrusel (costo marginal, mismo llamado a IA) por si
alguna termina siendo video. Backend: `POST /api/producir-imagen` acepta
`video_slides: [1, 3, ...]` (1-indexado); `image_producer.producir_imagen()`
salta esas láminas, `dashboard/app.py` las produce aparte y mezcla los
archivos en la carpeta final (`slide_01.mp4`, `slide_02.png`, ...) ordenados
por nombre. `history.html` ya soporta miniaturas mixtas imagen/video.
Requiere ELEVENLABS_API_KEY + PEXELS_API_KEY (mismo check que producir-video).
Probado end-to-end con un carrusel de 3 láminas, 1 en video — funcionó
(1080x1080, audio sincronizado, B-roll acorde a la query).

## Estructura de carrusel por cantidad de láminas (ya implementada)

- 3 → Hook / Desarrollo / CTA
- 4 → Hook / Obstáculo / Desarrollo / CTA
- 5 → Hook / Obstáculo / Desarrollo / Resultado / CTA
- 6-9 → Hook / Obstáculo / Desarrollo (expandido en pasos) / Resultado / CTA

Cada rol tiene su propio diseño visual (`image_producer.py` → `BEAT_STYLE` /
`FONDOS`): el hook con blob de acento y título grande, el obstáculo con barra
de alerta arriba, los desarrollo con badge numerado ("PASO 2 DE 4"), el CTA
como botón-pill con flecha. Nada de plantilla repetida.

## Formatos de imagen

- Carrusel → **siempre cuadrado** (1080×1080).
- Imagen suelta → elegible **cuadrado o vertical** (4:5, 1080×1350).
- Historia (opcional, "generar en conjunto") → **9:16** (1080×1920), teaser
  automático sin IA ("Nuevo video/carrusel/post" + título + "Ya está en el
  feed →").
- Video → 9:16 (1080×1920) vía ElevenLabs + Pexels + FFmpeg.
- Logo: toggle on/off + opción de subir un PNG personalizado por producción
  (no pisa el logo del perfil de marca).

## Overlays de texto quemados en video (27 jul 2026, noche)

El video (completo y láminas-video de carrusel) ahora SÍ lleva texto en
pantalla — antes era solo voz + B-roll, sin nada visual. Reutiliza las
mismas plantillas de skin que las imágenes (`image_producer.py`), con el
fondo forzado a transparente (`_forzar_fondo_transparente` — override CSS
antes de `</head>`, cubre `background` y `background-image`) y capturadas
con `page.screenshot(omit_background=True)` de Playwright para obtener PNG
con canal alfa. Ese PNG se compone sobre el B-roll con FFmpeg
(`ensamblar_con_overlays` en `test_video_pipeline.py`, filtro `overlay` con
`enable='between(t,inicio,fin)'` para timing, o sin `enable` para toda la
duración).

- **Láminas de carrusel como video** (`video_producer.producir_slide_video`):
  usa el **diseño completo de la lámina** (mismo look que su hermana
  imagen) vía `image_producer.producir_overlay_slide(brand, slide,
  estilo_visual)` — se ve exactamente igual que si fuera PNG, pero con
  B-roll de fondo en vez de color sólido.
- **Video completo** (`video_producer.producir_video`): usa los
  `texto_pantalla` que ya generaba `generator_ia.py` (frase + momento, ej.
  "0-3s" o "~8s") como "chips" cortos con la identidad de color/tipografía
  de cada skin (`image_producer.producir_caption_png`, tabla
  `_CAPTION_TABLA` — un estilo de chip por skin, no la lámina completa).
  `video_producer._parse_momento()` interpreta el string de momento a
  segundos (rango o instante ±2.5s de default).
- `estilo_visual` ahora aplica a los 3 formatos (antes solo imagen/carrusel)
  — selector visible siempre en el dashboard, incluido para "video".
  `/api/producir-video` y el loop de `video_slides` en `/api/producir-
  imagen` lo pasan a `video_producer`.
- Probado end-to-end con llamadas reales a ElevenLabs+Pexels: una
  lámina-video (skin "listicle") con el diseño completo quemado sobre B-roll
  real, y un video completo (skin "brutalista") con 2 captions temporizados
  — se verificó frame por frame que cada caption aparece y desaparece en su
  ventana exacta (0-3s, luego nada hasta 8-10.5s).

### Siguiente ronda pedida por Andrés (27 jul 2026, viendo un output real) — EN ORDEN:

1. ~~Historia = screenshot real del video, no teaser genérico.~~ HECHO (27
   jul 2026, noche). Cuando `contenido.formato === 'video'` y se generó
   "también historia", el frontend manda el `video_url` ya producido a
   `/api/producir-historia`; el backend saca un frame real con
   `video_producer.extraer_frame_mejor_momento()` (ffprobe+ffmpeg) y arma la
   historia con `image_producer.producir_historia_con_frame()` — mismo
   texto/pill de siempre, pero de fondo el frame real con un scrim oscuro
   abajo para legibilidad, en vez de color sólido. "Mejor momento" = un
   instante que evita a propósito las ventanas de los `texto_pantalla` ya
   quemados en el video (si no, el caption del video se pisa con el
   título/pill de la historia — bug real encontrado y corregido en la
   prueba). Sin IA, $0 aparte del frame que ya existe. Probado end-to-end
   con un video real — el frame queda limpio, sin overlap con el texto de
   la historia.
2. ~~Variantes por segmento del guion (no solo el hook).~~ HECHO (27 jul
   2026, noche). `generator_ia.generar_variantes_hook()` se reemplazó por
   `generar_variantes_segmento(contenido, perfil, campo, n)` — `campo` es
   "hook"|"obstaculo"|"ejecucion"|"cta" en video, índice de slide (0-idx) en
   carrusel, o se ignora en imagen. Endpoint renombrado a `/api/generar-
   variantes-segmento` (`VariantesSegmentoIn` en `dashboard/app.py`).
   Frontend: cada segmento del output de video, y cada lámina del carrusel,
   tiene su propio botón "Variantes" + contenedor de resultado
   (`data-variantes-campo`/`data-variantes-resultado`) — antes solo existía
   un botón global que únicamente variaba el hook/slide 1. Formato imagen
   mantiene un único botón global ("Variantes de titular"). Funciones JS
   genéricas `generarVariantesSegmento()`/`aplicarVarianteSegmento()`
   reemplazan a las viejas `...Hook()`. Probado end-to-end (curl real para
   video y carrusel + clic real en el dashboard): genera 3 alternativas
   para el segmento elegido sin tocar el resto, "Usar" reemplaza solo ese
   campo y recompone el `guion` completo del video automáticamente.
3. ~~Control de estilo del texto en pantalla (color, fondo sí/no, fuente).~~
   HECHO (27 jul 2026, noche). `image_producer.producir_caption_png()`
   acepta overrides opcionales `texto_color` (hex), `fondo_activo` (bool —
   `False` = texto suelto con sombra oscura para legibilidad en vez de la
   caja del skin) y `fuente` ("sans"|"serif") que pisan la tabla
   `_CAPTION_TABLA` del skin elegido; si no se pasan, sigue el default de
   siempre. Bug encontrado y arreglado en la prueba: sin fondo, el texto
   heredaba el color oscuro pensado para ir SOBRE una chapa de color, no
   directo sobre video — quedaba negro con sombra negra, ilegible; ahora
   por defecto es blanco con sombra oscura cuando no hay fondo. Solo aplica
   al **video completo** (los `texto_pantalla`) — las láminas-video de
   carrusel siguen usando el diseño íntegro del skin (`producir_overlay_
   slide`) para no romper la paridad visual con su hermana imagen.
   Wireado: `video_producer.producir_video()` y `ProducirIn` (`texto_color`/
   `fondo_texto`/`fuente_texto`) en `dashboard/app.py`; en el dashboard,
   controles visibles solo para formato video (selector de color con botón
   "automático", checkbox de fondo, select de fuente). Probado con 4
   variantes (default, color custom, sin fondo, fuente forzada) — todas
   correctas.
4. ~~Cambio de toma de B-roll cada ~3s según el tramo del guion.~~ HECHO
   (27 jul 2026, noche) — última de las 4, la más grande. `generator_ia.py`
   ahora pide `broll_query_hook`/`_obstaculo`/`_ejecucion`/`_cta` (además
   del `broll_query` general, que queda de respaldo). `video_producer.
   producir_video()`: genera la voz primero, mide su duración REAL
   (ffprobe, no un estimado) y reparte esa duración entre los tramos con
   texto no vacío proporcional a su cantidad de caracteres
   (`_segmentos_por_duracion`) — así el cambio de toma coincide con lo que
   se está diciendo en cada momento, no con tiempos fijos que no calzan
   con el ritmo real de la narración. Trae un clip de Pexels por tramo y
   los encadena con FFmpeg (`ensamblar_multi_broll` en `test_video_
   pipeline.py`: `trim`+`scale`+`crop` por segmento → `concat` → overlay de
   captions igual que siempre, mapeando el audio de la voz completa).
   Retrocompatible: si `contenido` no trae `broll_query_<tramo>` (piezas
   generadas antes de este cambio), usa el camino viejo de un solo B-roll.
   Sube costo/tiempo (4 llamadas a Pexels en vez de 1). Probado end-to-end
   con llamada real a ElevenLabs + 4 a Pexels — se extrajeron frames en
   cada tramo y se confirmó que la toma cambia (celebración/gráficos →
   escritorio desordenado → dashboard digital → apretón de manos) sin
   cortes de audio.

Los 4 puntos de esta ronda quedaron completos.

**Verificación final end-to-end (27 jul 2026, misma noche):** a pedido de
Andrés, se generó y produjo un video real de 15s sobre "live shopping" a
través de los endpoints reales del dashboard (`POST /api/generar` →
`POST /api/producir-video`, no llamadas directas a las funciones) para
confirmar que toda la ronda funciona integrada, no solo en pruebas
aisladas. Resultado: multi-broll por tramo con tomas muy relevantes al
tema (alguien vendiendo en vivo, alguien grabando con el celular),
captions bien sincronizados con el skin "listicle". **Nota honesta:** la
duración real terminó en 21s en vez de los 15s pedidos — `duracion_seg`
solo ajusta la CANTIDAD DE PALABRAS objetivo que se le pide al LLM: la
duración real la define ElevenLabs narrando a su propio ritmo, y no
siempre calza exacto con la estimación de palabras/segundo. Es una
limitación preexistente (no algo que rompió esta ronda) — pendiente si
se quiere mayor precisión: medir la duración real después de generar la
voz y, si se pasó mucho del objetivo, regenerar el guion más corto, o
ajustar `PALABRAS_POR_SEGUNDO` en `generator_ia.py` según la voz/velocidad
configurada.

## Ritmo de corte dinámico + investigación de "descuadrado" (30 jul 2026, cont.)

Después de la ronda de 4 ajustes (abajo), Andrés pidió ritmo de corte más dinámico:
"metele 2 y 3 segundos cambio de escena, necesito que tengan más retención" —
`DURACION_TOMA_OBJETIVO` bajó de 3.5s a 2.5s y `MAX_TOMAS_POR_TRAMO` subió de 3 a 5
en `video_producer.py` (más tomas por tramo posibles ahora que el ritmo es más rápido).

Con eso probado, Andrés siguió reportando "los subtítulos están descuadrados" —
**esta vez se midió en píxeles, no a ojo**, para no seguir adivinando: se extrajo un
frame real del video producido y se escaneó la columna central buscando dónde
empieza/termina el color de fondo del chip (cyan). Resultado: margen inferior de
**exactamente 150px**, igual en el video real que en un render aislado del mismo
chip — la POSICIÓN del caption está bien, no es un bug de layout.

Hipótesis actual (sin confirmar todavía por Andrés): el "descuadrado" no es de
posición ni de sync audio↔texto (ambos verificados) sino de **ritmo relativo** — con
el corte de escena ahora cada 2-3s pero el texto todavía cambiando 1 sola vez por
tramo (~9s), la escena corta mucho más rápido que el texto, y esa diferencia de
cadencia entre ambos se puede sentir como "descuadrado" aunque cada uno por
separado esté bien sincronizado con el audio. **Próximo paso propuesto (pendiente
de confirmación de Andrés):** volver a permitir más de un `texto_pantalla` por
tramo, pero esta vez alineado a las TOMAS reales (que ahora se calculan con
precisión vía `_tomas_por_tramo`), no adivinado por la IA como antes — así el
texto cambiaría junto con cada corte de escena, no solo una vez por tramo.

## Ronda de ajustes de video, viendo videos reales (30 jul 2026, misma sesión)

Con el sync ya arreglado, Andrés siguió viendo videos reales y encontró 3 problemas
más — todos arreglados en la misma sesión:

1. **"Cambios de escena cada 3 segundos, se ve descuadrado"**: en realidad NO era el
   B-roll (ese solo cortaba 3 veces, en los límites de cada tramo) — era el TEXTO
   cambiando cada ~3s dentro de un mismo tramo mientras la escena de fondo se quedaba
   quieta (la IA a veces mandaba 2 `texto_pantalla` para el mismo tramo, a pesar de
   la instrucción del schema). Fix de 2 capas: (a) el schema ahora pide EXACTAMENTE
   un texto por tramo (`maxItems: 4`); (b) como el LLM no siempre lo respeta,
   `generator_ia.generar_contenido()` ahora DEDUPLICA en código quedándose con la
   primera aparición de cada segmento, sin importar qué haya mandado la IA — garantía
   real, no solo instrucción de prompt.
2. **Tramos largos con una sola toma fija**: al revés del punto 1 — un tramo de 7-9s
   con una sola imagen fija todo ese tiempo también se siente estático. Fix:
   `video_producer._tomas_por_tramo()` (nuevo) calcula cuántas tomas de B-roll le
   corresponden a cada tramo según su duración REAL (~1 cada 3.5s, tope 3) — todas de
   la MISMA query (coherencia temática) pero clips DISTINTOS de Pexels
   (`broll_pexels(..., indice=k)`, nuevo parámetro que pide el resultado k-ésimo de
   la búsqueda en vez de repetir siempre el primero). **Limitación real encontrada en
   la prueba**: Pexels a veces indexa varias tomas de la misma sesión de grabación
   bajo la misma búsqueda — pedir índices distintos no siempre da variedad visual
   real, a veces es el mismo modelo/set en otra pose. No hay fix $0 fácil para esto
   (necesitaría diversificar la QUERY, no solo el índice); queda como límite conocido.
3. **B-roll con gente que no parece latinoamericana**: la audiencia es LatAm pero las
   queries en inglés (ej. "person frustrated phone") traían modelos de stock sin ese
   sesgo. Fix: las 5 descripciones de `broll_query*` en `generator_ia.py` ahora piden
   agregar "latin american"/"hispanic" a la query cuando hay una persona en escena.
4. **CTA forzando un giveaway que no existe**: el usuario aclaró que no todo video
   vende/regala algo — a veces es puramente informativo y el cierre correcto es un
   simple "síguenos para más contenido", no forzar "comentá X y te lo mando" si no hay
   nada real para entregar. La descripción del campo `cta` ahora distingue 3 casos
   explícitos (giveaway real / solo seguir la cuenta / otras CTAs puntuales) en vez de
   solo "usala cuando aplique" — quedaba ambiguo y a veces la IA lo forzaba igual.

Las 4 probadas end-to-end contra los endpoints reales (2 videos completos generados y
producidos, revisando frames + contenido JSON de cada uno): un texto por tramo
confirmado, CTA informativo sin forzar giveaway confirmado ("Actualiza tu app... 
Síguenos para más contenido" en vez de comentá X), B-roll con "hispanic"/"latin
american" en las queries confirmado y visualmente más representativo en los frames.

## Sincronización real de subtítulos en video (30 jul 2026)

Bug real encontrado por Andrés viendo un video de prueba: los `texto_pantalla`
(subtítulos quemados) no coincidían con lo que se estaba diciendo en ese momento —
en el peor caso, un caption aparecía 4s tarde y otro 3s antes de tiempo. Confirmado
con evidencia real: transcripción de la voz con whisper (timestamps reales) vs.
frames del video mostrando cuándo aparecía cada caption.

**Causa raíz**: `texto_pantalla` traía un "momento" (ej. "~8s") que la IA ADIVINABA
al escribir el guion, ANTES de generar la voz — pero ElevenLabs narra a su propio
ritmo y nunca calza exacto con la estimación (limitación ya conocida de la duración
total, pero no se había medido el impacto en los subtítulos hasta esta prueba).

**Fix**: `texto_pantalla` ahora trae `segmento` (hook/obstaculo/ejecucion/cta) en vez
de un segundo adivinado. `video_producer._limites_segmentos()` (nuevo, refactor de
`_segmentos_por_duracion` que ya existía para el multi-B-roll) calcula el tiempo
REAL de cada tramo recién con la voz ya generada — misma proporción por caracteres
que ya se usaba para cambiar de B-roll. Cada caption se ubica en el tramo real que
le corresponde; si hay más de un caption para el mismo tramo, se reparten ese tiempo
en partes iguales. `extraer_frame_mejor_momento()` (usado por la historia con frame
real) también se actualizó para calcular sus ventanas-a-evitar con el mismo criterio.
Retrocompatible: contenido viejo con `momento` en vez de `segmento` sigue funcionando
con el parseo anterior (sin alinear al tiempo real).

Probado end-to-end contra los endpoints reales: se generó y produjo un video real
de "live shopping" (con 2 captions en el mismo tramo, para probar la subdivisión),
se transcribió la voz con whisper (timestamps reales) y se comparó contra cuándo
aparece cada caption quemado en el video — **coinciden casi exactos en los 5 puntos
verificados**, incluido el CTA final (antes era el más desfasado, 3s adelantado).

## Fondo del caption desproporcionado en video (30 jul 2026)

Segundo hallazgo de Andrés viendo el mismo video de prueba: el fondo del texto en
pantalla se veía "desproporcionado". Causa: `_CAPTION_TABLA` en `image_producer.py`
usaba `border-radius: 100px` (pill completo) para los skins con fondo de acento
("listicle" y "editorial") — en una sola línea se ve como una pastilla prolija,
pero en dos líneas (caja ~180px de alto) el radio de 100px por esquina genera un
efecto "blob" redondeado en exceso, no una forma limpia. Fix: `radius` bajado a
`32px` para esos dos skins (rectángulo redondeado proporcional, igual en 1 o 2
líneas) + tamaño de fuente subido de 50px a 56px (pedido explícito: "el texto
puede ser un poco más grande"). Verificado renderizando el chip aislado (1 línea
y 2 líneas) — ya no hay blob, se ve consistente en ambos casos.

## Patrones de video de referentes (29 jul 2026)

Andrés quería mejorar cómo el agente genera VIDEOS (no solo carruseles) acercándose
a cómo comunican cuentas reales del nicho. Se analizaron **75 reels reales de 5
cuentas** (IA/marketing/emprendimiento) — no 1-2 sueltos, una muestra grande por
cuenta — con transcripción de audio real (whisper) + caption/copy completo (vía
`yt-dlp --dump-json`, sin necesidad de abrir cada post en el navegador).

- `referentes.py` ahora acepta un `caption` opcional por fuente (además del video) y
  suma un campo `patron_copy` al análisis — antes solo miraba el video, ignoraba el
  copy que lo acompaña. Se corrigió de paso un descuido de privacidad: el campo
  `fuente` guardaba la URL/nombre de archivo crudo (podía tener el handle) — ahora
  siempre es "Referente N" genérico.
- El usuario inició sesión en su Instagram real en el Browser pane para poder ver el
  contenido (Instagram bloquea casi todo sin login) — se navegó de forma puramente
  read-only, sin dar like/seguir/comentar nada.
- Se excluyó explícitamente contenido personal/vlog (viajes, cumpleaños, familia,
  eventos sociales) de cada cuenta — solo se analizó lo laboral/informativo, según
  pidió Andrés explícitamente.
- Pipeline técnico (para no repetir tropiezos): `yt-dlp --dump-json --no-download` trae
  caption+métricas sin abrir el post; yt-dlp SIN cookies empieza a colgarse a partir de
  la 2da-3ra request seguida en un loop bash (throttling silencioso de Instagram) — hubo
  que reescribirlo en Python con `subprocess.run(timeout=25)` + `sleep` entre requests.
  Los links de reels se sacan de la grilla del perfil vía `read_page`, no abriendo cada
  uno.
- Resultado consolidado (nunca nombrando las cuentas, siempre "Cuenta A".."Cuenta E") en
  **`patrones_video_referentes.md`** (nuevo, mismo espíritu que `plantillas_referentes.md`
  pero para video con guion hablado): hooks que se repiten (problema directo, afirmación
  audaz, pregunta directa, promesa de secreto), estructuras (problema→solución, lista/
  top, tutorial, anécdota personal como prueba), patrón de copy (emojis funcionales,
  tono adaptable, hashtags mixtos), y CTAs (el más fuerte por lejos: "comentá PALABRA y
  te lo mando" — confirmado con capturas reales de gente respondiendo la palabra pedida).
- Ver memoria `patrones-video-referentes-live247` para el detalle de sesión.

**HECHO (29 jul 2026, mismo día):** `generator_ia.py` ajustado con estos patrones —
- `hook`: la descripción del schema ya no fuerza "el resultado" como único patrón;
  el LLM elige entre problema/dolor directo, afirmación audaz, pregunta directa, o
  dato de impacto (solo si hay cifra real), según qué calce mejor con la noticia.
- `cta`: agrega explícitamente "Comentá [PALABRA] y te lo mando" como opción
  recomendada cuando hay un recurso/guía para entregar — el patrón con mejor
  respuesta real confirmada en el corpus (gente comentando la palabra pedida).
- `obstaculo`/`ejecucion`: ejecución redactada como SOLUCIÓN concreta al problema
  (no descripción abstracta); obstáculo puede saltar directo a "por qué importa" si
  el hook ya cubrió el dolor, para permitir la variante "problema→solución directa"
  sin romper los 4 campos fijos (siguen fijos por compatibilidad con multi-B-roll/
  overlays/variantes por segmento, que dependen de esos 4 nombres de campo).
  Los NOMBRES de los 4 tramos quedan iguales a propósito (rompería medio pipeline
  cambiarlos), pero el contenido de cada uno ya no sigue un solo patrón rígido.
- System prompt: pide emojis FUNCIONALES en el caption (separan ideas/enfatizan),
  no decorativos sueltos.
Probado con 2 generaciones reales: una sin recurso para entregar (hook tipo
pregunta, CTA sin forzar "comentá X" — correcto, no aplicaba) y una con lista de
prompts descargable (CTA "Comentá 'PROMPTS' y te enviamos la lista completa" —
exactamente el patrón esperado). No se tocó `carrusel`/`imagen` — el pedido era
específico de video.

## 3 mejoras al pipeline pedidas por Andrés (28 jul 2026, mismo día)

Ideas propias de Andrés (no de un tercero), en el orden que pidió.

### 1. Gate de calidad antes de entregar (bloqueante)

`calidad_video.py` (nuevo) — chequeo automático que corre DESPUÉS de
ensamblar un video (completo o lámina de carrusel producida como video,
NUNCA en imagen/carrusel estático ni en los briefs de texto) y ANTES de
que cuente como entrega final. Dos chequeos con filtros nativos de FFmpeg
(sin decodificar frame a frame a mano):
- **Estático/sin B-roll**: `freezedetect` detecta tramos sin cambio de
  imagen — rechaza si hay un tramo seguido de más de `UMBRAL_CONGELADO_SEG`
  (3s) o si la cobertura visual total cae debajo de `UMBRAL_COBERTURA_MIN`
  (85%).
- **B-roll sin variedad real**: si el contenido pedía B-roll distinto por
  tramo pero todas las queries usadas terminaron siendo la misma (fallback
  silencioso), lo marca aunque el video "se mueva".

Si rechaza: el archivo se renombra con prefijo `RECHAZADO_` (no se borra,
queda para debug), se loguea en `errores.py` (contexto
`gate_calidad_video`) y **no se registra en `/history`** — para el video
completo (`/api/producir-video`) esto corta toda la respuesta con error
422; para láminas de carrusel-video (`/api/producir-imagen`) es más
quirúrgico: esa lámina puntual se rechaza y se avisa en un array `avisos`
de la respuesta, pero el resto del carrusel (imágenes + otras láminas-
video que sí pasaron) se entrega igual — no tira todo el carrusel por una
lámina.

Probado end-to-end contra el endpoint real: un video real generado en la
prueba dio 3.5s de tramo estático y **fue rechazado correctamente** —
archivo renombrado, logueado, sin entrada en history. Nota honesta: con el
umbral actual (3s/85%) el gate es exigente — es intencional (bloqueante de
verdad, no un aviso), pero si en uso real rechaza demasiado seguido,
`UMBRAL_CONGELADO_SEG`/`UMBRAL_COBERTURA_MIN` son los dos números a
ajustar.

### 2. Filtro de investigación más estricto (4 puntajes)

`ranker_ia.py` (Modo 1) e `investigacion.py` (Modo 2): en vez de un único
score 1-10, cada noticia/ángulo se evalúa en **4 dimensiones
independientes** (1-10 cada una): **Novedad**, **Prueba** (¿hay dato/
fuente verificable?), **Conflicto** (¿alguien pierde algo si es verdad?),
**Acción** (¿el espectador puede hacer algo hoy con esto?). Si **Prueba**
puntúa debajo de `UMBRAL_PRUEBA` (4), esa noticia/ángulo se **descarta
directo**, sin importar cuánto sume el resto — filtrado en Python después
de que la IA evalúa TODAS las candidatas (antes la IA elegía el top 5
directamente; ahora elige evaluando parejo y Python decide el corte, más
transparente y controlable). `score_ia` (usado para las estrellas de
destaque) pasa a ser el promedio de las 4 dimensiones, no un score único
de la IA.

UI: tabla compacta de puntajes (🆕 Novedad · 📎 Prueba · ⚔️ Conflicto · ✅
Acción) debajo de cada noticia/ángulo en el dashboard — aplica tanto al
TOP 5 del Modo 1 como a los ángulos del Modo 2 (comparten el mismo
renderer `pintarNoticias`). Si el Modo 2 descarta TODOS los ángulos de un
tema, el dashboard lo dice explícito ("Ningún ángulo tuvo evidencia
verificable suficiente...") en vez de mostrar una lista vacía sin
explicación.

Probado end-to-end contra los endpoints reales: investigación sobre "IA
generativa en ecommerce LatAm" devolvió 4 ángulos con Prueba 8-9 (ninguno
descartado, todos bien respaldados por la investigación de Perplexity);
ranking del Modo 1 sobre noticias de fútbol (datos de prueba, no el feed
real de marketing) devolvió puntajes bajos coherentes en
Novedad/Conflicto/Acción a pesar de Prueba alta — confirma que el filtro
evalúa cada dimensión de forma independiente, no arrastra un solo número.

### 3. Predicción vs. resultado real

Al producir una pieza (imagen o video — no la historia-teaser), un campo
opcional "🔮 Tu predicción antes de publicar" (texto libre, ej. "creo que
va a rendir bien, tema caliente") se guarda en `history_store` junto con
la pieza (`prediccion` en `ProducirIn`, pasado a `history_store.
registrar()`). En `/history`, si esa pieza tiene métricas cargadas Y hay
al menos otra pieza con métricas para comparar, se calcula su score
(misma fórmula que la matriz de viralidad y el test de variantes:
`likes+comentarios*3+guardados*2+compartidos*2`) contra el **promedio de
TODAS las demás piezas propias con métricas** (nunca contra benchmarks
externos, tal como pidió Andrés) y muestra "📈/📉 Resultado (X) por
encima/debajo de tu promedio (Y)" junto a la predicción original — para
que Andrés pueda comparar a ojo su intuición contra lo que realmente pasó.

Probado end-to-end: pieza A con predicción "creo que va a rendir bien" +
métricas bajas (score 58) vs. pieza B de referencia con métricas altas
(score 450, sin predicción) — el dashboard marcó correctamente la A como
"por debajo de tu promedio (450)" y la B como "por encima de tu promedio
(58)" (el promedio se calcula EXCLUYENDO la propia pieza de cada cálculo,
no un promedio global fijo).

## Reels de prueba en volumen — test de variantes hook×CTA (28 jul 2026)

Idea que quedó evaluada pero sin roadmapear el 24 jul: generar combinaciones
completas (no solo una variante de un segmento), producirlas todas y
trackear cuál gana con datos reales. Solo para formato **video** (ahí es
donde tiene más sentido — carrusel/imagen quedan para más adelante si hace
falta).

- **Generar combinaciones**: en el output de video, sección "🧪 Test de
  variantes (hook × CTA)" — elegís cuántos hooks alternativos (1-3) y
  cuántos CTAs alternativos (0-2) querés, reusa `generar_variantes_
  segmento()` (ya existente) para generarlos, arma el cross-product contra
  el hook/CTA original (incluido como "control") y muestra checkboxes con
  cada combinación para que elijas cuáles producir — nada se produce solo,
  cuidado explícito en el texto sobre el costo (cada combo es un video
  entero: voz ElevenLabs + B-roll Pexels).
- **Producir seleccionadas**: llama a `/api/producir-video` una vez por
  combo elegido, todas con el mismo `test_id` (timestamp) y una
  `test_variante` descriptiva ("Hook pregunta · CTA original"). `history_
  store.registrar()` ahora acepta `test_id`/`test_variante` opcionales
  (nuevos campos en la entrada del historial).
- **`/history` agrupa por test**: las piezas con el mismo `test_id` se
  muestran juntas en una card con borde de acento, cada una con su label
  de variante. Si al menos 2 piezas del grupo tienen métricas cargadas, la
  de mayor score (`likes + comentarios*3 + guardados*2 + compartidos*2` —
  misma fórmula que la matriz de viralidad) se marca con badge "🏆
  Ganador" automáticamente.

Probado end-to-end contra los endpoints reales (no simulado): generó 2
combinaciones (hook original vs. hook "pregunta", mismo CTA) desde el
dashboard real, produjo los 2 videos completos (voz+B-roll reales), se
agruparon correctamente en `/history`, y al cargar métricas distintas
(500 vs. 120 likes) el ganador se marcó solo en la pieza correcta.
Limpieza post-prueba filtrando por slug (no se tocó el resto del
historial real).

## Matriz de viralidad + simulador (28 jul 2026)

Inspirado en un sistema de un tercero visto en Instagram (PDF): scraping de
videos virales con Apify → matrix de patrones → simular un guion nuevo
antes de publicar. Se adaptó para el agente **sin Apify ni costo nuevo de
scraping**: usa datos que la app YA tenía guardados y sin usar —
`history_store` (lo producido) + `metricas_store` (métricas manuales que ya
se cargaban en `/history` desde el 24 jul pero no se usaban para nada).

- `matriz_viralidad.py` (nuevo): `generar_matriz(perfil)` cruza piezas
  propias CON métricas cargadas (mínimo 3), ordenadas por engagement
  (`likes + comentarios*3 + guardados*2 + compartidos*2`), y le pide a la
  IA (reusa la tarea "generacion", sin tarea nueva) que compare lo que más
  funcionó contra lo que menos y saque patrones de **hooks/temas/
  estructuras/frases/CTAs/duración**, cada uno con evidencia citando qué
  piezas lo prueban. Se persiste en `matriz_viralidad.json` (por perfil).
  Si hay menos de 3 piezas con métricas, tira un error claro en vez de
  alucinar un patrón con poca data.
- `simular_guion(texto, perfil)` cruza un guion/copy TODAVÍA SIN PRODUCIR
  contra la última matriz generada y devuelve probabilidad (alta/media/
  baja) + justificación + qué cumple/no cumple + sugerencias concretas.
  Requiere haber generado la matriz antes.
- Backend: `/api/matriz` (GET), `/api/matriz/generar` (POST), `/api/matriz/
  simular` (POST) en `dashboard/app.py`.
- UI: panel "📊 Matriz de viralidad" en `/history` (selector de perfil +
  botón generar/actualizar + resultado formateado por categoría). Botón
  "🔮 Simular viralidad" en el output del dashboard principal (cualquier
  formato — video/carrusel/imagen) que arma el texto relevante de la pieza
  recién generada y lo manda a simular, mostrando el resultado inline.

Probado end-to-end contra los endpoints reales (curl + clic real en
`/history`) con 4 piezas de prueba con métricas variadas: la matriz
detectó correctamente los patrones (IA/automatización con hooks de
curiosidad o dolor personal ganan por lejos a un reporte genérico de
tendencias) citando evidencia real, y dijo honestamente que no había data
suficiente para el patrón de CTAs (no se la di). El simulador marcó
"probabilidad baja" a un guion genérico de prueba con sugerencias
concretas y coherentes con la matriz. Limpieza post-prueba hecha
filtrando por slug/perfil (no borrando archivos enteros — ver memoria
`feedback-no-borrar-archivos-datos-en-limpieza`).

**Limitación honesta:** hoy `metricas.jsonl` está vacío (nadie cargó
métricas reales todavía) — la matriz no tiene con qué generarse hasta que
Andrés publique contenido y cargue sus métricas en `/history`. Es
infraestructura a futuro, no utilizable de inmediato.

## Plantillas de post/historia + fondos animados (27 jul 2026, sesión siguiente)

**Fix de plantillas:** el skin `listicle` mostraba "DESLIZA PARA VER →"
hardcodeado en la portada aunque fuera una imagen suelta (sin nada más que
deslizar) — venía de reusar la misma plantilla del hook de carrusel.
`_slide_html_listicle()` ahora solo muestra el hint cuando `paginador` no
está vacío (o sea, cuando SÍ es parte de un carrusel real). Los demás 6
skins ya se comportaban bien con imagen suelta (el `paginador` queda vacío
y no se ve nada raro).

**Fondos animados (imagen suelta e historia, no carrusel ni video — el
carrusel ya tiene sus láminas-video, el video ya es animado de por sí):**
checkbox "🎬 Fondo animado" junto al resto de controles de imagen — en vez
de un PNG con color/gradiente sólido, produce un MP4 en loop (6s, sin
audio) con el mismo diseño de texto/skin quemado encima.

Dos orígenes, elegibles en el dashboard:
- **Pexels** (banco gratis, libre de derechos) — reusa `broll_pexels` ya
  validado en el pipeline de video.
- **IA** (Gemini "nano-banana", `llm_client.generar_imagen()`) — genera una
  imagen fija desde un prompt y le aplica zoom lento (Ken Burns) con FFmpeg
  (`zoompan`). Gemini no genera video real; esto es lo más parecido a "fondo
  animado por IA" sin meterse en generación de video (cara/lenta). Nota
  técnica encontrada en la prueba: Gemini **ignora la proporción pedida en
  el texto del prompt** — hay que pasar `generationConfig.imageConfig.
  aspectRatio` explícito (`llm_client.generar_imagen(..., aspect_ratio=)`),
  si no siempre devuelve cuadrado.

Piezas nuevas:
- `llm_client.generar_imagen()` — primera función de generación de imagen
  de la app (hasta ahora `llm_client` solo generaba JSON/texto, incluso con
  visión de entrada). Fija a Gemini (`gemini-2.5-flash-image`) porque es el
  único proveedor con esto integrado; requiere `GEMINI_API_KEY` sea cual sea
  el proveedor configurado para las demás tareas. Precio agregado a
  `usage_store.PRECIOS_TOKENS`.
- `image_producer.producir_overlay_historia()` — versión transparente de la
  historia-teaser (mismo patrón que `producir_overlay_slide()` para
  carrusel), refactorizando el armado de HTML a `_historia_html()` para no
  duplicar el if/elif por skin.
- `fondo_producer.py` (nuevo módulo) — `fondo_pexels()`, `fondo_ia()`,
  `componer_fondo_con_overlay()`, y las funciones de alto nivel
  `producir_imagen_animada()` / `producir_historia_animada()`.
- Backend: `ProducirIn` suma `fondo_animado`/`fuente_fondo`/`fondo_query`;
  `/api/producir-imagen` y `/api/producir-historia` ramifican a
  `fondo_producer` cuando `fondo_animado=True` (chequeo de key según fuente:
  `PEXELS_API_KEY` o `GEMINI_API_KEY`). Si el formato es 'video' con
  `video_url` ya presente, gana el flujo existente de "frame real del
  video" — `fondo_animado` no lo pisa.

Probado end-to-end contra los endpoints reales del dashboard (no solo
llamadas directas a las funciones): imagen suelta con fondo Pexels (skin
"prensa_ia", B-roll de "live streaming shopping" — resultado muy relevante
al tema) vía `curl` real a `/api/producir-imagen`, e historia con fondo IA
(skin "brutalista") con Ken Burns visible comparando frames de inicio/fin.
**Límite conocido:** el texto no siempre es legible sobre un B-roll muy
cargado/brillante (ej. brutalista con texto negro sobre fondo naranja
claro) — ningún skin tiene scrim/sombra automática detrás del texto cuando
el fondo es de video en vez de color sólido; pendiente si se vuelve
molesto en uso real.

## Configuración (`/config`)

5 secciones: Claves API (Gemini/Claude/OpenAI/Perplexity/ElevenLabs/Pexels),
Modelo de IA por tarea (ranking/generación/resumen/investigación — se
consulta en vivo a cada API, con respaldo si falla, y sugerencia de cuál
conviene según el caso), Voz de ElevenLabs (filtrable, o Voice ID manual),
Perfiles de marca editables, Gastos (tokens/USD, filtro, últimos 5,
descarga CSV, borrado), Errores (log + limpiar).

## Reestructuración grande del pipeline de video (1-5 ago 2026)

Sesión larga, arrancó arreglando el ritmo de corte y terminó reescribiendo
buena parte de `video_producer.py`. En orden:

1. **B-roll con múltiples tomas por tramo** (`video_producer._tomas_por_tramo()`,
   luego reemplazado — ver punto 4): primer fix del "descuadrado" que venía
   de antes (30 jul) — cada tramo pasó a tener varias tomas de Pexels (~1
   cada 2.5s) en vez de una sola fija.

2. **Subtítulos completos, no chips curados por IA**: Andrés reportó que no
   aparecía "todo lo que está narrando la persona" — el sistema viejo
   (`texto_pantalla`, 1 frase por tramo generada por la IA) solo mostraba
   frases sueltas. Fix intermedio: se dejó de pedirle texto a la IA para
   esto y se usó `voz_elevenlabs_con_timestamps()` (nuevo en
   `test_video_pipeline.py`, endpoint `/v1/text-to-speech/{id}/with-timestamps`
   de ElevenLabs — devuelve alignment carácter-por-carácter real) para
   armar subtítulos en bloques de 4 palabras cubriendo el guion completo.

3. **Pedido: separar por ORACIÓN, no por conteo fijo de palabras** — Andrés
   pidió que cada cartel sea una frase real (corte en el punto) y que el
   B-roll cambie de toma en ese mismo límite ("a medida que separa las
   frases, ese es el tiempo que permanece la escena"). Encontramos que
   **este patrón ya estaba resuelto en `avatarhype-studio/subtitulos.py`**
   (proyecto hermano) — se portó a `news_agent/subtitulos_ass.py`, adaptado
   para usar el alignment de ElevenLabs en vez de transcribir con
   faster-whisper (no hace falta, ya tenemos el timing real). Genera un
   `.ass` con libass: una línea de diálogo por palabra dentro de cada
   oración, coloreando SOLO la palabra activa con el acento de marca
   (efecto karaoke, no acumulativo) — quemado con el filtro `subtitles` de
   ffmpeg como POST-PROCESO (ya no PNGs vía Playwright para esto).
   `video_producer._oraciones_por_tramo()` reparte el alignment global
   entre hook/obstaculo/ejecucion/cta por conteo de palabras y agrupa cada
   porción en oraciones (corta en `. ! ? …`, tope de seguridad de 25
   palabras para texto sin puntuación). El B-roll ahora cambia de toma en
   esos mismos límites (`_tomas_broll_desde_oraciones`, luego
   `_tomas_broll_desde_limites`).

4. **Bug real encontrado por Andrés — el video se cortaba antes de que
   terminara la narración**: cada oración por sí sola solo cubre desde el
   inicio de su primera palabra hasta el fin de su última — sumar esas
   duraciones para decidir cuánto dura el video total (`-t dur_total` en
   `ensamblar_multi_broll`) IGNORABA las micro-pausas entre oraciones y
   entre tramos. Con un guion de varias oraciones esto perdía segundos
   reales (probado con datos sintéticos: 2.7s perdidos de 8.9s, un 30%).
   Fix: `_limites_oraciones_sin_huecos()` — el fin efectivo de cada oración
   es el INICIO de la oración siguiente (mismo criterio ya aplicado a los
   subtítulos para que no parpadeen entre palabras), y la última oración de
   todo el guion se extiende hasta la duración REAL del archivo de audio
   (ffprobe). Verificado con datos sintéticos (suma exacta) y con un video
   real (13.15s de video vs 13.19s de voz real — diferencia de 40ms, el
   delay antes de la primera palabra).

5. **Diseño visual del subtítulo, iterado con capturas** (probado sobre un
   fondo gris sintético + alignment simulado, sin gastar créditos): tamaño
   final 105pt (el doble del original 46pt), posicionado a un cuarto de
   pantalla desde abajo (`MarginV = video_h // 4` en `subtitulos_ass.py`,
   dinámico según resolución). Bug de diseño encontrado y arreglado en la
   misma ronda: el cartel parpadeaba (desaparecía y volvía a aparecer)
   entre palabras si había una micro-pausa en el alignment — mismo fix que
   el punto 4 pero a nivel palabra: el fin de cada línea de diálogo es el
   inicio de la palabra siguiente, no el fin real de la palabra activa.
   Fuente: Poppins (copiada de `avatarhype-studio/fonts/` a
   `news_agent/fonts/` — libass necesita el `.ttf` local, no puede usar
   Google Fonts vía CSS import como hace Playwright para las láminas).

6. **B-roll con clips irrelevantes** — un video de prueba sobre
   "automatizaciones para redes sociales" trajo, para la query
   `ai content creation latin american`, un clip de maquillaje de Catrina/
   Día de Muertos totalmente fuera de tema. Investigado a fondo: NI SIQUIERA
   el resultado #0 (el más relevante según Pexels) era bueno para esa query
   — el problema no era "buscar demasiado lejos en el ranking", era que la
   query en sí es un concepto abstracto de marketing sin buen stock en
   Pexels. Fix real: `generator_ia.py` ahora instruye a la IA a pedir
   queries CONCRETAS y fotografiables (objetos/acciones tangibles como
   "hands typing laptop schedule"), nunca conceptos abstractos — verificado
   contra la API de Pexels directa (6/6 resultados relevantes con queries
   concretas vs. fallando desde el resultado #0 con la abstracta). Además,
   resguardo general en `test_video_pipeline.broll_pexels()`:
   `TOPE_RELEVANCIA = 6` — si un tramo pide más tomas que eso de la misma
   query, cicla entre los primeros 6 resultados en vez de seguir bajando en
   el ranking de Pexels.

7. **Dashboard roto — CDN de Tailwind sin respaldo local**: Andrés reportó
   la interfaz "desfasada"/rota. Investigación larga (mi panel sandboxeado
   no tiene internet en absoluto — confirmado con `curl`/`fetch`, por eso
   ahí siempre se veía roto) pero el usuario confirmó que en SU Chrome real
   también se veía mal (logo del selector de marca gigante, tapando todo).
   Causa raíz: las 4 páginas del dashboard (`index.html`, `history.html`,
   `config.html`, `calendario.html`) dependían 100% de
   `<script src="https://cdn.tailwindcss.com">` sin ningún respaldo — si
   ese script no carga (bloqueador, red, lo que sea) toda la interfaz pierde
   estilos. Fix real y duradero (a pedido explícito de usar
   `ui-ux-pro-max`): se generó `news_agent/assets/local.css` a mano con los
   valores REALES de Tailwind v3 para las ~150 clases que el proyecto
   realmente usa (extraídas con grep de las 4 páginas + su JS embebido), y
   se reemplazó el `<script>` del CDN por `<link rel="stylesheet"
   href="/assets/local.css">` en las 4 páginas. Cero cambios de HTML/JS —
   solo CSS, verificado que toda la funcionalidad (clicks, tabs, forms)
   sigue intacta. También se agregó `width="20" height="20"` nativos al
   `<img>` del logo del selector de marca (defensa adicional aunque ya no
   dependa del CDN).

8. **Animación de carga global**: pedido explícito — overlay con el logo
   circular de Andrés Duque + anillo girando mientras procesa, check verde
   al completar, luego se desvanece. `news_agent/assets/loading-overlay.js`
   (un solo archivo, se inyecta una vez, expone
   `window.mostrarCargando(mensaje)` / `completarCargando()` /
   `cancelarCargando()`), cableado en las 11 acciones de procesamiento real
   (generar contenido, IA, video, matriz de viralidad, etc.) de las 4
   páginas — NO en micro-acciones instantáneas como guardar 1 tema o 1 API
   key, sería ruido visual.

9. **Infraestructura del sistema (no del código)**: `ffmpeg` apareció
   desinstalado a mitad de sesión (instalado vía un tap de Homebrew distinto
   — `homebrew-ffmpeg/ffmpeg` — pero DESLINKEADO; `brew link ffmpeg` lo
   arregló sin reinstalar nada). La key de ElevenLabs se quedó sin créditos
   (0 de 10000) durante las pruebas — Andrés pegó una key nueva directo en
   el chat, ya actualizada en `.env` (sumar a la lista de keys a rotar antes
   de ir a producción, ver sección de pendientes técnicos).

**Pendiente de esta ronda**: no se corrió ningún video real con el fix #6
(queries concretas de B-roll) integrado — se validó el prompt contra la API
de Pexels directa, pero no un video completo con contenido generado 100% por
la IA (los últimos videos de prueba usaron guion+queries escritas a mano).

## Pendiente del roadmap (ver memoria `spec-agente-contenido-v2` para el detalle completo)

En orden sugerido:
1. ~~**Modo 3 — Generador de ideas por referentes**~~ HECHO (24 jul 2026):
   tercer botón "Ideas por referentes" junto a "Buscar noticias" e
   "Investigar". El usuario pega links de video (uno por línea) o sube
   archivo(s) → `referentes.py` descarga audio con yt-dlp, transcribe local
   con whisper.cpp (modelo `models/ggml-medium.bin`, symlink a un modelo ya
   descargado en `creador-de-videos/whisper.cpp/`, $0) → la IA (tarea
   `referentes` en `ia_config.json`, Gemini por defecto) saca tema, hook,
   estructura y por qué funciona de cada referente, y propone 3-5 ángulos
   propios que entran al mismo flujo de siempre ("elegís un ángulo → Crear
   contenido"). Endpoint `POST /api/referentes` (multipart: `links` JSON +
   `archivos`) en `dashboard/app.py`. Probado end-to-end con un video real de
   YouTube — funciona.

   **BUG encontrado y RESUELTO (27 jul 2026):** el pipeline asumía que el
   video tenía narración hablada (whisper transcribe audio) — con scrolls
   silenciosos de carrusel (sin audio) fallaba directo en
   `_extraer_audio_de_archivo`. Fix: `referentes.py` ahora detecta por
   video si tiene pista de audio (`_tiene_audio`, ffprobe) — si sí,
   transcribe como antes; si no, extrae 6 frames repartidos parejo
   (`_extraer_frames`, ffmpeg) y los manda a un modelo con visión. Se
   pueden mezclar ambos tipos en la misma tanda (algunos videos con voz,
   otros carruseles silenciosos). Nuevo `llm_client.generar_json_imagenes()`
   soporta Gemini y Claude con imágenes inline (Perplexity/OpenAI no están
   soportados para esta tarea todavía — error claro si el usuario los
   configura para "referentes" y hay un video sin audio). Probado
   end-to-end contra el endpoint real (`POST /api/referentes` con
   multipart, dos videos silenciosos reales) — ambos se analizaron bien.

   **BUG de privacidad encontrado y RESUELTO en esa misma prueba:** al
   analizar frames visuales, el modelo veía nombres/marcas escritos en
   pantalla (firma del creador, marca de agua) y los repetía en la
   respuesta (`inspirado_en`, etc.) — viola la regla de nunca atribuir
   cuentas de referencia (ver memoria `feedback-no-atribuir-creadores-
   referencia`). Fix: system prompt de `analizar_referentes()` ahora
   prohíbe explícitamente nombrar personas/marcas/handles aunque aparezcan
   visibles en el video, e instruye a referirse siempre como "Referente 1/
   2/...". Reprobado con los mismos dos videos — ya no aparecen nombres,
   solo "Patrón 1/2".
2. ~~Variantes A/B de hooks (2-3 por pieza) + versión TikTok vs Instagram automática.~~
   HECHO (24 jul 2026): selector de plataforma (Instagram/TikTok/Ambas) en la
   noticia — "Ambas" genera las dos versiones en paralelo y las muestra con
   tabs; botón "Variantes de hook (A/B)" en el output genera 3 hooks
   alternativos (ángulos: dato duro/pregunta/contrarian/urgencia/curiosidad)
   con botón "Usar" para reemplazar en vivo. Ver `generar_variantes_hook` en
   `generator_ia.py` y `/api/generar-variantes-hook` en `dashboard/app.py`.
3. ~~Parámetros de brief como instrucciones al LLM: ritmo de corte, texto en
   pantalla, tipo de música, velocidad de narración.~~
   HECHO (24 jul 2026): panel "⚙ Parámetros de producción" (solo formato
   video) con ritmo de corte / música / velocidad de narración / zoom-cámara
   — el LLM ajusta el guion según esos valores y el resultado incluye una
   caja "Instrucciones de producción" (para quien edita, no se aplica en el
   render automático — límite honesto ya conocido) + "Texto en pantalla
   sugerido" (frase + momento, generado siempre). Ver `_instruccion_parametros`
   en `generator_ia.py`.
4. ~~Analizar las plantillas de carrusel del usuario y ajustar
   `image_producer.py` para acercarse a ese estilo visual.~~ HECHO
   (27 jul 2026) — los 5 skins identificados en el material de referencia
   están implementados. `estilo_visual` (`editorial` | `prensa_ia` |
   `listicle` | `ilustracion` | `sketch` | `mockup_telefono`) seleccionable
   en el dashboard antes de generar carrusel/imagen/historia. "prensa_ia" es
   un skin tipo
   prensa/newsletter (papel crudo + tinta, badge de color sólido arriba,
   láminas de contenido en fondo oscuro con kicker de acento, cierre con
   caja de acento sólido) — inspirado en el patrón más repetido de las
   plantillas analizadas (ver `plantillas_referentes.md` y la memoria
   persistente de referencias). El acento sigue saliendo de
   `brand['accent_color']`, nunca hardcodeado. Ver `ESTILOS_VISUALES`,
   `_slide_html_prensa` y las plantillas `_PRENSA_*` en
   `image_producer.py`; wireado en `dashboard/app.py` (`ProducirIn.
   estilo_visual`) y el selector `#estilo-visual` en `dashboard/index.html`.
   Probado con un carrusel de 3 láminas — coincide con el patrón.

   **Segundo skin HECHO (27 jul 2026, misma tarde): `estilo_visual="listicle"`**
   — carrusel numerado 100% fondo negro (identidad de un solo tono, a
   diferencia de "prensa_ia" que alterna papel/oscuro): portada con kicker +
   título grande + hint "DESLIZA PARA VER →", láminas de contenido con
   número gigante de acento ("1.", "2."...) + título en mayúscula + cuerpo,
   footer con puntos de progreso (el activo se alarga, estilo indicador de
   stories) que se calculan solos a partir del paginador "i/N" — el hint de
   deslizar se oculta automáticamente en la última lámina antes del CTA.
   CTA en caja de acento sólido. Ver `ESTILOS_VISUALES`, `_slide_html_
   listicle`, las plantillas `_LISTICLE_*` y `_listicle_dots()` en
   `image_producer.py`; ya wireado en `dashboard/index.html` (opción
   "Listicle numerado" en el selector). Probado con un carrusel de 4
   láminas (hook/obstáculo/desarrollo/cta) — coincide con el patrón,
   incluyendo que el hint de swipe desaparece bien en la penúltima lámina.

   **Tercer, cuarto y quinto skin HECHOS (27 jul 2026, misma tarde) —
   los últimos 3 pendientes, todos de una:**
   - `estilo_visual="ilustracion"` — fondo pastel sólido fijo (#F4E3D7),
     muy minimalista (casi sin bullets): portada limpia sin elementos,
     láminas de contenido con una ilustración abstracta de "pedestales"
     (columnas de altura ascendente en color de acento, `_ilustracion_
     pedestales()`) en vez de bullets/gráficos, CTA en fondo oscuro
     invertido con caja de acento. Sin depender de ningún asset externo.
   - `estilo_visual="sketch"` — fondo blanco/crudo, tipografía serif
     (Georgia) para los títulos (distinto a los demás skins, todos
     sans-serif), con un boceto lineal SVG de un "camino con bifurcaciones"
     (`_SKETCH_CAMINO_SVG`) solo en la portada — variante más artística,
     evoca el estilo pizarra/sketch del patrón sin necesitar un asset
     dibujado a mano de verdad.
   - `estilo_visual="mockup_telefono"` — fondo oscuro, título con la
     última palabra resaltada en color de acento tipo marcador
     (`_mockup_resaltar()`, automático — no depende de que la IA marque
     qué palabra), mockup de teléfono en CSS puro (sin foto real) con
     grid 3×3 de "iconos de apps" (bloques de color sólido, nunca logos
     reales de terceros) en todas las láminas de contenido. Bug encontrado
     y arreglado en la prueba: el título se pisaba con el paginador
     "i/N" en la esquina — se le puso `max-width` al `h1`.

   Los 3 se probaron con un carrusel de 3 láminas + su historia cada uno —
   todos renderizan bien. **Nunca escribir los handles/nombres de las
   cuentas de referencia en ningún archivo del proyecto.**

   **Sexto y séptimo skin HECHOS (27 jul 2026, misma noche) — origen
   distinto: no vienen de un video de referencia, sino de la skill
   `/ui-ux-pro-max` (`--design-system`), a pedido del usuario, para tener
   una fuente de estilos nuevos cuando se acabe el material de referencia
   real. Ambos evitan cargar fuentes externas (system-ui/Georgia) para no
   depender de red al renderizar con Playwright:**
   - `estilo_visual="brutalista"` — inspirado en el design system "Kinetic
     Brutalism" que sugirió la skill (paleta acid + Lexend Mega, adaptado
     acá con tipografía de sistema). Fondo blanco, tinta negra, **cero
     border-radius en todo el skin** (`border-radius: 0 !important` global
     — único skin sin ninguna esquina redondeada), bordes gruesos (6-14px),
     título en mayúsculas enorme con tracking negativo, CTA de fondo lleno
     de color de acento con marco de 14px.
   - `estilo_visual="premium"` — inspirado en "Liquid Glass" (blur/glass
     no aplica a exportación estática, así que se adaptó a fondo casi
     negro cálido + tipografía elegante), con la tipografía real elegida
     vía `--domain typography "elegant premium editorial luxury"` (Playfair
     Display/Inter → acá serif de sistema con peso 300). Único skin
     **centrado** y de peso de texto liviano (el resto son bold/900) — la
     restricción es la firma, no el volumen. CTA con borde fino de acento
     en vez de caja rellena.

   Ambos probados (carrusel de 3 láminas + historia) — funcionan y se ven
   claramente distintos entre sí y de los otros 5. Van **7 skins en total**
   (`editorial` default + 6 más). Ver `ESTILOS_VISUALES` en
   `image_producer.py` para la lista completa.
5. ~~Plantillas para imágenes de post/historia~~ HECHO (27 jul 2026, ver
   sección "Plantillas de post/historia + fondos animados" más arriba): fix
   de un leak de carrusel en el skin listicle + fondos animados (Pexels/IA)
   para imagen suelta e historia.
6. ~~Métricas, banco evergreen, series recurrentes~~ HECHO. Métricas
   (`metricas_store.py`, botón/formulario en `/history`) y banco evergreen
   (`evergreen_store.py`, botón 🌲 en el dashboard) ya estaban hechos desde
   el 24 jul — este documento estaba desactualizado en eso. **Series
   recurrentes HECHO (28 jul 2026):** nuevo `series_store.py` — una serie
   es nombre + día de la semana fijo + tema/formato/canal por defecto (ej.
   "Lunes de IA"). Al generar una semana en `/calendario`
   (`calendario_store.generar_semana()`), cada serie ACTIVA agrega su
   propio slot en su día correspondiente, ADEMÁS del reparto round-robin
   normal (no lo reemplaza — es una cita fija garantizada). El slot queda
   marcado con `serie_id`/`serie_nombre` y se ve con un badge "🔁 Nombre" en
   su tarjeta. Panel "🔁 Series" en `/calendario` (junto a "⚙ Config") con
   alta/baja, toggle activa/inactiva y borrado — endpoints `/api/series*`
   en `dashboard/app.py`. Probado end-to-end contra el servidor real (curl
   + clic real en el dashboard): serie "Lunes de IA" (carrusel, tema
   precargado) apareció correctamente en su lunes al generar la semana.

   **Incidente de datos (28 jul 2026):** al limpiar después de esta prueba
   se borró `calendario.jsonl` ENTERO por error (en vez de filtrar solo el
   slot de prueba) — ese archivo tenía datos reales del planificador desde
   el 24 jul, se perdieron sin poder recuperarlos (sin backup ni Time
   Machine accesible). Ver memoria `feedback-no-borrar-archivos-datos-en-
   limpieza`: de acá en más, limpiar SIEMPRE filtrando por id/slug de la
   prueba, nunca borrando el archivo.
7. ~~Matriz de viralidad + simulador~~ HECHO (28 jul 2026, idea traída de un
   PDF de un tercero, ver sección propia más arriba): detecta patrones
   (hooks/temas/estructura/frases/CTAs) comparando piezas propias con
   métricas cargadas, y un simulador que cruza un guion nuevo contra la
   matriz antes de producirlo. 100% con datos ya guardados en la app, sin
   Apify ni scraping nuevo.

**Ideas nuevas evaluadas (24 jul 2026)** — Andrés mostró el video "Comenta
SANTIA" (5 skills de Claude para 160 Reels/mes). De esas 5: generador de
ideas por competidores = Modo 3 (ya hecho, arriba) y copywriter = ya
cubierto por `generator_ia.py` + variantes de hook.
- ~~Planificador de contenido~~ HECHO (24 jul 2026): `/calendario` (ícono
  📅 en el header del dashboard). `calendario_store.py` guarda slots
  (fecha/formato/canal/tema/estado) en `calendario.jsonl` + config
  (canales activos, objetivo semanal por formato: video/carrusel/imagen)
  en `calendario_config.json`. Vista semanal Lunes-Domingo (grid de 7
  columnas en desktop, 1 en mobile), navegación entre semanas, botón
  "Generar semana" que reparte el objetivo configurado round-robin entre
  días y canales activos (no pisa una semana ya planificada salvo que se
  confirme regenerar). Cada slot es editable inline (formato/canal/tema/
  estado pendiente→listo→publicado) y se puede agregar/borrar suelto por
  día. NO publica nada ni se integra (todavía) con "Crear contenido" —
  es solo el mapa de la semana; el campo `slug` queda preparado para
  asociarlo a una producción real más adelante si se quiere. Endpoints
  bajo `/api/calendario/*` en `dashboard/app.py`. Probado end-to-end
  (generar semana, editar tema, cambiar estado — persistencia verificada
  con curl).
- ~~Reels de prueba en volumen~~ HECHO (28 jul 2026, ver sección propia más
  arriba): combinaciones hook×CTA para video, producción en batch y
  tracking de ganador por métricas en `/history`.
- Diseñador de lead magnets (documentos de valor con marca/naming) — sigue
  sin roadmapear; tipo de output distinto a lo que genera hoy el sistema
  (reels/carruseles).

## Pendiente técnico / seguridad

- **Rotar las keys reales que se pegaron en el chat**: ElevenLabs (3 —
  la original, una segunda el 30 jul, y una TERCERA el 4 ago cuando la
  segunda se quedó sin créditos — 0 de 10000 — de tanto probar), Pexels,
  Gemini, Perplexity. Ninguna es free tier real (son keys viejas del
  usuario) — cuando termine la fase de pruebas, rotarlas desde cada
  plataforma y volver a pegarlas en `/config`. **CRÍTICO antes de subir el
  repo a cualquier lado público**: confirmar que `.env` esté en
  `.gitignore` y nunca se haya commiteado.
- Todavía no hay key real de Anthropic/Claude configurada (se probó y dio
  401 esperado con una key inválida de prueba).
- **`fuente_texto` en `producir_video()` quedó sin efecto** desde la
  reestructuración del 1-5 ago — libass necesita un `.ttf` local y solo
  tenemos Poppins en `fonts/`. Si se quiere volver a soportar variar la
  tipografía del subtítulo, hay que sumar más `.ttf` a esa carpeta.
- **`extraer_frame_mejor_momento()` (historia-teaser) ya no puede evitar
  el subtítulo al elegir un frame** — desde que el video quema subtítulos
  completos (sin huecos), cualquier frame trae texto parcial quemado
  abajo. No implementado: recortar esa franja al componer el frame de
  fondo de la historia.

## Preferencias del usuario (para no perderlas)

- Llamarlo **"mor"** en la conversación.
- Respuestas cortas, sin resúmenes largos innecesarios.
- Marca "HAM Agencia" (no "HAN Agency" — error de tipeo ya corregido, ojo si vuelve a aparecer).
- Prioriza $0/simple cuando hay opción, salvo que pida explícitamente lo contrario.

## Notas técnicas para quien retome (no repetir estos tropiezos)

- **Puerto 8765 puede tener un servidor viejo corriendo** (de una sesión
  anterior, sin los últimos endpoints) — si el dashboard no refleja cambios
  recién hechos, chequear `lsof -iTCP:8765` y reiniciar el proceso.
- **El panel del Browser (Claude Code) es angosto** (~611px nativo) — no usar
  `resize_window` a anchos grandes (ej. 1400px) para probar layouts
  responsive, porque el usuario ve ese mismo panel y todo le queda diminuto.
  Si hace falta, volver a `preset: "desktop"` (tamaño nativo) apenas se
  termina la prueba.
- **El panel del Browser (Claude Code) NO tiene salida a internet** —
  confirmado con `curl`/`fetch` fallando resolución DNS (agosto 2026). Solo
  puede llegar a `localhost`. Cualquier página que dependa de un CDN
  externo (Tailwind, Google Fonts, etc.) se va a ver rota AHÍ aunque el
  código esté perfecto — no asumir que es un bug real sin verificar
  primero si el usuario lo ve roto en SU navegador real (con internet).
- **Dashboard ya NO depende de `cdn.tailwindcss.com`** — usa
  `news_agent/assets/local.css` (generado a mano, cubre las clases
  Tailwind realmente usadas). Si se agrega una clase Tailwind nueva a
  cualquiera de las 4 páginas del dashboard, hay que sumarla también a ese
  CSS a mano — no hay build step ni compilador, es estático.
- **`ffmpeg` puede aparecer "instalado pero no encontrado"** (visto el 4
  ago 2026: instalado vía el tap `homebrew-ffmpeg/ffmpeg` pero
  deslinkeado) — antes de reinstalar, probar `brew link ffmpeg` primero
  (no destructivo).
- **Subtítulos y B-roll del video comparten la misma agrupación por
  oración** (`video_producer._oraciones_por_tramo()` /
  `_limites_oraciones_sin_huecos()`) — si se toca el timing de uno, hay
  que revisar el otro, están acoplados a propósito para que el corte de
  escena y el cambio de cartel coincidan siempre.
