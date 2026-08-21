"""Búsqueda léxica sobre el perfil, con procedencia.

Implementa el puerto `ProfileSearch`. La elección es deliberada y proporcional al
corpus: el perfil completo son unas 1,500 palabras en dos idiomas. Un índice
vectorial añadiría un servicio que operar, una dependencia que mantener y latencia
de red por consulta, sin mejorar de forma medible el recall sobre un texto de este
tamaño. Al quedar detrás del puerto, cambiarlo por embeddings más adelante no toca
el caso de uso.

El índice cubre español e inglés simultáneamente: quien pregunta en inglés por
"traceability" encuentra el mismo material que quien pregunta por "trazabilidad".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.domain.fragment import ProfileFragment, Section
from src.domain.profile import Language, LocalizedText, Profile

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
    """Una entrada del índice: el texto en ambos idiomas más su procedencia."""

    text: LocalizedText
    section: Section
    context: str | None
    tokens: set[str]
    normalized: str

    def to_fragment(self, language: Language) -> ProfileFragment:
        return ProfileFragment(
            text=self.text.get(language),
            section=self.section,
            context=self.context,
        )


class LexicalProfileSearch:
    """Índice en memoria construido una vez al arrancar el proceso."""

    def __init__(self, profile: Profile) -> None:
        self._entries = self._build_index(profile)

    # -- construcción ---------------------------------------------------------

    @staticmethod
    def _entry(text: LocalizedText, section: Section, context: str | None) -> _IndexEntry:
        # Se indexan ambos idiomas juntos: la consulta encuentra el fragmento sin
        # importar en qué idioma esté formulada.
        combined = f"{text.es} {text.en}"
        extra = context or ""
        return _IndexEntry(
            text=text,
            section=section,
            context=context,
            tokens=_content_tokens(f"{combined} {extra}"),
            normalized=_normalize(combined),
        )

    @classmethod
    def _build_index(cls, profile: Profile) -> tuple[_IndexEntry, ...]:
        entries: list[_IndexEntry] = [
            cls._entry(profile.summary, Section.SUMMARY, None),
            cls._entry(profile.headline, Section.SUMMARY, None),
        ]

        for experience in profile.experiences:
            header = LocalizedText(
                es=(
                    f"{experience.role.es} en {experience.company} "
                    f"({experience.period}). {experience.company_description.es}"
                ),
                en=(
                    f"{experience.role.en} at {experience.company} "
                    f"({experience.period}). {experience.company_description.en}"
                ),
            )
            entries.append(cls._entry(header, Section.EXPERIENCE, experience.company))
            for achievement in experience.achievements:
                entries.append(
                    cls._entry(achievement, Section.EXPERIENCE, experience.company)
                )

        for education in profile.education:
            text = LocalizedText(
                es=f"{education.degree.es}. {education.institution} ({education.period}).",
                en=f"{education.degree.en}. {education.institution} ({education.period}).",
            )
            entries.append(cls._entry(text, Section.EDUCATION, education.institution))

        for category in profile.skill_categories:
            skills = ", ".join(category.skills)
            text = LocalizedText(
                es=f"{category.name.es}: {skills}.",
                en=f"{category.name.en}: {skills}.",
            )
            entries.append(cls._entry(text, Section.SKILLS, category.name.es))

        for certification in profile.certifications:
            text = LocalizedText(
                es=(
                    f"{certification.name.es} — {certification.issuer} "
                    f"({certification.year.es})."
                ),
                en=(
                    f"{certification.name.en} — {certification.issuer} "
                    f"({certification.year.en})."
                ),
            )
            entries.append(cls._entry(text, Section.CERTIFICATIONS, certification.issuer))

        for patent in profile.patents:
            text = LocalizedText(
                es=(
                    f"{patent.title.es} Expediente IMPI {patent.file_number}. "
                    f"{patent.status.es}."
                ),
                en=(
                    f"{patent.title.en} IMPI file {patent.file_number}. "
                    f"{patent.status.en}."
                ),
            )
            entries.append(cls._entry(text, Section.PATENTS, patent.file_number))

        for project in profile.projects:
            text = LocalizedText(
                es=f"{project.name.es} ({project.period}). {project.description.es}",
                en=f"{project.name.en} ({project.period}). {project.description.en}",
            )
            entries.append(cls._entry(text, Section.PROJECTS, project.name.es))

        for recognition in profile.recognitions:
            entries.append(cls._entry(recognition.description, Section.RECOGNITIONS, None))

        for language_skill in profile.languages:
            text = LocalizedText(
                es=f"{language_skill.name.es}: {language_skill.level.es}.",
                en=f"{language_skill.name.en}: {language_skill.level.en}.",
            )
            entries.append(cls._entry(text, Section.LANGUAGES, None))

        return tuple(entries)

    # -- consulta -------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        language: Language = "es",
        limit: int = 5,
    ) -> list[ProfileFragment]:
        query_tokens = _content_tokens(query)
        if not query_tokens:
            return []

        normalized_query = _normalize(query.strip())
        scored: list[tuple[float, int, _IndexEntry]] = []

        for position, entry in enumerate(self._entries):
            overlap = query_tokens & entry.tokens
            score = float(len(overlap))

            # Un término que no coincide como palabra completa puede seguir siendo
            # relevante como subcadena: "rag" dentro de "ragas", "kube" en
            # "kubernetes". Vale menos que una coincidencia exacta.
            for token in query_tokens - overlap:
                if len(token) > 3 and token in entry.normalized:
                    score += 0.5

            # La consulta completa presente literalmente es la señal más fuerte.
            if len(normalized_query) > 3 and normalized_query in entry.normalized:
                score += 2.0

            if score > 0:
                # `position` desempata de forma estable: sin él, dos fragmentos con
                # el mismo puntaje se ordenarían de manera arbitraria.
                scored.append((score, -position, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry.to_fragment(language) for _, _, entry in scored[:limit]]
