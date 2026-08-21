"""Entidades del perfil profesional.

Capa de dominio: no importa nada fuera de la biblioteca estándar. Aquí vive el
*qué* es un perfil, sin saber de dónde salen los datos (infraestructura) ni cómo
se conversa sobre ellos (aplicación).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Language = Literal["es", "en"]


@dataclass(frozen=True)
class LocalizedText:
    """Texto con su versión en español e inglés.

    El agente es bilingüe y responde en el idioma en que le preguntan. Mantener
    ambas versiones juntas en el mismo objeto evita que los datos se
    desincronicen entre idiomas, que es exactamente el defecto que traían los
    PDFs originales (un reconocimiento decía "300 proyectos" en español y "60"
    en inglés).
    """

    es: str
    en: str

    def get(self, language: Language) -> str:
        return self.en if language == "en" else self.es


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
    role: LocalizedText
    period: str
    company_description: LocalizedText
    achievements: tuple[LocalizedText, ...]


@dataclass(frozen=True)
class Education:
    degree: LocalizedText
    institution: str
    period: str


@dataclass(frozen=True)
class Certification:
    name: LocalizedText
    issuer: str
    year: LocalizedText


@dataclass(frozen=True)
class Patent:
    """Patente en trámite ante el IMPI.

    Los títulos oficiales están registrados en español; `title.en` es una
    traducción de cortesía y así se declara al usuario cuando corresponde.
    """

    title: LocalizedText
    file_number: str
    status: LocalizedText


@dataclass(frozen=True)
class Project:
    name: LocalizedText
    period: str
    description: LocalizedText


@dataclass(frozen=True)
class Recognition:
    description: LocalizedText


@dataclass(frozen=True)
class SkillCategory:
    name: LocalizedText
    skills: tuple[str, ...]


@dataclass(frozen=True)
class LanguageSkill:
    name: LocalizedText
    level: LocalizedText


@dataclass(frozen=True)
class Profile:
    """Raíz del agregado: todo lo que el agente puede llegar a decir."""

    full_name: str
    headline: LocalizedText
    location: LocalizedText
    summary: LocalizedText
    years_of_experience: int
    contact_channels: tuple[ContactChannel, ...]
    experiences: tuple[Experience, ...]
    education: tuple[Education, ...]
    languages: tuple[LanguageSkill, ...]
    skill_categories: tuple[SkillCategory, ...]
    certifications: tuple[Certification, ...]
    patents: tuple[Patent, ...]
    projects: tuple[Project, ...]
    recognitions: tuple[Recognition, ...]

    def find_experience(self, company_query: str) -> Experience | None:
        """Busca una experiencia por nombre de empresa, de forma tolerante.

        Quien pregunta escribe "Abba" o "arbomex", no la razón social completa.
        """
        needle = company_query.strip().lower()
        if not needle:
            return None
        for experience in self.experiences:
            if needle in experience.company.lower():
                return experience
        return None

    def find_project(self, name_query: str) -> Project | None:
        needle = name_query.strip().lower()
        if not needle:
            return None
        for project in self.projects:
            if needle in project.name.es.lower() or needle in project.name.en.lower():
                return project
        return None

    def find_skill_category(self, category_query: str) -> SkillCategory | None:
        needle = category_query.strip().lower()
        if not needle:
            return None
        for category in self.skill_categories:
            if needle in category.name.es.lower() or needle in category.name.en.lower():
                return category
        return None
