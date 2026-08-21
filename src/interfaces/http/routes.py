"""Rutas HTTP: la entrega del caso de uso por el contrato Open Responses."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.application.conversation import AnswerProfileQuestion
from src.infrastructure.openai_engine import (
    LLMConfigurationError,
    LLMEngineError,
    LLMRateLimitError,
)
from src.interfaces.http.schemas import ResponsesReply, ResponsesRequest
from src.interfaces.http.security import authorize

logger = logging.getLogger(__name__)

router = APIRouter()


def get_use_case(request: Request) -> AnswerProfileQuestion:
    """Recupera el caso de uso construido en el composition root."""
    use_case = getattr(request.app.state, "answer_question", None)
    if use_case is None:  # pragma: no cover - solo si el wiring falla
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El agente no está disponible.",
        )
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


@router.post(
    "/responses",
    response_model=ResponsesReply,
    response_model_exclude_none=True,
    tags=["agente"],
    dependencies=[Depends(authorize)],
)
async def create_response(
    payload: ResponsesRequest,
    use_case: AnswerProfileQuestion = Depends(get_use_case),
) -> ResponsesReply:
    """Responde un turno de conversación sobre el perfil profesional.

    El historial completo del hilo llega en `input`; el servicio no guarda estado
    entre peticiones.
    """
    if payload.stream:
        # Se rechaza de forma explícita en lugar de responder sin streaming como
        # si nada: declarar una capacidad que no se implementa es peor que no
        # tenerla.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Este agente responde de forma síncrona; 'stream' no está soportado. "
                "Envía la petición con stream=false."
            ),
        )

    started = time.perf_counter()
    try:
        result = use_case.execute(
            payload.as_input_items(),
            caller_instructions=payload.instructions,
        )
    except LLMRateLimitError as exc:
        # Cuota del proveedor saturada. Es transitorio, así que se propaga como
        # 429 con la espera sugerida: quien integra el agente puede reintentar
        # con criterio en lugar de tratarlo como un servicio caído.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "El proveedor del modelo alcanzó su límite de uso. Reintenta en unos segundos."
            ),
            headers={"Retry-After": str(exc.retry_after)},
        ) from None
    except LLMConfigurationError:
        # Credencial o modelo mal configurados: el servicio no puede responder
        # hasta que se corrija. Se distingue de una caída pasajera.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El agente no está configurado correctamente.",
        ) from None
    except LLMEngineError:
        # El detalle ya quedó en los logs del adaptador; al cliente le llega un
        # error genérico para no filtrar interioridades del proveedor.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El modelo no está disponible en este momento. Intenta de nuevo.",
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
