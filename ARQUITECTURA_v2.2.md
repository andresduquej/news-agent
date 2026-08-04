# Agente de Contenido con IA — Documento de Arquitectura v2.2

**HAN Agency · Andrés Duque**
Julio 2026 · Fase Beta Local → Escala equipo HAN

v2.2 fusiona v2.0 (estado real del pipeline) + v2.1 (mejoras de Gemini: Playwright, FastAPI,
brand_config completo) y resuelve la única contradicción entre ambos: un solo pipeline de video
de prueba (no tres en paralelo), acorde al plan de Claude Code actual del usuario.

---

## 1. Resumen Ejecutivo

Agente que automatiza: selección de tema → búsqueda de información → ranking por potencial
de contenido → generación de brief/guión → producción de video, carrusel o imagen → entrega
para revisión.

Uso inicial: interno, para Andrés Duque (personal) y HAN Agency (agencia), con dashboard local.
Escala a equipo HAN solo después de validar el flujo con uso real — no antes.

## 2. Problema que Resuelve

- Monitorear fuentes de noticias/información a diario toma tiempo.
- El proceso manual (tema → formato → guión → producción → publicación) toma horas.
- Sin sistema, el output es inconsistente.
- A escala de agencia, el problema se multiplica por cliente.

## 3. Estado Actual (punto de partida real)

Pipeline funcional en Python, por CLI (`run.py`), costo $0:

```
Fetcher (RSS Google News) → Filter (heurística) → Generator (briefs) → Exporter →
Video/Imagen/Carrusel (say + ffmpeg, placeholder de prueba)
```

Este documento evoluciona ese pipeline, no lo descarta.

## 4. Visión del Producto

### 4.1 Fase Beta (actual)
- Dashboard local (FastAPI sirviendo frontend).
- Dos perfiles de marca: Andrés Duque personal y HAN Agency.
- Costo operativo mínimo (free tiers + Claude API + ElevenLabs a bajo consumo).
- Objetivo: validar el flujo completo y que el output sea de calidad publicable.
- **Sin login, sin roles.** Mono-usuario.

### 4.2 Fase Producción (solo si Beta valida)
- Dashboard hosteado (Railway/Render, ~$5-10/mes).
- Login y roles cuando entre el equipo de HAN Agency.
- Multi-cuenta real por cliente.
- Seguridad se diseña en ese momento, no antes.

## 5. Flujo del Agente (Flujo A — Actualidad, el único que se construye ahora)

1. **Gestión de temas**: lista dinámica de keywords — agregar, quitar, seleccionar.
   Se guarda lo consultado; no es una lista fija.
2. **Fetcher**: RSS Google News según tema elegido.
3. **Filter**: heurística por keyword/fecha/tema, acota el universo antes de gastar en IA.
4. **Ranker**: Claude API evalúa el subconjunto ya filtrado (nunca el feed crudo, por costo).
   Devuelve TOP 5 con score 1-10 y justificación (relevancia, novedad, engagement, aplicabilidad).
5. **Selección de perfil de marca**: Andrés Duque o HAN Agency → define logo, colores, tono,
   hashtags base del output.
6. **Selección de formato**: video (9:16/16:9/1:1), carrusel (1:1/4:5) o imagen estática.
   El agente sugiere el óptimo según el tipo de noticia.
7. **Generator**: guión (video) / copy slide por slide (carrusel) / headline+copy (imagen),
   más caption y hashtags.
8. **Producción**:
   - **Carrusel / imagen estática**: HTML/CSS + Playwright (headless) → render 100% fiel al
     branding, $0, sin riesgo de texto alucinado. Ideogram queda como fallback solo para
     arte conceptual generativo (no para texto).
   - **Video**: pipeline único de prueba — **ElevenLabs (voz) + Pexels API (B-roll) + FFmpeg**.
     Higgsfield queda como gate opcional a validar después, NO como parte del build inicial
     (ver §8). Remotion + Kie AI + Apify queda anotado como alternativa futura si este pipeline
     no convence (ver §14).
