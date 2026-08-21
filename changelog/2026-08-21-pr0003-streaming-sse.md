# Streaming SSE del contrato Open Responses

**Rama:** `main`
**Fecha:** 2026-08-21

## Motivación

El streaming era la única pieza del contrato que no implementábamos. No es
requisito del reto, pero cerrarlo elimina la necesidad de declarar una
compatibilidad parcial.

## Qué se implementó

La secuencia completa de eventos del protocolo: `response.created`,
`response.in_progress`, `response.output_item.added`,
`response.content_part.added`, los `response.output_text.delta`, el cierre de
cada nivel (`output_text.done`, `content_part.done`, `output_item.done`),
`response.completed` y el terminador literal `[DONE]`, con `sequence_number`
correlativo y `Content-Type: text/event-stream`.

El identificador de respuesta se genera al abrir el flujo y se mantiene estable:
los primeros eventos salen antes de que el proveedor devuelva el suyo, y
cambiarlo a mitad rompería a un cliente que correlacione por `id`.

El ciclo de herramientas es el mismo en ambos modos. Las llamadas se resuelven
dentro del servicio y solo el texto de la respuesta final llega al cliente.

## El problema que no era evidente

**El streaming abría un agujero en la política de divulgación.** El guarda
existente revisa la respuesta completa y redacta lo que tenga forma de teléfono.
Al emitir fragmentos conforme se generan, ese texto completo nunca existe, y lo
ya emitido no se puede retirar: un número repartido en varios trozos saldría sin
que ningún fragmento coincidiera con el patrón.

`StreamingDisclosureGuard` lo resuelve reteniendo la cola. Mientras el final del
texto acumulado pueda ser el principio de algo con forma de teléfono, esa parte
no se emite. Se libera cuando llega texto que demuestra que no lo era, o al
cerrar el flujo.

Las pruebas fijan la propiedad concreta: un número troceado en cinco fragmentos
no produce ningún fragmento con sus dígitos, mientras métricas (`17,000+`),
expedientes (`MX/a/2024/008296`) y normas (`IATF 16949`) pasan intactos.

## Efecto en la tarjeta de agente

`capabilities.streaming` pasa a `true`, ahora que corresponde a lo que el
servicio hace. También se corrigió `preferredTransport`, que declaraba `JSONRPC`
cuando el transporte real es `HTTP+JSON`, y se añadió `supportedInterfaces`, que
la plataforma exige para importar la tarjeta.

## Archivos

- `src/domain/streaming_guard.py` (nuevo)
- `src/interfaces/http/streaming.py` (nuevo)
- `src/application/ports.py`, `src/application/conversation.py`
- `src/infrastructure/openai_engine.py`
- `src/interfaces/http/routes.py`, `src/interfaces/http/agent_card.py`

140 pruebas en verde. Verificado contra el modelo real en local y en producción.
