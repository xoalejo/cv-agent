"""Configuración del servicio, leída del entorno.

Nada de secretos en código. En local se cargan desde `.env` (ignorado por git);
en Fly.io llegan como secrets del runtime.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Proveedor del modelo -------------------------------------------------
    openai_api_key: str = Field(default="", description="Clave de la API de OpenAI.")

    #: El modelo lo decide el servidor, no quien llama. La plataforma que registra
    #: el agente ofrece un campo "Modelo" opcional; aceptarlo dejaría que un
    #: tercero forzara un modelo caro o inexistente contra nuestra cuenta.
    #:
    #: Se parte del nivel más económico de la familia. La tarea es Q&A fundamentado
    #: sobre un contexto que ya se le entrega, no razonamiento intensivo, así que
    #: la pregunta no es "¿cuál es el mejor modelo?" sino "¿cuál es el más barato
    #: que supera la suite de evaluación?". Los casos de `pii`, `injection` y
    #: `honestidad` son los que discriminan: si el nivel elegido falla alguno, se
    #: sube al siguiente. Verificar el identificador exacto con:
    #:     python -c "from openai import OpenAI; [print(m.id) for m in OpenAI().models.list() if m.id.startswith('gpt-5')]"
    openai_model: str = Field(default="gpt-5.6-luna")

    #: Esfuerzo de razonamiento ("none", "low", "medium", "high", "xhigh", "max").
    #:
    #: Esta familia de modelos NO admite `temperature`: la API rechaza cualquier
    #: valor distinto del predeterminado. El control disponible es este.
    #:
    #: Se usa "low" por medición, no por intuición. Se probó "none", que suprime
    #: los tokens de razonamiento previos al texto, pero con el resto del sistema
    #: ya optimizado la diferencia es de 0.06 s y a cambio el modelo sigue peor
    #: las instrucciones matizadas: en las pruebas de tono adelantaba la mención
    #: de lo que falta y omitía el impacto medible.
    #:
    #: La latencia percibida no venía del razonamiento sino de las vueltas extra
    #: por herramientas; ese es el problema que se atacó. Ver
    #: `scripts/bench_latency.py`.
    reasoning_effort: str = Field(default="low")

    request_timeout_seconds: float = Field(default=60.0)

    #: Vueltas máximas al modelo dentro de un turno (control de costo).
    max_tool_iterations: int = Field(default=5)

    # -- Seguridad del endpoint ----------------------------------------------
    #: Bearer token que debe presentar quien consuma `/responses`. Si queda vacío
    #: el servicio arranca sin autenticación, algo que solo tiene sentido en
    #: desarrollo local; `require_auth` lo hace explícito.
    agent_api_key: str = Field(default="")

    require_auth: bool = Field(default=True)

    #: Peticiones por ventana y tamaño de la ventana, por cliente.
    #:
    #: La protección real del endpoint es la credencial; este límite es defensa
    #: secundaria contra una clave filtrada o un cliente en bucle. Por eso no se
    #: aprieta tanto como para estorbar el uso legítimo: la propia suite de
    #: evaluación consume del orden de 26 peticiones seguidas, y varias personas
    #: pueden estar probando el agente con la misma credencial a la vez.
    rate_limit_requests: int = Field(default=60)
    rate_limit_window_seconds: int = Field(default=60)

    #: Integración servidor-a-servidor: sin orígenes de navegador por defecto.
    cors_allow_origins: str = Field(default="")

    # -- Operación ------------------------------------------------------------
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_allow_origins.strip()
        if not raw:
            return []
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def auth_enabled(self) -> bool:
        return self.require_auth and bool(self.agent_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
