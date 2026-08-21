"""Adaptador del puerto `LLMEngine` sobre la Responses API de OpenAI.

Es el único archivo del proyecto que sabe que el proveedor es OpenAI. Cambiarlo
por otro motor no toca el dominio ni el caso de uso: es la misma tesis que
sostiene a Open Responses, aplicada al código propio.

Decisión de privacidad: **`store=False` en cada llamada**. La Responses API
persiste las conversaciones del lado del proveedor por defecto, y esa persistencia
es la que habilita `previous_response_id`. Aquí el hilo se reconstruye enviando los
ítems en cada petición, de modo que la continuidad se conserva sin dejar
conversaciones almacenadas fuera del proceso.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from src.application.ports import EngineResponse, ToolCall

logger = logging.getLogger(__name__)


class LLMEngineError(RuntimeError):
    """Fallo al hablar con el proveedor del modelo.

    Se traduce a un error genérico en la respuesta HTTP: el detalle se queda en
    los logs del servidor, no viaja al cliente.
    """


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

    def __init__(self, *, api_key: str, model: str, timeout: float = 60.0) -> None:
        if not api_key:
            raise ValueError("Falta OPENAI_API_KEY: el motor no puede inicializarse.")
        self._client = OpenAI(api_key=api_key, timeout=timeout)
        self._model = model

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
            )
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
