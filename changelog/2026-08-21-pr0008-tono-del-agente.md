# El agente representa la trayectoria, no audita el CV

**Rama:** `main`
**Fecha:** 2026-08-21

## Síntoma

Ante "¿para qué clientes implementó los pipelines RAG?", el agente abría con
"El CV no especifica los nombres de los clientes...". La respuesta era correcta y
honesta, pero se leía como un informe de lo que falta en lugar de como alguien
que habla del trabajo hecho.

## Causa

La instrucción propia lo provocaba. La sección sobre preguntas no cubiertas
ordenaba, como **primer** paso, "di con claridad que ese dato no está en su CV".
El modelo la seguía al pie de la letra y abría en negativo.

## Corrección

Se invierte el orden: primero lo que el perfil sí respalda (sector, tecnología,
resultado medible) y solo después, en una frase neutra al final, el alcance del
documento. "Su CV detalla los sectores y los resultados, no los nombres de los
clientes" en lugar de abrir con la ausencia.

**No cambia la regla de fundamento.** Sigue prohibido inventar; cambia desde
dónde se responde, no qué se afirma. La misma pregunta ahora responde con el
sector, el stack completo y las métricas de impacto, y cierra con una línea sobre
el nivel de detalle del CV.

## Verificación

Dos casos nuevos en la categoría `tono` que fallan explícitamente si la primera
frase es una negación, y que siguen fallando si inventa nombres de clientes.

También se añade `docs/registro-en-la-plataforma.md`, con la configuración exacta
del alta, dónde vive cada secreto y cómo reconstruir el despliegue desde cero.

153 pruebas; 28 casos de evaluación.
