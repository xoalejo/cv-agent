"""Composition root: el único lugar donde se conocen las implementaciones.

Aquí, y solo aquí, se decide que el motor es OpenAI, que el perfil vive en código
y que la búsqueda es léxica. El resto del sistema conversa con puertos. Cambiar
cualquiera de esas piezas es cambiar estas líneas.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.application.conversation import AnswerProfileQuestion
from src.application.tool_registry import ToolRegistry
from src.config import Settings, get_settings
from src.infrastructure.lexical_search import LexicalProfileSearch
from src.infrastructure.openai_engine import OpenAIResponsesEngine
from src.infrastructure.profile_data import StaticProfileRepository
from src.interfaces.http.routes import router
from src.interfaces.http.schemas import ErrorDetail, ErrorReply
from src.interfaces.http.security import advertir_si_es_inefectivo

logger = logging.getLogger(__name__)


def build_use_case(settings: Settings) -> AnswerProfileQuestion:
    """Ensambla el caso de uso con sus adaptadores concretos."""
    profile_repository = StaticProfileRepository()
    search = LexicalProfileSearch(profile_repository.get())
    engine = OpenAIResponsesEngine(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout=settings.request_timeout_seconds,
        reasoning_effort=settings.reasoning_effort,
    )
    return AnswerProfileQuestion(
        engine=engine,
        profile_repository=profile_repository,
        tools=ToolRegistry(profile_repository, search),
        max_tool_iterations=settings.max_tool_iterations,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not settings.auth_enabled:
        # Arrancar sin autenticación solo tiene sentido en desarrollo. Si pasa en
        # otro entorno, que quede constancia ruidosa en los logs.
        logger.warning("Servicio sin autenticación: define AGENT_API_KEY antes de exponerlo.")

    advertir_si_es_inefectivo(settings)

    try:
        app.state.answer_question = build_use_case(settings)
        logger.info("Agente listo (modelo=%s)", settings.openai_model)
    except ValueError as exc:
        # Sin clave del proveedor el servicio arranca igualmente para que /health
        # responda y el hosting no entre en bucle de reinicios; /responses
        # devolverá 503 hasta que se configure.
        app.state.answer_question = None
        logger.error("El agente no pudo inicializarse: %s", exc)

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    # La documentación interactiva y el esquema OpenAPI describen rutas, modelos
    # y validaciones. No contienen secretos, pero publicarlos regala trabajo de
    # reconocimiento sobre una API que exige credencial. Se sirven solo fuera de
    # producción, donde son útiles para desarrollar.
    en_produccion = settings.environment.lower() == "production"

    app = FastAPI(
        title="CV Agent",
        description=(
            "Agente conversacional sobre la trayectoria profesional de Oscar Alejo, "
            "compatible con el contrato Open Responses."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if en_produccion else "/docs",
        redoc_url=None if en_produccion else "/redoc",
        openapi_url=None if en_produccion else "/openapi.json",
    )

    # Integración servidor-a-servidor: sin orígenes de navegador salvo que se
    # declaren explícitamente. Nunca "*".
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["POST", "GET"],
            allow_headers=["Authorization", "Content-Type"],
        )

    # Política de versionado.
    #
    # `/v1` es la ruta canónica y designa el contrato al que este servicio se
    # compromete: la forma del objeto `Response`, los eventos del flujo SSE y los
    # códigos de error documentados. Un cambio incompatible viviría en `/v2`, y
    # `/v1` seguiría respondiendo igual.
    #
    # Eso importa porque quien consume este endpoint es una plataforma externa
    # que registra la URL una vez: no hay forma de pedirle que actualice si el
    # contrato cambia bajo sus pies.
    #
    # La raíz se mantiene como alias de conveniencia y sigue a la última versión.
    # Sirve para pruebas rápidas con curl; una integración debería registrar
    # `/v1`.
    app.include_router(router, prefix="/v1")
    app.include_router(router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorReply(
                error=ErrorDetail(
                    message=str(exc.detail),
                    type="invalid_request_error" if exc.status_code < 500 else "api_error",
                    code=str(exc.status_code),
                )
            ).model_dump(),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = first.get("msg", "Petición inválida.")
        return JSONResponse(
            status_code=422,
            content=ErrorReply(
                error=ErrorDetail(
                    message=f"{field}: {message}" if field else message,
                    type="invalid_request_error",
                    code="422",
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Nada de trazas ni mensajes internos hacia el cliente.
        logger.exception("Error no controlado", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorReply(
                error=ErrorDetail(
                    message="Error interno del servicio.",
                    type="api_error",
                    code="500",
                )
            ).model_dump(),
        )

    return app


app = create_app()
