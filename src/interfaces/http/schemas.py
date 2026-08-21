"""DTOs del contrato Open Responses.

El request es **permisivo con campos desconocidos** a propósito: la plataforma
que registra el agente permite adjuntar parámetros extra por petición
(`temperature`, `reasoning`, etc.). Un parser estricto rechazaría peticiones
válidas por traer un campo que no usamos; se ignoran sin romper.

Lo que sí se valida con rigor es lo propio: la forma de `input` y los límites de
tamaño, que son la puerta de entrada al servicio.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Cota defensiva sobre el historial que acepta un turno. La plataforma reenvía
#: la transcripción completa en cada llamada, así que sin un tope el tamaño del
#: contexto —y su costo— crece con la conversación sin límite.
MAX_INPUT_ITEMS = 200
MAX_TEXT_LENGTH = 32_000


class ResponsesRequest(BaseModel):
    """Petición entrante a `POST /responses`."""

    model_config = ConfigDict(extra="allow")

    #: Se acepta pero se ignora: el modelo lo decide el servidor. Ver `config.py`.
    model: str | None = None

    input: str | list[dict[str, Any]]

    #: Instrucciones opcionales del cliente. Se integran subordinadas al prompt
    #: propio, nunca lo sustituyen. Ver `application.prompt`.
    instructions: str | None = None

    stream: bool = False

    @field_validator("input")
    @classmethod
    def _validate_input(
        cls, value: str | list[dict[str, Any]]
    ) -> str | list[dict[str, Any]]:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("El campo 'input' no puede estar vacío.")
            if len(value) > MAX_TEXT_LENGTH:
                raise ValueError("El campo 'input' excede el tamaño máximo.")
            return value

        if not value:
            raise ValueError("El campo 'input' no puede ser una lista vacía.")
        if len(value) > MAX_INPUT_ITEMS:
            raise ValueError(
                f"El historial excede el máximo de {MAX_INPUT_ITEMS} elementos."
            )
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("Cada elemento de 'input' debe ser un objeto.")
        return value

    def as_input_items(self) -> list[dict[str, Any]]:
        """Normaliza `input` a la forma de lista de ítems del protocolo."""
        if isinstance(self.input, str):
            return [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": self.input}],
                }
            ]
        return list(self.input)


class OutputTextContent(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str
    annotations: list[dict[str, Any]] = Field(default_factory=list)


class OutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str
    role: Literal["assistant"] = "assistant"
    status: Literal["completed"] = "completed"
    content: list[OutputTextContent]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ResponsesReply(BaseModel):
    """Objeto `Response` que devuelve el endpoint.

    Solo contiene el mensaje final del asistente. Las llamadas a herramientas se
    resuelven dentro del servicio, así que no viajan al cliente: quien integra el
    agente no tiene que ejecutar nada por su cuenta.
    """

    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed"] = "completed"
    model: str
    output: list[OutputMessage]
    output_text: str
    usage: Usage

    @classmethod
    def from_text(
        cls,
        *,
        text: str,
        model: str,
        usage: dict[str, int] | None = None,
        response_id: str | None = None,
    ) -> ResponsesReply:
        return cls(
            id=response_id or f"resp_{uuid.uuid4().hex}",
            created_at=int(time.time()),
            model=model,
            output=[
                OutputMessage(
                    id=f"msg_{uuid.uuid4().hex}",
                    content=[OutputTextContent(text=text)],
                )
            ],
            output_text=text,
            usage=Usage(**(usage or {})),
        )


class ErrorDetail(BaseModel):
    message: str
    type: str
    code: str | None = None


class ErrorReply(BaseModel):
    """Error con la forma que espera un cliente del protocolo."""

    error: ErrorDetail
