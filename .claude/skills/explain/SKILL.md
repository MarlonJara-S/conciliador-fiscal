---
name: explain
description: Explica un concepto técnico a fondo usando el código del proyecto y luego evalúa la comprensión del usuario
disable-model-invocation: true
---
Explícame a fondo: $ARGUMENTS

1. Explica el concepto desde los fundamentos, sin asumir que lo conozco bien.
2. Muestra dónde aparece (o debería aparecer) en el código de este proyecto, con archivo y línea.
3. Dame un experimento pequeño que pueda correr para verlo en acción (por ejemplo, un script o un EXPLAIN ANALYZE).
4. Hazme 3 preguntas de comprensión, una a la vez, y espera mi respuesta antes de la siguiente.
5. Al final, resume en inglés en 3 líneas lo que aprendí para agregarlo a docs/LEARNING_LOG.md.
