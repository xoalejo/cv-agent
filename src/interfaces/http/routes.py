"""Rutas HTTP: la entrega del caso de uso por el contrato Open Responses."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from src.application.conversation import AnswerProfileQuestion
from src.application.errors import (
    LLMConfigurationError,
    LLMEngineError,
    LLMRateLimitError,
)
from src.infrastructure.profile_data import StaticProfileRepository
from src.interfaces.http.agent_card import build_agent_card
from src.interfaces.http.schemas import ResponsesReply, ResponsesRequest
from src.interfaces.http.security import authorize
from src.interfaces.http.streaming import OpenResponsesStream

logger = logging.getLogger(__name__)

router = APIRouter()

#: Traducción de un fallo del proveedor a la respuesta que ve el cliente.
#:
#: Vive en una tabla y no repartida en bloques `except` porque las dos rutas, la
#: síncrona y la de streaming, deben comunicar lo mismo. Escritos por separado ya
#: habían divergido: la de streaming perdía el `Retry-After`.
#:
#: El orden importa: las subclases primero, porque la traducción se resuelve con
#: la primera coincidencia.
_ERRORES: tuple[tuple[type[LLMEngineError], int, str], ...] = (
    (
        LLMRateLimitError,
        status.HTTP_429_TOO_MANY_REQUESTS,
        "El proveedor del modelo alcanzó su límite de uso. Reintenta en unos segundos.",
    ),
    (
        LLMConfigurationError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "El agente no está configurado correctamente.",
    ),
    (
        LLMEngineError,
        status.HTTP_502_BAD_GATEWAY,
        "El modelo no está disponible en este momento. Intenta de nuevo.",
    ),
)


def _traducir(exc: LLMEngineError) -> tuple[int, str]:
    """Código y mensaje público para un fallo del proveedor.

    El detalle real ya quedó en los logs del adaptador; lo que sale de aquí no
    revela nada de la infraestructura.
    """
    return next(
        (codigo, mensaje) for tipo, codigo, mensaje in _ERRORES if isinstance(exc, tipo)
    )


def get_use_case(request: Request) -> AnswerProfileQuestion:
    """Recupera el caso de uso, construyéndolo si el arranque no lo dejó listo.

    Normalmente lo ensambla el `lifespan` al arrancar el proceso. Pero en un
    entorno serverless ese ciclo no siempre se ejecuta, y sin esta reserva el
    endpoint respondería 503 pese a estar bien configurado. Se construye una vez
    y se guarda en el estado de la aplicación, así que el costo lo paga como
    mucho la primera petición de cada instancia.
    """
    use_case = getattr(request.app.state, "answer_question", None)
    if use_case is not None:
        return use_case

    from src.config import get_settings
    from src.interfaces.http.app import build_use_case

    try:
        use_case = build_use_case(get_settings())
    except ValueError:
        # Falta la credencial del proveedor: es un fallo de configuración, no una
        # caída, y se distingue como tal.
        logger.error("El agente no pudo inicializarse: falta configuración")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El agente no está configurado correctamente.",
        ) from None

    request.app.state.answer_question = use_case
    return use_case


@router.get("/health", tags=["operación"])
async def health(request: Request) -> dict[str, object]:
    """Sonda de salud, sin autenticación, para los healthchecks del hosting.

    No revela configuración: solo si el servicio está arriba y si el motor quedó
    inicializado.
    """
    return {
        "status": "ok",
        "agent": "cv-agent",
        "engine_ready": getattr(request.app.state, "answer_question", None) is not None,
    }


def _streaming_response(
    payload: ResponsesRequest, use_case: AnswerProfileQuestion
) -> StreamingResponse:
    """Devuelve la respuesta como flujo de eventos del protocolo.

    Los fallos del proveedor no pueden viajar como código HTTP una vez abierto el
    flujo, así que se comunican como un evento `response.failed` seguido del
    terminador. Cerrar la conexión sin más dejaría al cliente esperando.
    """
    started = time.perf_counter()

    # Se resuelven antes de abrir el generador para no retener el DTO completo,
    # que puede pesar cientos de kilobytes, durante todo el flujo.
    items = payload.as_input_items()
    instrucciones = payload.instructions
    emisor = OpenResponsesStream()

    def generador():
        try:
            yield from emisor.run(
                use_case.execute_stream(items, caller_instructions=instrucciones)
            )
        except LLMEngineError as exc:
            codigo, mensaje = _traducir(exc)
            if isinstance(exc, LLMRateLimitError):
                # No hay cabecera que poner una vez abierto el flujo, así que la
                # espera sugerida viaja dentro del mensaje.
                mensaje = f"{mensaje} Reintenta en {exc.retry_after} segundos."
            yield from emisor.failed(mensaje, code=str(codigo))
        finally:
            logger.info(
                "turno completado (streaming)",
                extra={"latency_ms": round((time.perf_counter() - started) * 1000)},
            )

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Evita que un proxy intermedio acumule el flujo y anule el streaming.
            "X-Accel-Buffering": "no",
        },
    )


@router.api_route(
    "/.well-known/agent-card.json",
    # HEAD incluido a propósito: hay clientes que comprueban la existencia del
    # documento antes de descargarlo, y un 405 lo haría parecer inexistente.
    methods=["GET", "HEAD", "OPTIONS"],
    tags=["operación"],
)
async def agent_card(request: Request) -> JSONResponse:
    """Tarjeta de agente A2A para descubrimiento automático.

    Sin autenticación a propósito: un mecanismo de descubrimiento que exigiera
    credenciales no podría cumplir su función. No expone secretos, solo declara
    que el endpoint espera un token Bearer.

    Se sirve con CORS abierto, y solo esta ruta. Un documento de descubrimiento
    que un navegador no pueda leer no descubre nada, y su contenido es público
    por definición. `/responses` mantiene el CORS cerrado: ahí sí hay una
    credencial de por medio y la integración es servidor a servidor.
    """
    base = str(request.base_url).rstrip("/")
    return JSONResponse(
        content=build_agent_card(StaticProfileRepository().get(), base_url=base),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=60",
        },
    )


@router.post(
    "/responses",
    # El endpoint devuelve un objeto `Response` o un flujo SSE según `stream`, y
    # FastAPI no puede derivar un modelo de esa unión. La forma de la respuesta
    # síncrona la fija `ResponsesReply.from_text`, y la del flujo el módulo
    # `streaming`; ambas están cubiertas por pruebas.
    response_model=None,
    tags=["agente"],
    dependencies=[Depends(authorize)],
)
def create_response(
    payload: ResponsesRequest,
    use_case: AnswerProfileQuestion = Depends(get_use_case),
) -> ResponsesReply | StreamingResponse:
    """Responde un turno de conversación sobre el perfil profesional.

    El historial completo del hilo llega en `input`; el servicio no guarda estado
    entre peticiones.

    **Definido con `def`, no con `async def`, a propósito.** El caso de uso es
    síncrono de principio a fin y tarda segundos. FastAPI ejecuta los handlers
    `async` en el bucle de eventos, así que uno bloqueante detendría todas las
    demás peticiones de la instancia mientras dura el turno; los `def` van al
    threadpool y no bloquean a nadie.
    """
    if payload.stream:
        return _streaming_response(payload, use_case)

    started = time.perf_counter()
    try:
        result = use_case.execute(
            payload.as_input_items(),
            caller_instructions=payload.instructions,
        )
    except LLMEngineError as exc:
        codigo, mensaje = _traducir(exc)
        raise HTTPException(
            status_code=codigo,
            detail=mensaje,
            # La espera sugerida solo existe para el límite de cuota, y dársela al
            # cliente es lo que le permite reintentar con criterio.
            headers=(
                {"Retry-After": str(exc.retry_after)}
                if isinstance(exc, LLMRateLimitError)
                else None
            ),
        ) from None

    elapsed_ms = round((time.perf_counter() - started) * 1000)

    # Observabilidad sin acumular datos de terceros: se registran métricas del
    # turno, nunca el contenido de la conversación.
    logger.info(
        "turno completado",
        extra={
            "latency_ms": elapsed_ms,
            "iterations": result.iterations,
            "tools_invoked": list(result.tools_invoked),
            "exhausted": result.exhausted,
            "total_tokens": result.usage.get("total_tokens", 0),
            "model": result.model,
        },
    )

    return ResponsesReply.from_text(
        text=result.output_text,
        model=result.model,
        usage=result.usage,
        response_id=result.response_id or None,
    )
