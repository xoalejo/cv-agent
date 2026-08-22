"""Modos de fallo del motor de lenguaje, como parte del contrato del puerto.

Viven aquí y no en el adaptador de OpenAI porque **son parte de lo que el puerto
promete**. Si estas clases pertenecieran al adaptador, un motor alternativo
tendría que importar el módulo de OpenAI para lanzar los tipos correctos, o la
capa HTTP dejaría de saber traducirlos: justo lo contrario de la sustituibilidad
que los puertos existen para dar.

Cada clase distingue una causa que merece una respuesta distinta. Colapsarlas en
una sola haría que un límite pasajero y una credencial mal configurada se
comunicaran igual, y son problemas que se resuelven de forma opuesta.

El módulo no importa nada fuera de la biblioteca estándar, de modo que la capa
HTTP puede conocer los errores sin arrastrar el SDK del proveedor.
"""

from __future__ import annotations


class LLMEngineError(RuntimeError):
    """Fallo al hablar con el proveedor del modelo.

    Se traduce a un error genérico en la respuesta HTTP: el detalle se queda en
    los logs del servidor, no viaja al cliente.
    """


class LLMRateLimitError(LLMEngineError):
    """El proveedor rechazó por cuota (peticiones o tokens por minuto).

    Es transitorio: reintentar más tarde tiene sentido, y por eso viaja al
    cliente como 429 con `Retry-After` y no como un 502.
    """

    def __init__(self, message: str, *, retry_after: int = 20) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMConfigurationError(LLMEngineError):
    """Credencial inválida o modelo inexistente.

    Reintentar no lo arregla: requiere corregir la configuración del servicio.
    Se separa para que no se confunda con una indisponibilidad pasajera.
    """
