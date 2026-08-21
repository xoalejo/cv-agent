"""Búsqueda léxica sobre el perfil, con procedencia.

Implementa el puerto `ProfileSearch`. La elección es deliberada y proporcional al
corpus: el perfil completo son unas 1,500 palabras. Un índice
vectorial añadiría un servicio que operar, una dependencia que mantener y latencia
de red por consulta, sin mejorar de forma medible el recall sobre un texto de este
tamaño. Al quedar detrás del puerto, cambiarlo por embeddings más adelante no toca
el caso de uso.

El corpus está en español. El prompt instruye al modelo a formular la consulta en
español aunque converse en otro idioma, de modo que la búsqueda opera siempre
sobre el mismo vocabulario que el índice.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.domain.fragment import ProfileFragment, Section
from src.domain.profile import Profile

# Palabras que aparecen en casi cualquier consulta y no discriminan nada. Se
# escriben como texto y se parten en tiempo de importación: una lista literal de
# doscientos elementos sería ilegible en una revisión de código.
_STOPWORDS = frozenset(
    """
    a al algo alguna algunas alguno algunos ante antes como con contra cual cuales cuando
    de del desde donde dos el ella ellas ellos en entre era eres es esa esas ese eso esos
    esta estas este esto estos ha han hace hacer hasta hay la las le les lo los mas más me
    mi mis mucho muy nos o para pero por porque que qué quien quienes se ser si sin sobre
    son su sus te tiene tienen tu tus un una uno unos y ya
    about above after all also an and any are as at be been but by can could did do does
    for from had has have he her his how in into is it its me more most my no not of on
    or our over said she so some such than that the their them then there these they this
    those to too under up use used using was we were what when where which who why will
    with would you your
    """.split()  # noqa: SIM905 - legibilidad por encima del literal precalculado
)

_WORD = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    """Minúsculas sin acentos, para que "automatización" y "automatizacion" coincidan."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(_normalize(text))


def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokenize(text) if len(t) > 2 and t not in _STOPWORDS}


@dataclass(frozen=True)
class _IndexEntry:
    """Una entrada del índice: el texto más su procedencia."""

    text: str
    section: Section
    context: str | None
    tokens: set[str]
    normalized: str
    #: Palabras del fragmento, para la coincidencia por prefijo.
    words: tuple[str, ...]

    def to_fragment(self) -> ProfileFragment:
        return ProfileFragment(
            text=self.text,
            section=self.section,
            context=self.context,
        )


class LexicalProfileSearch:
    """Índice en memoria construido una vez al arrancar el proceso."""

    def __init__(self, profile: Profile) -> None:
        self._entries = self._build_index(profile)

    # -- construcción ---------------------------------------------------------

    @staticmethod
    def _entry(text: str, section: Section, context: str | None) -> _IndexEntry:
        # El contexto (empresa, proyecto) entra en los tokens para que buscar por
        # el nombre de una empresa recupere también sus logros.
        extra = context or ""
        normalized = _normalize(text)
        return _IndexEntry(
            text=text,
            section=section,
            context=context,
            tokens=_content_tokens(f"{text} {extra}"),
            normalized=normalized,
            words=tuple(_WORD.findall(normalized)),
        )

    @classmethod
    def _build_index(cls, profile: Profile) -> tuple[_IndexEntry, ...]:
        entries: list[_IndexEntry] = [
            cls._entry(profile.summary, Section.SUMMARY, None),
            cls._entry(profile.headline, Section.SUMMARY, None),
        ]

        for experience in profile.experiences:
            header = (
                f"{experience.role} en {experience.company} "
                f"({experience.period}). {experience.company_description}"
            )
            entries.append(cls._entry(header, Section.EXPERIENCE, experience.company))
            for achievement in experience.achievements:
                entries.append(cls._entry(achievement, Section.EXPERIENCE, experience.company))

        for education in profile.education:
            text = f"{education.degree}. {education.institution} ({education.period})."
            entries.append(cls._entry(text, Section.EDUCATION, education.institution))

        for category in profile.skill_categories:
            text = f"{category.name}: {', '.join(category.skills)}."
            entries.append(cls._entry(text, Section.SKILLS, category.name))

        for certification in profile.certifications:
            text = f"{certification.name}, {certification.issuer} ({certification.year})."
            entries.append(cls._entry(text, Section.CERTIFICATIONS, certification.issuer))

        for patent in profile.patents:
            text = f"{patent.title} Expediente IMPI {patent.file_number}. {patent.status}."
            entries.append(cls._entry(text, Section.PATENTS, patent.file_number))

        for project in profile.projects:
            text = f"{project.name} ({project.period}). {project.description}"
            entries.append(cls._entry(text, Section.PROJECTS, project.name))

        for recognition in profile.recognitions:
            entries.append(cls._entry(recognition.description, Section.RECOGNITIONS, None))

        for language_skill in profile.languages:
            text = f"{language_skill.name}: {language_skill.level}."
            entries.append(cls._entry(text, Section.LANGUAGES, None))

        return tuple(entries)

    # -- consulta -------------------------------------------------------------

    def search(self, query: str, *, limit: int = 5) -> list[ProfileFragment]:
        query_tokens = _content_tokens(query)
        if not query_tokens:
            return []

        normalized_query = _normalize(query.strip())
        scored: list[tuple[float, int, _IndexEntry]] = []

        for position, entry in enumerate(self._entries):
            overlap = query_tokens & entry.tokens
            score = float(len(overlap))

            # Un término que no coincide como palabra completa puede seguir siendo
            # relevante como prefijo: "kube" en "kubernetes", "automat" en
            # "automatización". Vale menos que una coincidencia exacta.
            #
            # La coincidencia se ancla al inicio de palabra a propósito. Buscar la
            # subcadena en cualquier posición produce falsos positivos que cruzan
            # idiomas ("files" dentro de "perfiles") y ensucian los resultados con
            # fragmentos que no tienen relación con la consulta.
            for token in query_tokens - overlap:
                if len(token) > 3 and any(word.startswith(token) for word in entry.words):
                    score += 0.5

            # La consulta completa presente literalmente es la señal más fuerte.
            if len(normalized_query) > 3 and normalized_query in entry.normalized:
                score += 2.0

            if score > 0:
                # `position` desempata de forma estable: sin él, dos fragmentos con
                # el mismo puntaje se ordenarían de manera arbitraria.
                scored.append((score, -position, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry.to_fragment() for _, _, entry in scored[:limit]]
