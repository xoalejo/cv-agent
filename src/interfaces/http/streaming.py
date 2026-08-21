"""Serialización de la respuesta como eventos SSE de Open Responses.

El spec exige tres cosas que aquí se cumplen de forma literal:

* `Content-Type: text/event-stream`.
* Cada `data:` es un objeto JSON.
* El evento terminal es la cadena literal `[DONE]`.

Los eventos siguen la máquina de estados del protocolo, con `sequence_number`
correlativo: creación, progreso, alta del ítem y de la parte de contenido, los
deltas de texto, y el cierre de cada nivel antes de completar la respuesta. No se
emite un flujo de texto suelto, porque un cliente que siga el spec espera esta
secuencia y no otra.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from src.application.conversation import AnswerCompleted, AnswerDelta, ConversationEvent

#: Marca de fin de flujo que exige el protocolo.
DONE = "[DONE]"


class _Sequence:
    """Contador correlativo para `sequence_number`."""

    def __init__(self) -> None:
        self._value = -1

    def next(self) -> int:
        self._value += 1
        return self._value


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _response_envelope(
    *,
    response_id: str,
    model: str,
    status: str,
    text: str | None = None,
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Objeto `Response` embebido en los eventos de estado."""
    envelope: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": status,
        "model": model,
        "output": [],
    }
    if text is not None:
        envelope["output"] = [
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex}",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ]
        envelope["output_text"] = text
    if usage is not None:
        envelope["usage"] = usage
    return envelope


def stream_open_responses(
    events: Iterator[ConversationEvent],
    *,
    fallback_model: str,
) -> Iterator[str]:
    """Traduce los eventos del caso de uso a la secuencia SSE del protocolo.

    El identificador de respuesta se genera aquí y se mantiene durante todo el
    flujo: los eventos iniciales se emiten antes de que el proveedor haya
    devuelto el suyo, y cambiarlo a mitad rompería a un cliente que correlacione
    por `id`.
    """
    seq = _Sequence()
    response_id = f"resp_{uuid.uuid4().hex}"
    item_id = f"msg_{uuid.uuid4().hex}"
    acumulado: list[str] = []

    yield _sse(
        {
            "type": "response.created",
            "sequence_number": seq.next(),
            "response": _response_envelope(
                response_id=response_id, model=fallback_model, status="in_progress"
            ),
        }
    )
    yield _sse(
        {
            "type": "response.in_progress",
            "sequence_number": seq.next(),
            "response": _response_envelope(
                response_id=response_id, model=fallback_model, status="in_progress"
            ),
        }
    )
    yield _sse(
        {
            "type": "response.output_item.added",
            "sequence_number": seq.next(),
            "output_index": 0,
            "item": {
                "type": "message",
                "id": item_id,
                "role": "assistant",
                "status": "in_progress",
                "content": [],
            },
        }
    )
    yield _sse(
        {
            "type": "response.content_part.added",
            "sequence_number": seq.next(),
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []},
        }
    )

    modelo = fallback_model
    usage: dict[str, int] = {}

    for event in events:
        if isinstance(event, AnswerDelta):
            acumulado.append(event.text)
            yield _sse(
                {
                    "type": "response.output_text.delta",
                    "sequence_number": seq.next(),
                    "item_id": item_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": event.text,
                }
            )
        elif isinstance(event, AnswerCompleted):
            modelo = event.result.model or fallback_model
            usage = event.result.usage
            # Si el turno terminó sin texto (por ejemplo al agotar las vueltas de
            # herramientas), se emite el mensaje de cierre como un delta más para
            # que el cliente no reciba un flujo vacío.
            if not acumulado and event.result.output_text:
                acumulado.append(event.result.output_text)
                yield _sse(
                    {
                        "type": "response.output_text.delta",
                        "sequence_number": seq.next(),
                        "item_id": item_id,
                        "output_index": 0,
                        "content_index": 0,
                        "delta": event.result.output_text,
                    }
                )

    texto = "".join(acumulado)

    yield _sse(
        {
            "type": "response.output_text.done",
            "sequence_number": seq.next(),
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "text": texto,
        }
    )
    yield _sse(
        {
            "type": "response.content_part.done",
            "sequence_number": seq.next(),
            "item_id": item_id,
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": texto, "annotations": []},
        }
    )
    yield _sse(
        {
            "type": "response.output_item.done",
            "sequence_number": seq.next(),
            "output_index": 0,
            "item": {
                "type": "message",
                "id": item_id,
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": texto, "annotations": []}],
            },
        }
    )
    yield _sse(
        {
            "type": "response.completed",
            "sequence_number": seq.next(),
            "response": _response_envelope(
                response_id=response_id,
                model=modelo,
                status="completed",
                text=texto,
                usage=usage,
            ),
        }
    )
    yield f"data: {DONE}\n\n"


def stream_error(message: str, *, code: str) -> Iterator[str]:
    """Emite un error dentro del flujo y lo cierra según el protocolo.

    Cuando el fallo ocurre con la respuesta ya iniciada no se puede cambiar el
    código HTTP, así que el protocolo lo comunica como evento.
    """
    yield _sse(
        {
            "type": "response.failed",
            "sequence_number": 0,
            "error": {"message": message, "type": "api_error", "code": code},
        }
    )
    yield f"data: {DONE}\n\n"
