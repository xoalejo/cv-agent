"""Definición y despacho de las herramientas del agente.

El registro conoce las firmas y valida los argumentos; el caso de uso solo sabe
que hay herramientas que ejecutar. Todas leen del perfil a través de puertos, así
que ninguna toca la red ni servicios externos: **ningún dato no confiable entra
al contexto del modelo**, lo que elimina de raíz la inyección vía salida de
herramienta en lugar de tener que mitigarla.

Un error de una herramienta se devuelve como dato (`{"error": ...}`), no como
excepción: el modelo puede corregir el argumento y reintentar, que es un
comportamiento mejor que abortar la conversación.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.application.ports import ProfileRepository, ProfileSearch
from src.domain.policies import allowed_contact_channels
from src.domain.profile import Profile

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_profile",
        "description": (
            "Busca en todo el CV y devuelve los fragmentos más relevantes junto con su "
            "procedencia (sección y empresa o proyecto). Úsala para preguntas que cruzan "
            "varias secciones: dónde ha usado una tecnología, qué experiencia tiene en un "
            "sector, o qué respalda una habilidad concreta. Úsala también cuando quieras "
            "citar de dónde sale un dato. **Formula la consulta siempre en español**, "
            "aunque converses en otro idioma: el CV está redactado en español."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Términos a buscar, por ejemplo 'RAG', 'trazabilidad industrial' "
                        "o 'sector financiero'."
                    ),
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_experience",
        "description": (
            "Devuelve la experiencia profesional con sus logros. Sin argumentos devuelve "
            "las tres posiciones; con 'company' devuelve solo esa empresa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": (
                        "Nombre parcial de la empresa: 'ABBA', 'Remote Data' o 'Arbomex'."
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_projects",
        "description": (
            "Devuelve los proyectos propios, con su descripción completa. Sin argumentos "
            "los devuelve todos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre parcial del proyecto.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_certifications",
        "description": (
            "Devuelve las certificaciones y formación continua, con emisor y año."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_tech_stack",
        "description": (
            "Devuelve el stack técnico agrupado por categoría (IA & Agentes, Cloud & "
            "DevOps, Data & Analytics, AppSec, etc.). Con 'category' devuelve solo esa."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Nombre parcial de la categoría, por ejemplo 'cloud'.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_contact_info",
        "description": (
            "Devuelve los canales de contacto que pueden compartirse. Es la única fuente "
            "válida de datos de contacto; no existe ningún otro canal disponible."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


class ToolRegistry:
    """Ejecuta las herramientas del agente contra el perfil."""

    def __init__(self, profile_repository: ProfileRepository, search: ProfileSearch) -> None:
        self._profiles = profile_repository
        self._search = search
        self._handlers: dict[str, Callable[[Profile, dict[str, Any]], Any]] = {
            "search_profile": self._search_profile,
            "get_experience": self._get_experience,
            "get_projects": self._get_projects,
            "get_certifications": self._get_certifications,
            "get_tech_stack": self._get_tech_stack,
            "get_contact_info": self._get_contact_info,
        }
        # Dos listas que deben coincidir: las definiciones que ve el modelo y los
        # handlers que las ejecutan. Si divergen, el síntoma en producción sería
        # un error de herramienta inexistente a mitad de una conversación; aquí
        # falla al arrancar, que es donde se nota.
        declaradas = {definition["name"] for definition in TOOL_DEFINITIONS}
        if declaradas != self._handlers.keys():
            raise ValueError(
                f"Definiciones y handlers no coinciden: {declaradas ^ self._handlers.keys()}"
            )

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return TOOL_DEFINITIONS

    def execute(self, name: str, raw_arguments: str) -> dict[str, Any]:
        """Ejecuta una herramienta y devuelve siempre un objeto serializable."""
        handler = self._handlers.get(name)
        if handler is None:
            return {"error": f"La herramienta '{name}' no existe."}

        try:
            arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
        except json.JSONDecodeError:
            return {"error": "Los argumentos no son JSON válido."}

        if not isinstance(arguments, dict):
            return {"error": "Los argumentos deben ser un objeto JSON."}

        try:
            return {"result": handler(self._profiles.get(), arguments)}
        except Exception as exc:  # noqa: BLE001 - la herramienta no debe tumbar el turno
            return {"error": f"La herramienta falló: {type(exc).__name__}: {exc}"}

    # -- handlers -------------------------------------------------------------

    def _search_profile(self, _: Profile, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"matches": [], "note": "La consulta venía vacía."}

        fragments = self._search.search(query, limit=5)
        return {
            "query": query,
            "matches": [
                {"text": fragment.text, "source": fragment.citation} for fragment in fragments
            ],
            "note": (
                "Cada fragmento incluye su procedencia en 'source'."
                if fragments
                else "Sin coincidencias: el CV no cubre ese tema."
            ),
        }

    @staticmethod
    def _get_experience(profile: Profile, arguments: dict[str, Any]) -> Any:
        company = str(arguments.get("company", "")).strip()

        def render(experience: Any) -> dict[str, Any]:
            return {
                "company": experience.company,
                "role": experience.role,
                "period": experience.period,
                "company_description": experience.company_description,
                "achievements": list(experience.achievements),
            }

        if company:
            match = profile.find_experience(company)
            if match is None:
                available = [e.company for e in profile.experiences]
                return {
                    "error": f"No hay experiencia registrada en '{company}'.",
                    "available": available,
                }
            return render(match)

        return [render(experience) for experience in profile.experiences]

    @staticmethod
    def _get_projects(profile: Profile, arguments: dict[str, Any]) -> Any:
        name = str(arguments.get("name", "")).strip()

        def render(project: Any) -> dict[str, Any]:
            return {
                "name": project.name,
                "period": project.period,
                "description": project.description,
            }

        if name:
            match = profile.find_project(name)
            if match is None:
                return {
                    "error": f"No hay proyecto registrado con el nombre '{name}'.",
                    "available": [p.name for p in profile.projects],
                }
            return render(match)

        return [render(project) for project in profile.projects]

    @staticmethod
    def _get_certifications(profile: Profile, arguments: dict[str, Any]) -> Any:
        return [
            {
                "name": certification.name,
                "issuer": certification.issuer,
                "year": certification.year,
            }
            for certification in profile.certifications
        ]

    @staticmethod
    def _get_tech_stack(profile: Profile, arguments: dict[str, Any]) -> Any:
        category = str(arguments.get("category", "")).strip()

        if category:
            match = profile.find_skill_category(category)
            if match is None:
                return {
                    "error": f"No hay categoría '{category}' en el stack.",
                    "available": [c.name for c in profile.skill_categories],
                }
            return {"category": match.name, "skills": list(match.skills)}

        return [
            {"category": c.name, "skills": list(c.skills)} for c in profile.skill_categories
        ]

    @staticmethod
    def _get_contact_info(profile: Profile, _: dict[str, Any]) -> dict[str, Any]:
        channels = allowed_contact_channels(profile.contact_channels)
        return {
            "channels": [{"kind": c.kind, "value": c.value, "url": c.url} for c in channels],
            "note": (
                "Estos son los únicos canales disponibles. No hay teléfono ni "
                "domicilio que compartir."
            ),
        }
