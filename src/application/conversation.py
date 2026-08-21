"""Caso de uso: responder una pregunta sobre el perfil.

Orquesta el ciclo completo de un turno —instrucciones, llamada al motor,
ejecución de herramientas, reinyección de resultados— sin conocer el proveedor ni
el transporte HTTP. Eso es lo que permite probarlo entero sin red.

Sobre la memoria del hilo: este caso de uso es **stateless por diseño**. La
continuidad la aporta `input_items`, que llega con el historial completo en cada
petición. No se guarda nada entre llamadas ni se pide al proveedor que lo guarde,
de modo que no hay conversaciones en reposo en ningún lado.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.application.ports import EngineResponse, LLMEngine, ProfileRepository
from src.application.prompt import build_instructions
from src.application.tool_registry import ToolRegistry
from src.domain.policies import redact_contact_data
from src.domain.profile import Language

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
    r"\b(qué|que|cuál|cual|cómo|como|dónde|donde|cuándo|cuando|quién|quien|"
    r"experiencia|trabajo|proyectos|habilidades|años|empresa|puedes|tiene|háblame|"
    r"cuéntame|para|con|del|los|las|una|por)\b",
    re.IGNORECASE,
)
_EN_MARKERS = re.compile(
    r"\b(what|which|how|where|when|who|experience|work|projects|skills|years|"
    r"company|can|does|tell|about|with|the|his|your)\b",
    re.IGNORECASE,
)


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


def detect_language(text: str) -> Language:
    """Heurística mínima ES/EN. Ante la duda, español."""
    if not text.strip():
        return "es"
    spanish = len(_ES_MARKERS.findall(text))
    english = len(_EN_MARKERS.findall(text))
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

    def _finish(
        self,
        response: EngineResponse,
        *,
        language: Language,
        tools_invoked: list[str],
        iterations: int,
    ) -> ConversationResult:
        # Última capa de la política de divulgación: si algo con forma de teléfono
        # llegó a la respuesta —por ejemplo porque quien pregunta lo pegó en el
        # chat y pidió confirmarlo—, no sale de aquí.
        safe_text = redact_contact_data(response.output_text, language)
        return ConversationResult(
            response_id=response.response_id,
            output_text=safe_text,
            model=response.model,
            usage=response.usage,
            tools_invoked=tuple(tools_invoked),
            iterations=iterations,
        )
