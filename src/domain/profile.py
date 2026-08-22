"""Entidades del perfil profesional.

Capa de dominio: no importa nada fuera de la biblioteca estándar. Aquí vive el
*qué* es un perfil, sin saber de dónde salen los datos (infraestructura) ni cómo
se conversa sobre ellos (aplicación).

El perfil se almacena **solo en español**, que es el idioma canónico del CV. El
agente responde en el idioma de quien pregunta traduciendo en el momento, en lugar
de mantener una segunda copia del contenido. Guardar dos versiones obligaría a
actualizar ambas y permitiría que divergieran; con una sola no existe esa clase de
error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

Language = Literal["es", "en"]

_T = TypeVar("_T")


def _buscar(items: tuple[_T, ...], query: str, campo: Callable[[_T], str]) -> _T | None:
    """Primera coincidencia por subcadena, sin distinguir mayúsculas.

    La misma regla de tolerancia sirve para empresas, proyectos y categorías;
    tenerla escrita una vez evita que mejorarla en un sitio la deje peor en los
    otros dos.
    """
    needle = query.strip().lower()
    if not needle:
        return None
    return next((item for item in items if needle in campo(item).lower()), None)


@dataclass(frozen=True)
class ContactChannel:
    """Un canal de contacto publicable.

    El `kind` es lo que la política de divulgación evalúa para decidir si el
    canal puede compartirse. Ver `domain.policies`.
    """

    kind: str
    value: str
    url: str | None = None


@dataclass(frozen=True)
class Experience:
    company: str
    role: str
    period: str
    company_description: str
    achievements: tuple[str, ...]


@dataclass(frozen=True)
class Education:
    degree: str
    institution: str
    period: str


@dataclass(frozen=True)
class Certification:
    name: str
    issuer: str
    year: str


@dataclass(frozen=True)
class Project:
    name: str
    period: str
    description: str


@dataclass(frozen=True)
class Recognition:
    description: str


@dataclass(frozen=True)
class SkillCategory:
    name: str
    skills: tuple[str, ...]


@dataclass(frozen=True)
class LanguageSkill:
    name: str
    level: str


@dataclass(frozen=True)
class Profile:
    """Raíz del agregado: todo lo que el agente puede llegar a decir."""

    full_name: str
    headline: str
    location: str
    summary: str
    years_of_experience: int
    contact_channels: tuple[ContactChannel, ...]
    experiences: tuple[Experience, ...]
    education: tuple[Education, ...]
    languages: tuple[LanguageSkill, ...]
    skill_categories: tuple[SkillCategory, ...]
    certifications: tuple[Certification, ...]
    projects: tuple[Project, ...]
    recognitions: tuple[Recognition, ...]

    def find_experience(self, company_query: str) -> Experience | None:
        """Busca una experiencia por nombre de empresa, de forma tolerante.

        Quien pregunta escribe "Abba" o "arbomex", no la razón social completa.
        """
        return _buscar(self.experiences, company_query, lambda e: e.company)

    def find_project(self, name_query: str) -> Project | None:
        return _buscar(self.projects, name_query, lambda p: p.name)

    def find_skill_category(self, category_query: str) -> SkillCategory | None:
        return _buscar(self.skill_categories, category_query, lambda c: c.name)
