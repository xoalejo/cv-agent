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
    openai_model: str = Field(default="gpt-4.1-mini")

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
