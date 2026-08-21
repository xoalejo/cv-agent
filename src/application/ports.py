"""Puertos: los contratos que la capa de aplicación necesita del exterior.

Definirlos aquí —y no importar adaptadores concretos— es lo que invierte la
dependencia: la infraestructura se adapta a la aplicación, no al revés.

El beneficio no es teórico. `LLMEngine` deja el proveedor sustituible, que es la
misma tesis que sostiene a Open Responses: desacoplar el agente del proveedor. Y
con los puertos en dobles de prueba, el caso de uso se prueba sin red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.domain.fragment import ProfileFragment
from src.domain.profile import Profile


@dataclass(frozen=True)
class ToolCall:
    """Petición del modelo para ejecutar una herramienta."""

    call_id: str
    name: str
    #: Argumentos tal como los emite el modelo: JSON sin parsear. El registro de
    #: herramientas es quien valida, porque es quien conoce cada firma.
    arguments: str


@dataclass(frozen=True)
class EngineResponse:
    """Resultado de un turno del modelo.

    `output_items` son los ítems que deben reinyectarse en el `input` de la
    siguiente llamada para conservar el hilo del razonamiento. Se tratan como
    opacos: son el vocabulario del protocolo (Open Responses), no un detalle de
    un proveedor concreto.
    """

    response_id: str
    output_text: str
    output_items: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""

    @property
    def requires_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMEngine(Protocol):
    """Motor de lenguaje capaz de razonar con herramientas."""

    def respond(
        self,
        *,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> EngineResponse:
        """Ejecuta un turno.

        No debe persistir la conversación del lado del proveedor: la continuidad
        del hilo la aporta `input_items` en cada llamada.
        """
        ...


class ProfileRepository(Protocol):
    """Acceso al perfil profesional."""

    def get(self) -> Profile: ...


class ProfileSearch(Protocol):
    """Búsqueda sobre el perfil que devuelve fragmentos con procedencia."""

    def search(self, query: str, *, limit: int = 5) -> list[ProfileFragment]:
        """Busca en el perfil y devuelve fragmentos con su procedencia.

        El corpus está en español; el prompt instruye al modelo a consultar en ese
        idioma aunque la conversación transcurra en otro.
        """
        ...