9. **Revisión y entrega**: dashboard muestra guión/imagen/video, caption, hashtags.
   Aprobar / ajustar / descartar. Se guarda en historial.

### Flujo B — Aprende algo / Educativo (NO se construye en esta fase)
Tema libre que no vive en un feed RSS, requiere búsqueda web abierta, un solo resultado curado.
Queda documentado como capacidad futura, se retoma después de validar el Flujo A con uso real.

## 6. Stack Tecnológico

| Componente | Herramienta | Estado | Costo Beta |
|---|---|---|---|
| Backend/API | FastAPI (Python) | Por crear | $0 |
| Ranking | Claude API (Sonnet) | En uso | ~$3-8/mes |
| Búsqueda de noticias | RSS (Google News) | Ya funciona | $0 |
| Filtro | Heurística Python local | Ya funciona | $0 |
| Carruseles/imagen | HTML/CSS + Playwright | Por integrar | $0 |
| Arte generativo (fallback) | Ideogram API | Por integrar | $0 (free tier) |
| Voz | ElevenLabs API | Por integrar | $0–5/mes (free tier ~10 min/mes) |
| B-roll de video | Pexels API | Por integrar | $0 |
| Ensamblado de video | FFmpeg | Ya funciona | $0 |
| Video generativo AI | Higgsfield | Gate opcional, no bloqueante | $0 mientras se valida |
| Dashboard UI | HTML/JS/Tailwind vía FastAPI | Por construir | $0 |
| Servidor (Fase 2) | Railway o Render | N/A en beta | $0 |

**Total Beta estimado: ~$5-12/mes** (asumiendo se supera el free tier de ElevenLabs).

## 7. Arquitectura de Módulos

| Módulo | Función | Estado |
|---|---|---|
| `topics_store` | CRUD de temas/keywords dinámicos | Nuevo |
| `fetcher` | RSS según tema seleccionado | Existe, se adapta |
| `filter` | Heurística keyword/fecha/tema | Existe |
| `ranker` | Claude API sobre subconjunto filtrado, TOP 5 justificado | Nuevo |
| `generator` | Guión/copy/headline + caption + hashtags | Existe |
| `brand_config` | 2 perfiles de marca en JSON | **Ya existe** (`brand_config.json`) |
| `image_producer` | Playwright HTML-to-image + Ideogram fallback | Nuevo |
| `video_producer` | ElevenLabs + Pexels + FFmpeg (único, ver §8) | Nuevo |
| `history_store` | Historial de contenidos generados | Existe (exporter), se formaliza |
| `dashboard` | Backend FastAPI + UI en navegador | Nuevo |

Diseño mono-usuario: sin login ni roles en esta fase.

## 8. Validación de Higgsfield (gate opcional, no bloqueante)

Higgsfield **no** es parte del build inicial. Se prueba aparte, cuando haya tiempo/créditos:
1. Prompt corto de prueba, medir latencia y costo/crédito por segundo de video.
2. Si es estable y barato, se evalúa como reemplazo del pipeline ElevenLabs+Pexels+FFmpeg.
3. Si no, el pipeline por defecto (ElevenLabs+Pexels+FFmpeg) sigue siendo el único.

Esto evita construir contra tres motores de video en paralelo con un plan de Claude Code limitado.

## 9. Configuración de Marca (`brand_config.json`, ya creado)

Dos perfiles ya definidos con logos y colores reales del usuario:

- **Andrés Duque**: `#3956FA` / `#A542F3` / `#2BCBFF`, tono cercano y directo,
  audiencia emprendedores digitales LatAm, hashtags genéricos por ahora.
- **HAN Agency**: `#E94560` / `#1A1A2E` / `#2BD9FF`, tono profesional pero cercano,
  misma audiencia.

Pendiente: guardar los logos reales en `news_agent/assets/andres-duque-logo.png` y
`news_agent/assets/han-agency-logo.png` (el usuario los tiene, faltan copiarlos a esa ruta).

## 10. Dashboard — Vistas

