"""Tarjeta de agente A2A, publicada en `/.well-known/agent-card.json`.

Sirve para que un cliente descubra qué es este agente y cómo hablarle sin que
alguien tenga que teclear los datos a mano. La plataforma del reto la usa para
autocompletar su formulario de registro.

Se declara **solo lo que el servicio realmente hace**. `streaming: true` figura
aquí porque el endpoint implementa la secuencia de eventos SSE del protocolo, con
`sequence_number` correlativo y terminador `[DONE]`, no porque quede mejor:
anunciar una capacidad inexistente rompería a cualquier cliente que la creyera
disponible.

La tarjeta es pública por definición (es un mecanismo de descubrimiento) y no
contiene credenciales: solo declara que el endpoint espera un token Bearer, no
cuál es.
"""

from __future__ import annotations

from typing import Any

from src.domain.profile import Profile

#: Ejemplos que muestran de qué se puede conversar. Se eligen para cubrir el
#: rango real del agente: búsqueda transversal, dato puntual y bilingüismo.
_EXAMPLES = (
    "¿En qué empresas ha trabajado con RAG?",
    "¿Qué experiencia tiene en el sector financiero?",
    "¿Qué reconocimientos ha recibido?",
    "What is his experience building AI agents?",
)


def build_agent_card(profile: Profile, *, base_url: str) -> dict[str, Any]:
    """Construye la tarjeta a partir del perfil y de la URL desde la que se sirve.

    La URL se toma de la petición en lugar de fijarse en configuración: así la
    tarjeta es correcta en local, en una vista previa y en producción sin tener
    que redesplegar con el dominio escrito a mano.
    """
    base = base_url.rstrip("/")
    # Se anuncia la ruta versionada: es el contrato al que el servicio se
    # compromete y el que debería registrar una integración. La propia tarjeta
    # se sirve en la raíz, como exige la convención de `/.well-known/`.
    versioned = f"{base}/v1"
    endpoint = f"{versioned}/responses"

    return {
        "protocolVersion": "1.0",
        "name": f"Agente de CV de {profile.full_name}",
        "description": (
            f"Conversa sobre la trayectoria profesional de {profile.full_name}: "
            "experiencia, habilidades, proyectos y formación. "
            "Responde en español o inglés según el idioma de la pregunta y "
            "mantiene la continuidad del hilo."
        ),
        # `supportedInterfaces` es la forma de A2A v1.0 y sustituye al trío
        # `url` / `preferredTransport` / `additionalInterfaces`. Cada entrada
        # declara su propio enlace de protocolo; la primera es la preferida.
        #
        # El campo dentro de cada entrada es `protocolBinding`, no `transport`:
        # ese era el nombre en v0.3, y mezclarlos hace que un validador de v1.0
        # rechace la tarjeta entera.
        # La lista va por orden de preferencia. La primera entrada identifica el
        # protocolo concreto que habla el endpoint mediante el URI canónico de su
        # especificación, que es lo que A2A recomienda para enlaces no estándar:
        # `protocolBinding` es de forma libre y "debería ser un URI".
        #
        # La segunda describe el mismo endpoint en términos genéricos. Ambas son
        # ciertas y apuntan a la misma URL: un cliente que busque Open Responses
        # reconoce la primera, y uno que solo entienda los enlaces básicos de A2A
        # se queda con la segunda.
        # La lista va por orden de preferencia. La primera identifica el
        # protocolo concreto mediante el URI canónico de su especificación, que
        # es lo que A2A recomienda para enlaces no estándar: `protocolBinding` es
        # de forma libre y "debería ser un URI". La segunda describe el mismo
        # endpoint en términos genéricos, para un cliente que solo entienda los
        # enlaces básicos.
        "supportedInterfaces": [
            {
                "url": versioned,
                "protocolBinding": "https://openresponses.org",
                "protocolVersion": "1.0",
            },
            {
                "url": versioned,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            },
        ],
        # Se conservan los campos de v0.3 para consumidores que aún los lean.
        "url": versioned,
        "preferredTransport": "HTTP+JSON",
        "version": "1.0.0",
        "documentationUrl": "https://github.com/xoalejo/cv-agent",
        "provider": {
            "organization": profile.full_name,
            "url": "https://github.com/xoalejo",
        },
        "capabilities": {
            # El endpoint emite la secuencia de eventos SSE del protocolo cuando
            # la petición llega con stream=true.
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            # Mecanismo estándar de A2A para declarar extensiones de protocolo.
            "extensions": [
                {
                    "uri": "https://openresponses.org",
                    "description": "Endpoint compatible con Open Responses.",
                    "required": False,
                    "params": {"baseUrl": versioned, "endpoint": endpoint},
                }
            ],
        },
        # El historial completo llega en cada petición; el servicio no guarda
        # estado entre llamadas.
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Token que se envía como 'Authorization: Bearer ...'.",
            }
        },
        "security": [{"bearerAuth": []}],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "professional-profile",
                "name": "Trayectoria profesional",
                "description": (
                    "Responde preguntas sobre experiencia laboral, stack técnico, "
                    "proyectos, formación y reconocimientos, citando la "
                    "procedencia de cada dato dentro del CV."
                ),
                "tags": ["cv", "perfil profesional", "reclutamiento", "bilingüe"],
                "examples": list(_EXAMPLES),
            }
        ],
        # Extensión no estándar: la plataforma pide la URL de Open Responses para
        # autocompletar su formulario, y el spec A2A no tiene un campo para eso.
        "openResponses": {
            "baseUrl": versioned,
            "endpoint": endpoint,
            "conversationState": "replay_transcript",
            "authentication": "bearer",
        },
    }
