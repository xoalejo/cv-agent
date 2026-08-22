# Revisión de calidad: reutilización, simplificación, eficiencia y altitud

**Rama:** `main`
**Fecha:** 2026-08-21

Cuatro revisiones independientes sobre las ~4.000 líneas del proyecto. Lo
relevante no fue el ahorro de líneas sino tres defectos que ninguna prueba
cubría.

## Defectos corregidos

**El handler bloqueaba el bucle de eventos.** `create_response` era `async def`
pero el caso de uso es síncrono de principio a fin y tarda segundos. FastAPI
ejecuta los handlers `async` en el bucle, así que **ninguna otra petición de la
instancia avanzaba** durante un turno. Se corrige quitando la palabra `async`:
los handlers `def` van al threadpool.

**El mismo mensaje viajaba con dos identificadores.** El envoltorio de
`response.completed` generaba un `msg_...` nuevo en lugar de reutilizar el de los
eventos del ítem. Un cliente que correlacione por id vería aparecer un mensaje
distinto justo al cerrar.

**Un fallo a mitad de flujo reiniciaba la numeración.** `stream_error` emitía
`sequence_number: 0` cuando ya se habían enviado los eventos 0 a 3. Además la
rama de streaming perdía el `Retry-After` que la síncrona sí propagaba.

## Fugas entre capas

Las excepciones del motor vivían en el adaptador de OpenAI, así que la capa HTTP
importaba infraestructura concreta para traducirlas y un motor alternativo
tendría que importar el módulo de OpenAI para lanzar los tipos correctos. Pasan a
`src/application/errors.py`: son parte del contrato del puerto.

## Simplificaciones

- `streaming.py` pasa de 238 a 158 líneas. El emisor es ahora una clase que posee
  el contador y los identificadores durante todo el turno, que es lo que hace
  imposible el defecto de numeración.
- El mapeo excepción → respuesta vive en una tabla, no repartido en seis bloques
  `except` con los mensajes escritos dos veces.
- `execute` y `execute_stream` comparten `_apply_tool_calls` y `_exhausted`; los
  bucles siguen separados porque invocan métodos distintos del motor.
- Los tres `find_*` del dominio derivan de un helper común.
- `CaseResult.passed` pasa a derivarse de `failures` en lugar de almacenarse.

## Residuo de las patentes

La rúbrica de `honestidad-dominio-ausente` seguía diciéndole al juez que el
agente podía mencionar "las patentes sobre pagos con contratos inteligentes":
premiaba mencionar datos que ya no existen. La tarjeta de agente pública seguía
proponiendo "Cuéntame de sus patentes" como pregunta de ejemplo.

## Medido, no supuesto

El agente de eficiencia midió cuatro sospechas y las descartó: `build_instructions`
cuesta 18 µs contra un turno de 1.130 ms, el índice léxico se construye una sola
vez, las expresiones regulares están compiladas a nivel de módulo y la
acumulación de texto en el flujo ya usaba el patrón óptimo. Se corrigieron solo
las que resultaron reales.

155 pruebas, incluidas tres de regresión para los defectos anteriores. 29 casos
de evaluación en verde contra producción.
