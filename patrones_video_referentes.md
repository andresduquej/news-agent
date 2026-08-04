# Patrones de comunicación en video — cuentas referentes

Banco de patrones extraído de 75 videos reales (transcripción de audio + caption/copy)
de 5 cuentas referentes del nicho IA/marketing digital/emprendimiento (28-29 jul 2026),
con permiso y sesión logueada del usuario. Excluye contenido personal/vlog (viajes,
cumpleaños, vida familiar) — solo se analizó contenido laboral/informativo, según pidió
el usuario. Nunca se registran handles/nombres de las cuentas — se identifican como
"Cuenta A" a "Cuenta E" en todo el proyecto, ver `feedback-no-atribuir-creadores-referencia`.

Uso: sirve como referencia para ajustar `generator_ia.py` (estructura/tono de guiones)
y el copy/caption que genera la app, para acercar el estilo a lo que ya funciona en el
nicho — nunca para copiar contenido literal.

---

## Resumen

El corpus muestra una tendencia clara hacia educar y empoderar emprendedores en IA y
marketing digital: soluciones prácticas a problemas comunes, foco en eficiencia/
automatización, y búsqueda activa de engagement con CTAs de "comentá X y te lo mando".

## Hooks que se repiten

1. **Problema/frustración directa al inicio** — nombrar el dolor exacto del público ya
   en el hook (ej. "quedarte sin tokens no se arregla pagando más", "tu contenido tiene
   buenas vistas pero no vende").
2. **Afirmación audaz que desafía una creencia instalada** — declarar algo contraintuitivo
   de entrada ("no necesitas pagar edición", "el modelo más potente ya no es el más caro").
3. **Pregunta directa al espectador** — abre con una pregunta que obliga a autoevaluarse
   o reaccionar ("¿qué es lo más cool que hiciste con Claude?", "¿cuánto tiempo perdés
   buscando audio para tus videos?").
4. **Promesa de secreto/hack revelado** — anuncia que va a compartir algo puntual y
   accionable ("comandos que usan los que trabajan rápido", "cómo pasé de 1 video a
   300 millones de reproducciones").

## Estructuras narrativas

- **Problema → solución concreta**: la más común — plantea una ineficiencia real y
  cierra con una herramienta/método específico para resolverla.
- **Lista/top**: formato "N herramientas/hábitos/comandos que...".
- **Tutorial corto paso a paso**: instrucciones directas para implementar algo ya.
- **Anécdota personal como prueba**: comparte una experiencia propia para respaldar el
  consejo (da credibilidad sin ser un caso de estudio formal).
- **Entrevista/testimonio con cifras**: presentar a alguien contando su facturación +
  un consejo concreto (menos frecuente, una sola cuenta lo usa como formato fijo).

## Patrón de copy/caption

- **Emojis abundantes y funcionales** — no decorativos sueltos, se usan para separar
  ideas y guiar la lectura (👀🔥🚀💡🤯✅💰), presente en las 5 cuentas sin excepción.
- **Tono directo/conversacional**, que se adapta: informativo en contenido de IA,
  motivacional en contenido de mentalidad emprendedora.
- **Longitud variable** — desde una sola línea hasta varios párrafos explicando un
  proceso; no hay una regla fija de "corto siempre".
- **Hashtags mixtos**: 2-3 amplios (#ia, #marketingdigital) + 1-2 específicos del nicho
  o de la pieza puntual.

## CTAs que se repiten

1. **"Comentá [PALABRA] y te lo mando"** — el más prevalente por lejos; convierte el
   CTA en una micro-acción de bajo esfuerzo que además alimenta el algoritmo con
   comentarios. Confirmado en capturas reales: la gente literalmente responde la
   palabra pedida.
2. **"Seguime para más [tema]"** — el CTA genérico de crecimiento de cuenta, presente
   en las 5 cuentas.
3. **"Guardá este video"** — pedido de guardar como recordatorio/oportunidad futura.
4. **Pregunta abierta en comentarios** — cierra pidiendo opinión/experiencia propia del
   espectador, genera debate en vez de una sola respuesta esperada.

## Temas recurrentes del nicho

- Uso práctico/avanzado de IA (Claude en particular) para negocio y creación de contenido.
- Estrategia de marketing digital y crecimiento (ecommerce, ventas, automatización).
- Mentalidad de emprendedor (disciplina, enfoque, hábitos, superar obstáculos).
- Optimización de creación/edición de contenido (video/imagen/texto) con IA.
- Recomendación de herramientas/recursos para productividad.

---

**Próximo paso (no implementado aún, pendiente de que Andrés confirme dirección):**
ajustar los system prompts de `generator_ia.py` (hook/estructura del guion) y del
copy/caption para incorporar estos patrones — sobre todo el CTA de "comentá X" (hoy
`generator_ia.py` no lo contempla como opción) y la variedad de estructuras (hoy todo
video sigue rígido hook→obstáculo→ejecución→CTA, sin la variante "problema→solución
directa" ni "lista/top" que se repiten tanto en el nicho real).
