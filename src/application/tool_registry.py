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
from src.domain.profile import Language, Profile

_LANGUAGE_PARAM = {
    "type": "string",
    "enum": ["es", "en"],
    "description": (
        "Idioma en el que devolver el contenido. Usa el idioma de la conversación."
    ),
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_profile",
        "description": (
            "Busca en todo el CV y devuelve los fragmentos más relevantes junto con su "
            "procedencia (sección y empresa o proyecto). Úsala para preguntas que cruzan "
            "varias secciones —por ejemplo dónde ha usado una tecnología, qué experiencia "
            "tiene en un sector, o qué respalda una habilidad concreta— y cuando quieras "
            "citar de dónde sale un dato. Funciona en español y en inglés."
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
                "language": _LANGUAGE_PARAM,
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
                "language": _LANGUAGE_PARAM,
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
                "language": _LANGUAGE_PARAM,
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
            "properties": {"language": _LANGUAGE_PARAM},
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_patents",
        "description": (
            "Devuelve las patentes en trámite ante el IMPI, con número de expediente y "
            "estado del trámite."
        ),
        "parameters": {
            "type": "object",
            "properties": {"language": _LANGUAGE_PARAM},
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
                "language": _LANGUAGE_PARAM,
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


def _language_of(arguments: dict[str, Any]) -> Language:
    value = arguments.get("language")
    return "en" if value == "en" else "es"


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
            "get_patents": self._get_patents,
            "get_tech_stack": self._get_tech_stack,
            "get_contact_info": self._get_contact_info,
        }

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

        language = _language_of(arguments)
        fragments = self._search.search(query, language=language, limit=5)
        return {
            "query": query,
            "matches": [
                {"text": fragment.text, "source": fragment.citation}
                for fragment in fragments
            ],
            "note": (
                "Sin coincidencias: el CV no cubre ese tema."
                if not fragments
                else "Cada fragmento incluye su procedencia en 'source'."
            ),
        }

    @staticmethod
    def _get_experience(profile: Profile, arguments: dict[str, Any]) -> Any:
        language = _language_of(arguments)
        company = str(arguments.get("company", "")).strip()

        def render(experience: Any) -> dict[str, Any]:
            return {
                "company": experience.company,
                "role": experience.role.get(language),
                "period": experience.period,
                "company_description": experience.company_description.get(language),
                "achievements": [a.get(language) for a in experience.achievements],
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
        language = _language_of(arguments)
        name = str(arguments.get("name", "")).strip()

        def render(project: Any) -> dict[str, Any]:
            return {
                "name": project.name.get(language),
                "period": project.period,
                "description": project.description.get(language),
            }

        if name:
            match = profile.find_project(name)
            if match is None:
                return {
                    "error": f"No hay proyecto registrado con el nombre '{name}'.",
                    "available": [p.name.get(language) for p in profile.projects],
                }
            return render(match)

        return [render(project) for project in profile.projects]

    @staticmethod
    def _get_certifications(profile: Profile, arguments: dict[str, Any]) -> Any:
        language = _language_of(arguments)
        return [
            {
                "name": certification.name.get(language),
                "issuer": certification.issuer,
                "year": certification.year.get(language),
            }
            for certification in profile.certifications
        ]

    @staticmethod
    def _get_patents(profile: Profile, arguments: dict[str, Any]) -> Any:
        language = _language_of(arguments)
        return {
            "note": (
                "Patentes en trámite ante el IMPI. Los títulos oficiales están "
                "registrados en español."
            ),
            "patents": [
                {
                    "title": patent.title.get(language),
                    "file_number": patent.file_number,
                    "status": patent.status.get(language),
                }
                for patent in profile.patents
            ],
        }

    @staticmethod
    def _get_tech_stack(profile: Profile, arguments: dict[str, Any]) -> Any:
        language = _language_of(arguments)
        category = str(arguments.get("category", "")).strip()

        if category:
            match = profile.find_skill_category(category)
            if match is None:
                return {
                    "error": f"No hay categoría '{category}' en el stack.",
                    "available": [c.name.get(language) for c in profile.skill_categories],
                }
            return {"category": match.name.get(language), "skills": list(match.skills)}

        return [
            {"category": c.name.get(language), "skills": list(c.skills)}
            for c in profile.skill_categories
        ]

    @staticmethod
    def _get_contact_info(profile: Profile, _: dict[str, Any]) -> dict[str, Any]:
        channels = allowed_contact_channels(profile.contact_channels)
        return {
            "channels": [
                {"kind": c.kind, "value": c.value, "url": c.url} for c in channels
            ],
            "note": (
                "Estos son los únicos canales disponibles. No hay teléfono ni "
                "domicilio que compartir."
            ),
        }
