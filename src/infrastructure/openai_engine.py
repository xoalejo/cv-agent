"""Adaptador del puerto `LLMEngine` sobre la Responses API de OpenAI.

Es el único archivo del proyecto que sabe que el proveedor es OpenAI. Cambiarlo
por otro motor no toca el dominio ni el caso de uso: es la misma tesis que
sostiene a Open Responses, aplicada al código propio.

Decisión de privacidad: **`store=False` en cada llamada**. La Responses API
persiste las conversaciones del lado del proveedor por defecto, y esa persistencia
es la que habilita `previous_response_id`. Aquí el hilo se reconstruye enviando los
ítems en cada petición, de modo que la continuidad se conserva sin dejar
conversaciones almacenadas fuera del proceso.

Sobre los límites del proveedor: OpenAI aplica cuotas por minuto de peticiones
(RPM) y de tokens (TPM). Como cada turno envía el perfil completo (del orden de
4-5k tokens de entrada), **el límite que se alcanza primero es el de tokens, no
el de peticiones**. Un 429 del proveedor es transitorio y debe distinguirse de un
fallo real: se traduce en `LLMRateLimitError` para que la capa HTTP responda 429
con `Retry-After` en lugar de presentar un límite pasajero como avería.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)

from src.application.ports import EngineResponse, ToolCall

logger = logging.getLogger(__name__)

#: Reintentos automáticos del SDK ante 429 y errores de conexión, con espera
#: exponencial. Absorbe los picos breves sin que el cliente se entere; los
#: sostenidos sí escalan como 429 hacia arriba.
DEFAULT_MAX_RETRIES = 3


class LLMEngineError(RuntimeError):
    """Fallo al hablar con el proveedor del modelo.

    Se traduce a un error genérico en la respuesta HTTP: el detalle se queda en
    los logs del servidor, no viaja al cliente.
    """


class LLMRateLimitError(LLMEngineError):
    """El proveedor rechazó por cuota (RPM o TPM).

    Es transitorio: reintentar más tarde tiene sentido, y por eso viaja al
    cliente como 429 con `Retry-After` y no como un 502.
    """

    def __init__(self, message: str, *, retry_after: int = 20) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMConfigurationError(LLMEngineError):
    """Credencial inválida o modelo inexistente.

    Reintentar no lo arregla: requiere corregir la configuración del servicio.
    Se separa para que no se confunda con una indisponibilidad pasajera.
    """


def _retry_after_seconds(exc: Exception, *, default: int = 20) -> int:
    """Extrae `Retry-After` de la respuesta del proveedor si viene.

    Reenviar la espera que indica OpenAI es mejor que inventar una: quien nos
    llama reintenta cuando de verdad tiene sentido.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return default
    raw = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return max(1, int(float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_dict(item: Any) -> dict[str, Any]:
    """Normaliza un ítem del SDK a diccionario reenviable como input."""
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dump(exclude_none=True)
    return dict(item)


class OpenAIResponsesEngine:
    """Motor de lenguaje sobre `client.responses.create`."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        reasoning_effort: str = "low",
    ) -> None:
        if not api_key:
            raise ValueError("Falta OPENAI_API_KEY: el motor no puede inicializarse.")
        # El SDK reintenta por su cuenta ante 429 y errores de conexión, con
        # espera exponencial. Se fija explícitamente en lugar de heredar el valor
        # por defecto: es una decisión de disponibilidad, no un detalle oculto.
        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self._model = model
        self._reasoning_effort = reasoning_effort

    @property
    def model(self) -> str:
        return self._model

    def respond(
        self,
        *,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> EngineResponse:
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=instructions,
                input=input_items,
                tools=tools,
                store=False,
                reasoning={"effort": self._reasoning_effort},
            )
        except RateLimitError as exc:
            # Llega aquí solo si los reintentos del SDK ya se agotaron: la cuota
            # está saturada de verdad, no es un pico puntual.
            retry_after = _retry_after_seconds(exc)
            logger.warning(
                "Cuota del proveedor agotada; se responderá 429 (retry_after=%ss)",
                retry_after,
            )
            raise LLMRateLimitError(str(exc), retry_after=retry_after) from exc
        except (AuthenticationError, NotFoundError) as exc:
            # Credencial inválida o modelo inexistente: reintentar no lo arregla.
            logger.error("Configuración del proveedor inválida: %s", exc)
            raise LLMConfigurationError(str(exc)) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            logger.warning("Problema de red con el proveedor: %s", exc)
            raise LLMEngineError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - se re-lanza acotado
            logger.exception("Fallo al invocar la Responses API")
            raise LLMEngineError(str(exc)) from exc

        output_items = [_as_dict(item) for item in (response.output or [])]

        tool_calls = [
            ToolCall(
                call_id=item.get("call_id") or item.get("id", ""),
                name=item.get("name", ""),
                arguments=item.get("arguments", "") or "",
            )
            for item in output_items
            if item.get("type") == "function_call"
        ]

        usage: dict[str, int] = {}
        if response.usage is not None:
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(response.usage, "output_tokens", 0) or 0,
                "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
            }

        return EngineResponse(
            response_id=response.id,
            output_text=(response.output_text or "").strip(),
            output_items=output_items,
            tool_calls=tool_calls,
            usage=usage,
            model=getattr(response, "model", self._model),
        )
