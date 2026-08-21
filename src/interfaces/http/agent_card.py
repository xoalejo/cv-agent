"""Tarjeta de agente A2A, publicada en `/.well-known/agent-card.json`.

Sirve para que un cliente descubra qué es este agente y cómo hablarle sin que
alguien tenga que teclear los datos a mano. La plataforma del reto la usa para
autocompletar su formulario de registro.

Se declara **solo lo que el servicio realmente hace**. En concreto,
`streaming: false`: el endpoint responde de forma síncrona y rechaza
`stream: true` de forma explícita. Anunciar una capacidad que no existe sería
peor que no anunciarla, porque un cliente que la creyera disponible fallaría al
usarla.

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
    "Cuéntame de sus patentes ante el IMPI",
    "What is his experience building AI agents?",
)


def build_agent_card(profile: Profile, *, base_url: str) -> dict[str, Any]:
    """Construye la tarjeta a partir del perfil y de la URL desde la que se sirve.

    La URL se toma de la petición en lugar de fijarse en configuración: así la
    tarjeta es correcta en local, en una vista previa y en producción sin tener
    que redesplegar con el dominio escrito a mano.
    """
    base = base_url.rstrip("/")

    return {
        "protocolVersion": "0.2.9",
        "name": f"Agente de CV de {profile.full_name}",
        "description": (
            f"Conversa sobre la trayectoria profesional de {profile.full_name}: "
            "experiencia, habilidades, proyectos, patentes y formación. "
            "Responde en español o inglés según el idioma de la pregunta y "
            "mantiene la continuidad del hilo."
        ),
        "url": base,
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "documentationUrl": "https://github.com/xoalejo/cv-agent",
        "provider": {
            "organization": profile.full_name,
            "url": "https://github.com/xoalejo",
        },
        "capabilities": {
            # Declarado como es: el endpoint es síncrono y rechaza stream=true.
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
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
                    "proyectos, patentes, formación y reconocimientos, citando la "
                    "procedencia de cada dato dentro del CV."
                ),
                "tags": ["cv", "perfil profesional", "reclutamiento", "bilingüe"],
                "examples": list(_EXAMPLES),
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
        # Extensión no estándar: la plataforma pide la URL de Open Responses para
        # autocompletar su formulario, y el spec A2A no tiene un campo para eso.
        "openResponses": {
            "baseUrl": base,
            "endpoint": f"{base}/responses",
            "conversationState": "replay_transcript",
            "authentication": "bearer",
        },
    }
