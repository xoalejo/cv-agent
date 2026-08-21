"""Fragmento del perfil con su procedencia.

Es la unidad que devuelve la búsqueda. Un fragmento no es solo texto: carga de
dónde salió, y eso es lo que permite que una afirmación del agente se pueda
rastrear hasta una sección concreta del CV en lugar de emerger difusa del prompt.
Es el mecanismo de grounding del sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Section(StrEnum):
    """Secciones del CV. El valor es el que se muestra como procedencia."""

    SUMMARY = "perfil"
    EXPERIENCE = "experiencia"
    EDUCATION = "formacion"
    SKILLS = "stack"
    CERTIFICATIONS = "certificaciones"
    PATENTS = "patentes"
    PROJECTS = "proyectos"
    RECOGNITIONS = "reconocimientos"
    LANGUAGES = "idiomas"


@dataclass(frozen=True)
class ProfileFragment:
    """Un trozo del perfil junto con su origen verificable."""

    text: str
    section: Section
    #: Contexto concreto dentro de la sección: la empresa, el proyecto, etc.
    #: `None` cuando la sección no se subdivide (por ejemplo, el resumen).
    context: str | None = None

    @property
    def citation(self) -> str:
        """Etiqueta legible de procedencia, para que el modelo la reproduzca."""
        if self.context:
            return f"{self.section.value} · {self.context}"
        return self.section.value