1. **Inicio**: selector de perfil (Andrés/HAN), gestión de temas (agregar/quitar/seleccionar).
2. **Resultados**: TOP 5 con score y justificación, botón "Crear contenido" por ítem.
3. **Formato**: selector de tipo y dimensiones, sugerencia automática.
4. **Output**: guión/brief, caption, hashtags. Botones "Producir video" / "Generar imagen" /
   "Descargar brief".
5. **Historial**: contenidos generados, filtrable por perfil.

## 11. Roadmap de Implementación

**Sprint 0 — Setup y validación de medios**
- Setup FastAPI (servidor local).
- Prueba de renderizado HTML→imagen con Playwright.
- Prueba real de ElevenLabs + Pexels + FFmpeg con un guión corto (medir calidad y costo real).

**Sprint 1 — Dashboard mínimo + temas dinámicos**
- `topics_store` (CRUD).
- Dashboard sirviendo fetcher + filter existentes.
- Selector de perfil de marca (ya hay JSON, falta UI).

**Sprint 2 — Ranker con Claude**
- Integrar Claude API sobre el subconjunto ya filtrado.
- TOP 5 con score y justificación en el dashboard.

**Sprint 3 — Generación y producción**
- Conectar `generator` + `brand_config` al dashboard.
- `image_producer`: Playwright + Ideogram fallback.
- `video_producer`: ElevenLabs + Pexels + FFmpeg.

**Sprint 4 — Historial y pulido**
- `history_store` visible en dashboard.
- Ajuste de prompts según calidad real de outputs.
- Empaquetar para correr local con un solo comando.

**Fuera de este roadmap** (documentado, no se construye ahora): Flujo B educativo,
validación de Higgsfield, hosting Railway/Render, login/roles multi-usuario, Remotion como
alternativa de video.

## 12. Costos Proyectados — Beta

| Herramienta | Plan | Costo mensual |
|---|---|---|
| FastAPI / servidor local | Local | $0 |
| Claude API (ranking) | Pay per use | ~$3-8 |
| RSS feeds | Gratis | $0 |
| Playwright (carruseles) | Código local | $0 |
| ElevenLabs | Free tier / Starter | $0-5 |
| Pexels API | Gratis | $0 |
| Ideogram | Free tier | $0 |
| Higgsfield | No se usa en beta | $0 |
| **TOTAL BETA** | | **~$3-13/mes** |

## 13. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Texto alucinado en carruseles por IA | Media | HTML-to-Image vía Playwright, render tipográfico exacto |
| ElevenLabs+Pexels+FFmpeg no da calidad publicable | Media | Se trata como piloto en Sprint 0 antes de comprometerse; si falla, se evalúa Higgsfield o Remotion (§14) |
| Sobrecosto en Claude API por payloads grandes | Baja | El filtro heurístico reduce a <20 ítems antes de llamar a la API |
| Plan de Claude Code limitado se agota probando 3 motores de video | Alta si no se prioriza | Un solo pipeline de video en el build (§8); alternativas quedan documentadas, no construidas |
| Dashboard local no escala a equipo | Baja en beta | Migración a servidor + login en Fase Producción, solo si Beta valida |

## 14. Alternativas descartadas por ahora (quedan documentadas, no se construyen)

- **Higgsfield AI**: gate opcional post-beta (§8).
- **Remotion + ElevenLabs + Kie AI + Apify**: sistema visto en referencia externa
  (video de Santiago Muñoz), más potente pero requiere levantar un proyecto de código
  aparte (Remotion) y gestionar 3 APIs de pago. Se reevalúa solo si ElevenLabs+Pexels+FFmpeg
  no alcanza calidad publicable.

## 15. Próximos Pasos Inmediatos

1. Copiar los dos logos a `news_agent/assets/`.
2. Ejecutar Sprint 0: setup FastAPI + prueba Playwright + prueba ElevenLabs/Pexels/FFmpeg.
3. Abrir sesión de ejecución (ya no de planeación) y comenzar Sprint 1.
