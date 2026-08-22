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

El emisor es una clase y no una función generadora suelta por una razón concreta:
el contador de secuencia y los identificadores tienen que sobrevivir a todo el
turno, incluido un fallo a mitad. Con generadores independientes, el evento de
error reiniciaba la numeración y emitía un `sequence_number` ya usado.
"""

from __future__ import annotations

import itertools
import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from src.application.conversation import AnswerCompleted, AnswerDelta, ConversationEvent

#: Marca de fin de flujo que exige el protocolo.
DONE = "[DONE]"


def _text_part(text: str) -> dict[str, Any]:
    """Parte de contenido textual, la forma que más se repite en el protocolo."""
    return {"type": "output_text", "text": text, "annotations": []}


def _message_item(item_id: str, *, status: str, text: str | None = None) -> dict[str, Any]:
    """Ítem de mensaje del asistente, con o sin contenido."""
    return {
        "type": "message",
        "id": item_id,
        "role": "assistant",
        "status": status,
        "content": [] if text is None else [_text_part(text)],
    }


class OpenResponsesStream:
    """Emite un turno completo como eventos del protocolo.

    Posee el contador de secuencia y los identificadores durante toda la
    respuesta. Un cliente que correlacione por `id` vería aparecer un mensaje
    distinto al cerrar si el envoltorio final generase el suyo propio, así que el
    del ítem se reutiliza en todos los eventos.
    """

    def __init__(self, *, model: str = "") -> None:
        self._seq = itertools.count()
        self._response_id = f"resp_{uuid.uuid4().hex}"
        self._item_id = f"msg_{uuid.uuid4().hex}"
        self._model = model
        self._chunks: list[str] = []
        self._usage: dict[str, int] = {}

    # -- serialización --------------------------------------------------------

    def _event(self, tipo: str, **campos: Any) -> str:
        payload = {"type": tipo, "sequence_number": next(self._seq), **campos}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _envelope(self, *, status: str, text: str | None = None) -> dict[str, Any]:
        """Objeto `Response` embebido en los eventos de estado."""
        envelope: dict[str, Any] = {
            "id": self._response_id,
            "object": "response",
            "created_at": int(time.time()),
            "status": status,
            "model": self._model,
            "output": [],
        }
        if text is not None:
            envelope["output"] = [_message_item(self._item_id, status="completed", text=text)]
            envelope["output_text"] = text
        if self._usage:
            envelope["usage"] = self._usage
        return envelope

    #: Campos de posición que acompañan a los eventos de contenido.
    @property
    def _position(self) -> dict[str, Any]:
        return {"item_id": self._item_id, "output_index": 0, "content_index": 0}

    # -- emisión --------------------------------------------------------------

    def run(self, events: Iterator[ConversationEvent]) -> Iterator[str]:
        """Traduce los eventos del caso de uso a la secuencia del protocolo."""
        abierto = self._envelope(status="in_progress")
        yield self._event("response.created", response=abierto)
        yield self._event("response.in_progress", response=abierto)
        yield self._event(
            "response.output_item.added",
            output_index=0,
            item=_message_item(self._item_id, status="in_progress"),
        )
        yield self._event("response.content_part.added", **self._position, part=_text_part(""))

        for event in events:
            if isinstance(event, AnswerDelta):
                yield from self._delta(event.text)
            elif isinstance(event, AnswerCompleted):
                self._model = event.result.model or self._model
                self._usage = event.result.usage
                # Si el turno terminó sin texto, por ejemplo al agotar las vueltas
                # de herramientas, se emite el mensaje de cierre como un delta más
                # para que el cliente no reciba un flujo vacío.
                if not self._chunks and event.result.output_text:
                    yield from self._delta(event.result.output_text)

        texto = "".join(self._chunks)
        yield self._event("response.output_text.done", **self._position, text=texto)
        yield self._event(
            "response.content_part.done", **self._position, part=_text_part(texto)
        )
        yield self._event(
            "response.output_item.done",
            output_index=0,
            item=_message_item(self._item_id, status="completed", text=texto),
        )
        yield self._event(
            "response.completed", response=self._envelope(status="completed", text=texto)
        )
        yield self.done()

    def _delta(self, text: str) -> Iterator[str]:
        self._chunks.append(text)
        yield self._event("response.output_text.delta", **self._position, delta=text)

    def failed(self, message: str, *, code: str) -> Iterator[str]:
        """Comunica un fallo dentro del flujo y lo cierra según el protocolo.

        Una vez abierta la respuesta ya no se puede cambiar el código HTTP, así
        que el protocolo lo transmite como evento. La numeración continúa donde
        iba: reiniciarla emitiría un `sequence_number` que el cliente ya recibió.
        """
        yield self._event(
            "response.failed",
            response=self._envelope(status="failed"),
            error={"message": message, "type": "api_error", "code": code},
        )
        yield self.done()

    @staticmethod
    def done() -> str:
        return f"data: {DONE}\n\n"
