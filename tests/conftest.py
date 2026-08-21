"""Dobles de prueba y fixtures compartidas.

Toda la suite corre sin red y sin claves: los puertos se sustituyen por dobles.
Eso es lo que hace las pruebas rápidas, deterministas y gratuitas, y es la razón
concreta por la que la arquitectura define puertos en lugar de importar el SDK
del proveedor desde el caso de uso.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.application.ports import EngineResponse, ToolCall
from src.application.tool_registry import ToolRegistry
from src.domain.profile import Profile
from src.infrastructure.lexical_search import LexicalProfileSearch
from src.infrastructure.profile_data import StaticProfileRepository


class FakeEngine:
    """Motor de lenguaje programable.

    Devuelve las respuestas que se le den, en orden, y registra con qué se le
    llamó para poder afirmar sobre el ciclo de herramientas.
    """

    def __init__(self, responses: list[EngineResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def respond(
        self,
        *,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> EngineResponse:
        self.calls.append(
            {
                "instructions": instructions,
                "input_items": list(input_items),
                "tools": tools,
            }
        )
        if not self._responses:
            raise AssertionError("FakeEngine se quedó sin respuestas programadas.")
        return self._responses.pop(0)


def text_response(text: str, *, response_id: str = "resp_test") -> EngineResponse:
    """Respuesta final, sin herramientas."""
    return EngineResponse(
        response_id=response_id,
        output_text=text,
        output_items=[
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        model="fake-model",
    )


def tool_response(
    name: str,
    arguments: dict[str, Any] | None = None,
    *,
    call_id: str = "call_1",
) -> EngineResponse:
    """Respuesta que pide ejecutar una herramienta."""
    raw = json.dumps(arguments or {})
    return EngineResponse(
        response_id="resp_tool",
        output_text="",
        output_items=[
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": raw,
            }
        ],
        tool_calls=[ToolCall(call_id=call_id, name=name, arguments=raw)],
        usage={"input_tokens": 8, "output_tokens": 3, "total_tokens": 11},
        model="fake-model",
    )


def user_message(text: str) -> dict[str, Any]:
    return {"role": "user", "content": [{"type": "input_text", "text": text}]}


@pytest.fixture
def profile_repository() -> StaticProfileRepository:
    return StaticProfileRepository()


@pytest.fixture
def profile(profile_repository: StaticProfileRepository) -> Profile:
    return profile_repository.get()


@pytest.fixture
def search(profile: Profile) -> LexicalProfileSearch:
    return LexicalProfileSearch(profile)


@pytest.fixture
def tools(
    profile_repository: StaticProfileRepository, search: LexicalProfileSearch
) -> ToolRegistry:
    return ToolRegistry(profile_repository, search)
