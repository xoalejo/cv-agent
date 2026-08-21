"""Caso de uso: responder una pregunta sobre el perfil.

Orquesta el ciclo completo de un turno (instrucciones, llamada al motor,
ejecución de herramientas, reinyección de resultados- sin conocer el proveedor ni
el transporte HTTP. Eso es lo que permite probarlo entero sin red.

Sobre la memoria del hilo: este caso de uso es **stateless por diseño**. La
continuidad la aporta `input_items`, que llega con el historial completo en cada
petición. No se guarda nada entre llamadas ni se pide al proveedor que lo guarde,
de modo que no hay conversaciones en reposo en ningún lado.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from src.application.ports import (
    EngineResponse,
    LLMEngine,
    ProfileRepository,
    TextDelta,
    TurnFinished,
)
from src.application.prompt import build_instructions
from src.application.tool_registry import ToolRegistry
from src.domain.policies import redact_contact_data
from src.domain.profile import Language
from src.domain.streaming_guard import StreamingDisclosureGuard

#: Tope de vueltas al modelo dentro de un mismo turno. Sin él, un modelo que
#: insista en llamar herramientas podría encadenar peticiones indefinidamente:
#: es un control de costo y de disponibilidad, no un detalle de implementación.
DEFAULT_MAX_TOOL_ITERATIONS = 5

_EXHAUSTED_MESSAGE = {
    "es": (
        "Me enredé consultando el CV y no logré cerrar la respuesta. "
        "¿Podrías reformular la pregunta?"
    ),
    "en": (
        "I got tangled up looking through the CV and couldn't finish the answer. "
        "Could you rephrase the question?"
    ),
}

# Marcadores frecuentes de cada idioma. Solo se usan para elegir el idioma de los
# mensajes del sistema y del marcador de redacción; el modelo detecta el idioma de
# la conversación por su cuenta.
_ES_MARKERS = re.compile(
    r"\b(el|la|los|las|un|una|de|del|al|en|y|que|qué|por|para|con|sin|sobre|"
    r"su|sus|se|es|son|fue|ha|han|tiene|tienen|más|como|cómo|pero|cuando|"
    r"cuándo|donde|dónde|quien|quién|cual|cuál|entre|desde|hasta|también|"
    r"experiencia|trabajo|trabajó|proyectos|habilidades|años|empresa|puedes|"
    r"háblame|cuéntame|aparece|cuenta)\b",
    re.IGNORECASE,
)
_EN_MARKERS = re.compile(
    r"\b(the|of|and|to|in|is|are|was|were|has|have|had|he|his|him|it|its|"
    r"for|with|that|this|these|those|on|at|as|by|from|an|a|does|did|do|can|"
    r"could|will|would|not|but|or|so|than|then|there|they|their|you|your|"
    r"about|into|over|under|before|after|while|yes|no|what|which|how|where|"
    r"when|who|experience|work|projects|skills|years|company|tell)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnswerDelta:
    """Fragmento de respuesta ya filtrado por la política de divulgación."""

    text: str


@dataclass(frozen=True)
class AnswerCompleted:
    """Fin de la conversación, con el resultado completo del turno."""

    result: ConversationResult


#: Lo que el caso de uso emite al responder en streaming.
ConversationEvent = AnswerDelta | AnswerCompleted


@dataclass(frozen=True)
class ConversationResult:
    """Lo que el turno produjo, listo para traducirse al DTO de salida."""

    response_id: str
    output_text: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    tools_invoked: tuple[str, ...] = ()
    iterations: int = 1
    exhausted: bool = False


def extract_last_user_text(input_items: list[dict[str, Any]]) -> str:
    """Recupera el texto del último mensaje del usuario.

    Acepta las dos formas que admite el protocolo: contenido como cadena suelta o
    como lista de partes tipadas.
    """
    for item in reversed(input_items):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            ]
            if parts:
                return " ".join(parts)
    return ""


#: Palabras que se examinan para decidir el idioma.
#:
#: Se mira solo el arranque porque ahí está la voz narrativa. Una respuesta en
#: inglés puede citar después títulos de patente registrados en español, y
#: contar el texto completo inclinaría la detección hacia el idioma de las citas
#: en lugar del idioma en que se está respondiendo. Doce palabras cubren la
#: oración de apertura, que es anterior a cualquier cita.
_LANGUAGE_SAMPLE_WORDS = 12


def detect_language(text: str) -> Language:
    """Heurística mínima ES/EN sobre el arranque del texto. Ante la duda, español."""
    if not text.strip():
        return "es"
    muestra = " ".join(text.split()[:_LANGUAGE_SAMPLE_WORDS])
    spanish = len(_ES_MARKERS.findall(muestra))
    english = len(_EN_MARKERS.findall(muestra))
    return "en" if english > spanish else "es"


class AnswerProfileQuestion:
    """Responde una pregunta sobre el perfil, usando herramientas si hacen falta."""

    def __init__(
        self,
        *,
        engine: LLMEngine,
        profile_repository: ProfileRepository,
        tools: ToolRegistry,
        max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        self._engine = engine
        self._profiles = profile_repository
        self._tools = tools
        self._max_iterations = max(1, max_tool_iterations)

    def execute(
        self,
        input_items: list[dict[str, Any]],
        *,
        caller_instructions: str | None = None,
    ) -> ConversationResult:
        instructions = build_instructions(
            self._profiles.get(), caller_instructions=caller_instructions
        )
        language = detect_language(extract_last_user_text(input_items))

        items: list[dict[str, Any]] = list(input_items)
        tools_invoked: list[str] = []
        last_response: EngineResponse | None = None

        for iteration in range(1, self._max_iterations + 1):
            last_response = self._engine.respond(
                instructions=instructions,
                input_items=items,
                tools=self._tools.definitions,
            )

            if not last_response.requires_tools:
                return self._finish(
                    last_response,
                    language=language,
                    tools_invoked=tools_invoked,
                    iterations=iteration,
                )

            # Los ítems del modelo vuelven al input para que el siguiente turno
            # conserve el hilo de razonamiento que llevó a pedir la herramienta.
            items.extend(last_response.output_items)

            for call in last_response.tool_calls:
                tools_invoked.append(call.name)
                result = self._tools.execute(call.name, call.arguments)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

        # Se agotaron las vueltas: se responde algo útil en vez de fallar.
        return ConversationResult(
            response_id=last_response.response_id if last_response else "",
            output_text=_EXHAUSTED_MESSAGE[language],
            model=last_response.model if last_response else "",
            usage=last_response.usage if last_response else {},
            tools_invoked=tuple(tools_invoked),
            iterations=self._max_iterations,
            exhausted=True,
        )

    def execute_stream(
        self,
        input_items: list[dict[str, Any]],
        *,
        caller_instructions: str | None = None,
    ) -> Iterator[ConversationEvent]:
        """Igual que `execute`, emitiendo la respuesta conforme se genera.

        El ciclo de herramientas es el mismo: lo que cambia es que el texto del
        turno final sale por partes en lugar de esperar a estar completo.

        Cada fragmento pasa por `StreamingDisclosureGuard` antes de salir. Sin
        ese filtro el streaming sería un agujero en la política de divulgación:
        el guarda de la respuesta completa revisa un texto que aquí nunca existe
        de una pieza, y lo ya emitido no se puede retirar.
        """
        instructions = build_instructions(
            self._profiles.get(), caller_instructions=caller_instructions
        )
        language = detect_language(extract_last_user_text(input_items))

        items: list[dict[str, Any]] = list(input_items)
        tools_invoked: list[str] = []
        guard = StreamingDisclosureGuard(language)
        last: EngineResponse | None = None

        for iteration in range(1, self._max_iterations + 1):
            last = None
            for event in self._engine.respond_stream(
                instructions=instructions,
                input_items=items,
                tools=self._tools.definitions,
            ):
                if isinstance(event, TextDelta):
                    if seguro := guard.feed(event.text):
                        yield AnswerDelta(seguro)
                elif isinstance(event, TurnFinished):
                    last = event.response

            if last is None:
                break

            if not last.requires_tools:
                if resto := guard.flush():
                    yield AnswerDelta(resto)
                yield AnswerCompleted(
                    self._finish(
                        last,
                        language=language,
                        tools_invoked=tools_invoked,
                        iterations=iteration,
                    )
                )
                return

            items.extend(last.output_items)
            for call in last.tool_calls:
                tools_invoked.append(call.name)
                result = self._tools.execute(call.name, call.arguments)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

        # Se agotaron las vueltas sin respuesta final.
        if resto := guard.flush():
            yield AnswerDelta(resto)
        yield AnswerCompleted(
            ConversationResult(
                response_id=last.response_id if last else "",
                output_text=_EXHAUSTED_MESSAGE[language],
                model=last.model if last else "",
                usage=last.usage if last else {},
                tools_invoked=tuple(tools_invoked),
                iterations=self._max_iterations,
                exhausted=True,
            )
        )

    def _finish(
        self,
        response: EngineResponse,
        *,
        language: Language,
        tools_invoked: list[str],
        iterations: int,
    ) -> ConversationResult:
        # Última capa de la política de divulgación: si algo con forma de teléfono
        # llegó a la respuesta, por ejemplo porque quien pregunta lo pegó en el
        # chat y pidió confirmarlo-, no sale de aquí.
        safe_text = redact_contact_data(response.output_text, language)
        return ConversationResult(
            response_id=response.response_id,
            output_text=safe_text,
            model=response.model,
            usage=response.usage,
            tools_invoked=tuple(tools_invoked),
            iterations=iterations,
        )
