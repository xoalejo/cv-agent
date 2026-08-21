"""Autenticación y limitación de tasa del endpoint público.

El agente se expone en internet y consume una API de pago. Sin control de acceso,
cualquiera podría gastar el presupuesto del proveedor; sin límite de tasa, basta
con tener la clave para hacerlo.
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from collections import deque

from fastapi import Header, HTTPException, Request, status

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _client_fingerprint(request: Request, credential: str | None) -> str:
    """Identifica al cliente para efectos de límite de tasa.

    Se usa un prefijo de la credencial —nunca la credencial completa— para no
    exponerla si esta estructura acabara en un log o en un volcado de memoria.
    """
    if credential:
        return f"key:{credential[:8]}"
    client = request.client
    return f"ip:{client.host}" if client else "ip:unknown"


class SlidingWindowRateLimiter:
    """Ventana deslizante en memoria.

    Limitación conocida y declarada: el estado vive en el proceso, así que con
    varias instancias el límite es por instancia, no global. Para el alcance de
    este servicio es suficiente y evita añadir Redis como dependencia que operar.
    Se documenta en el README en lugar de presentarlo como resuelto.
    """

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Registra un intento y devuelve si está dentro del límite."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                return False
            bucket.append(now)

            # Higiene: sin esto el diccionario crece con cada cliente visto.
            if len(self._hits) > 10_000:
                for stale_key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale_key]
            return True

    def retry_after(self) -> int:
        return self._window


_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter(settings: Settings | None = None) -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        resolved = settings or get_settings()
        _limiter = SlidingWindowRateLimiter(
            max_requests=resolved.rate_limit_requests,
            window_seconds=resolved.rate_limit_window_seconds,
        )
    return _limiter


def reset_rate_limiter() -> None:
    """Reinicia el limitador. Solo para pruebas."""
    global _limiter
    _limiter = None


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def authorize(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Valida la credencial y aplica el límite de tasa.

    La comparación es en tiempo constante: comparar con `==` filtra por el tiempo
    de respuesta cuántos caracteres iniciales coinciden, lo que permite descubrir
    la clave carácter a carácter.
    """
    settings = get_settings()
    credential = _extract_bearer(authorization)

    if settings.auth_enabled:
        if credential is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta la credencial Bearer.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not hmac.compare_digest(credential, settings.agent_api_key):
            logger.warning(
                "Credencial rechazada",
                extra={"client": _client_fingerprint(request, None)},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial inválida.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    limiter = get_rate_limiter(settings)
    if not limiter.check(_client_fingerprint(request, credential)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas peticiones. Intenta de nuevo en unos momentos.",
            headers={"Retry-After": str(limiter.retry_after())},
        )
