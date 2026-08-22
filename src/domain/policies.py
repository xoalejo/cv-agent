"""Políticas de divulgación: qué puede decir el agente y qué no.

Estas reglas viven en el dominio, no en el prompt. Un prompt es una petición al
modelo; una regla de dominio es código que se ejecuta siempre. La diferencia
importa cuando el sistema se expone públicamente y alguien intenta sacarle datos
que no debe dar.

Defensa en profundidad sobre el teléfono personal, en tres capas:

1. El número **no existe** en los datos del perfil. No hay dato que filtrar.
2. `ALLOWED_CONTACT_KINDS` restringe los canales publicables a nivel de dominio.
3. `redact_contact_data` revisa la salida final por si el número entró por otra
   vía: por ejemplo, alguien que ya tiene el CV lo pega en el chat y pide que el
   agente lo confirme o lo repita.

Nota deliberada: el número **no se codifica aquí** para compararlo. Hacerlo
publicaría en un repositorio público exactamente el dato que estas reglas
protegen, y un hash de diez dígitos es trivial de revertir por fuerza bruta. Por
eso la capa 3 detecta *formas* de teléfono, no un número concreto.
"""

from __future__ import annotations

import re

from src.domain.profile import ContactChannel, Language

#: Canales que el agente puede compartir. El teléfono queda fuera por diseño.
ALLOWED_CONTACT_KINDS: frozenset[str] = frozenset({"email", "linkedin", "github"})

# Separadores tolerados dentro de un número. La barra "/" queda fuera a
# propósito: los expedientes de patente (MX/a/2024/008296) la usan, y tratarla
# como separador convertiría un número de expediente en un falso positivo.
_SEP = r"[\s\-.() ]"

# +52 555 123 4567 y cualquier variante con separadores.
_INTERNATIONAL = re.compile(rf"\+{_SEP}*\d(?:{_SEP}*\d){{7,}}")

# "teléfono: 555 123 4567", "cel 5551234567", "whatsapp +52...".
_LABELED = re.compile(
    rf"(?i)\b(?:tel(?:[ée]fono)?|cel(?:ular)?|m[óo]vil|phone|mobile|whats\s?app)\b"
    rf"{_SEP}*:?{_SEP}*\+?\d(?:{_SEP}*\d){{6,}}"
)

# Diez o más dígitos corridos. Ninguna métrica real del perfil llega a esa
# longitud (17,000 archivos, 140 máquinas, años de 4 dígitos), y los separadores
# admitidos impiden que un expediente de patente se confunda con un teléfono.
_BARE_LONG_NUMBER = re.compile(rf"\b\d(?:{_SEP}*\d){{9,}}\b")

_PATTERNS = (_INTERNATIONAL, _LABELED, _BARE_LONG_NUMBER)

_REDACTION = {
    "es": "[dato de contacto no divulgado]",
    "en": "[contact detail not disclosed]",
}


def allowed_contact_channels(
    channels: tuple[ContactChannel, ...],
) -> tuple[ContactChannel, ...]:
    """Filtra los canales de contacto a los que la política permite compartir."""
    return tuple(c for c in channels if c.kind in ALLOWED_CONTACT_KINDS)


def contains_contact_data(text: str) -> bool:
    """Indica si el texto contiene algo con forma de teléfono."""
    return any(pattern.search(text) for pattern in _PATTERNS)


def redact_contact_data(text: str, language: Language = "es") -> str:
    """Sustituye cualquier secuencia con forma de teléfono por un marcador.

    Se aplica sobre la respuesta final del agente. Si nunca dispara, que es lo
    esperado porque el dato no está en el sistema, no altera el texto.
    """
    marker = _REDACTION[language]
    redacted = text
    for pattern in _PATTERNS:
        redacted = pattern.sub(marker, redacted)
    return redacted


#: Temas que el agente declina con cortesía, redirigiendo a contacto directo.
#: Se declaran aquí para que el prompt y las pruebas lean la misma fuente y no
#: se desincronicen.
OUT_OF_SCOPE_TOPICS: tuple[str, ...] = (
    "expectativas salariales o condiciones económicas",
    "opiniones políticas, religiosas o personales",
    "datos personales sensibles (domicilio, teléfono, familia, salud)",
    "preguntas de conocimiento general sobre negocios, tecnología o economía que "
    "no sean específicamente sobre su trayectoria, aunque suenen profesionales "
    '(ej. "¿cómo afecta la economía a una empresa?", "¿qué es Kubernetes?")',
)
