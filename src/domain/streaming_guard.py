"""Guarda de divulgación para texto que se emite por partes.

En una respuesta completa basta con revisar el texto y redactar. Al emitir
fragmentos conforme se generan, ese enfoque no sirve: un número podría salir
repartido en varios trozos y quedar fuera antes de que el patrón sea reconocible.
Lo emitido no se puede retirar.

La solución es **retener la cola**. Mientras el final del texto acumulado pueda
ser el principio de algo con forma de teléfono, esa parte no se emite y se
guarda. Se libera cuando llega texto que demuestra que no lo era, o al cerrar.

El resultado es que ninguna secuencia de dígitos con forma de teléfono sale del
servicio, ni completa ni troceada, sin renunciar a emitir el resto en cuanto
está disponible.
"""

from __future__ import annotations

import re

from src.domain.policies import redact_contact_data
from src.domain.profile import Language

#: Caracteres que pueden formar parte de un número telefónico. Mientras el texto
#: termine en una secuencia de estos, esa cola queda retenida.
_TAIL = re.compile(r"[\d+][\d\s\-.()+]*$")

#: Palabras que anteceden a un número y que la política redacta junto con él. Si
#: el texto termina en una de ellas, se retiene por si le siguen dígitos.
_LABEL_TAIL = re.compile(
    r"(?i)\b(?:tel(?:[ée]fono)?|cel(?:ular)?|m[óo]vil|phone|mobile|whats\s?app)"
    r"[\s:.\-]*$"
)


class StreamingDisclosureGuard:
    """Filtra fragmentos de texto aplicando la política de divulgación.

    Uso:
        guard = StreamingDisclosureGuard("es")
        for delta in fuente:
            if seguro := guard.feed(delta):
                emitir(seguro)
        if resto := guard.flush():
            emitir(resto)
    """

    def __init__(self, language: Language = "es") -> None:
        self._language = language
        self._pending = ""

    def feed(self, delta: str) -> str:
        """Incorpora un fragmento y devuelve la parte que ya es seguro emitir."""
        self._pending += delta

        corte = self._safe_cut(self._pending)
        if corte == 0:
            return ""

        emitible, self._pending = self._pending[:corte], self._pending[corte:]
        return redact_contact_data(emitible, self._language)

    def flush(self) -> str:
        """Cierra el flujo y devuelve lo retenido, ya redactado."""
        resto, self._pending = self._pending, ""
        return redact_contact_data(resto, self._language)

    @staticmethod
    def _safe_cut(text: str) -> int:
        """Posición hasta la que se puede emitir sin partir un posible teléfono.

        Devuelve el índice donde empieza la cola que hay que retener; si nada hay
        que retener, devuelve la longitud completa.
        """
        for patron in (_TAIL, _LABEL_TAIL):
            if match := patron.search(text):
                return match.start()
        return len(text)
