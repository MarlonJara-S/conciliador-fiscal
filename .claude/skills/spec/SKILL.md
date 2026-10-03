---
name: spec
description: Entrevista al usuario sobre una nueva versión o funcionalidad y escribe docs/SPEC.md
disable-model-invocation: true
---
Quiero construir: $ARGUMENTS

Entrevístame en detalle usando la herramienta AskUserQuestion.
Pregunta sobre implementación técnica, modelo de datos, concurrencia, fallos parciales, seguridad, costos de LLM, casos límite y tradeoffs.
No hagas preguntas obvias: enfócate en las partes difíciles que quizá no he considerado.

Cuando hayamos cubierto todo, escribe docs/SPEC.md con:
- Problema y objetivo de esta versión.
- Alcance y lo que queda FUERA de alcance.
- Archivos e interfaces involucrados.
- Riesgos y decisiones abiertas.
- Definición de terminado con métricas verificables.
- Un paso final de verificación de punta a punta.
