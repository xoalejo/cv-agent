"""Pruebas de la capa HTTP: contrato, seguridad y manejo de errores.

Se levanta la aplicación real, con su wiring, middleware y manejadores de error,
y solo se sustituye el motor del modelo. Así se valida el contrato que verá la
plataforma sin gastar una llamada al proveedor.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.application.conversation import AnswerProfileQuestion
from src.application.tool_registry import ToolRegistry
from src.config import Settings, get_settings
from src.infrastructure.lexical_search import LexicalProfileSearch
from src.infrastructure.openai_engine import (
    LLMConfigurationError,
    LLMEngineError,
    LLMRateLimitError,
)
from src.infrastructure.profile_data import StaticProfileRepository
from src.interfaces.http.app import create_app
from src.interfaces.http.security import reset_rate_limiter
from tests.conftest import FakeEngine, text_response, tool_response

API_KEY = "clave-de-prueba-suficientemente-larga"
AUTH = {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AGENT_API_KEY", API_KEY)
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-doble-de-prueba")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "30")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "")
    get_settings.cache_clear()
    reset_rate_limiter()
    yield
    get_settings.cache_clear()
    reset_rate_limiter()


def make_client(engine: FakeEngine) -> TestClient:
    """Aplicación real con el motor sustituido por un doble."""
    app = create_app()
    client = TestClient(app)
    client.__enter__()  # dispara el lifespan

    repository = StaticProfileRepository()
    app.state.answer_question = AnswerProfileQuestion(
        engine=engine,
        profile_repository=repository,
        tools=ToolRegistry(repository, LexicalProfileSearch(repository.get())),
    )
    return client


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = FakeEngine([text_response("Tiene 15 años de experiencia.")])
    test_client = make_client(engine)
    yield test_client
    test_client.__exit__(None, None, None)


class TestHealth:
    def test_responde_sin_autenticacion(self, client: TestClient) -> None:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_no_revela_configuracion(self, client: TestClient) -> None:
        body = response_text = client.get("/health").text.lower()

        for secret in ("api_key", "sk-", "openai", "clave"):
            assert secret not in body, f"/health no debe exponer '{secret}'"
        assert response_text


class TestAuthentication:
    def test_sin_credencial_devuelve_401(self, client: TestClient) -> None:
        response = client.post("/responses", json={"input": "hola"})

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_credencial_incorrecta_devuelve_401(self, client: TestClient) -> None:
        response = client.post(
            "/responses",
            json={"input": "hola"},
            headers={"Authorization": "Bearer clave-equivocada"},
        )
        assert response.status_code == 401

    def test_esquema_no_bearer_devuelve_401(self, client: TestClient) -> None:
        response = client.post(
            "/responses",
            json={"input": "hola"},
            headers={"Authorization": f"Basic {API_KEY}"},
        )
        assert response.status_code == 401

    def test_el_error_no_filtra_la_clave(self, client: TestClient) -> None:
        response = client.post(
            "/responses", json={"input": "hola"}, headers={"Authorization": "Bearer x"}
        )
        assert API_KEY not in response.text

    def test_con_credencial_valida_responde(self, client: TestClient) -> None:
        response = client.post("/responses", json={"input": "hola"}, headers=AUTH)
        assert response.status_code == 200


class TestResponsesContract:
    def test_forma_del_objeto_response(self, client: TestClient) -> None:
        body = client.post(
            "/responses", json={"input": "¿Cuántos años de experiencia tiene?"}, headers=AUTH
        ).json()

        assert body["object"] == "response"
        assert body["status"] == "completed"
        assert body["id"].startswith("resp")
        assert isinstance(body["created_at"], int)
        assert body["output_text"] == "Tiene 15 años de experiencia."

        message = body["output"][0]
        assert message["type"] == "message"
        assert message["role"] == "assistant"
        assert message["content"][0]["type"] == "output_text"
        assert message["content"][0]["text"] == "Tiene 15 años de experiencia."

    def test_reporta_uso_de_tokens(self, client: TestClient) -> None:
        usage = client.post("/responses", json={"input": "hola"}, headers=AUTH).json()["usage"]

        assert usage["total_tokens"] == 15

    def test_acepta_input_como_lista_de_items(self, client: TestClient) -> None:
        response = client.post(
            "/responses",
            json={
                "input": [
                    {"role": "user", "content": [{"type": "input_text", "text": "hola"}]}
                ]
            },
            headers=AUTH,
        )
        assert response.status_code == 200

    def test_la_salida_no_incluye_llamadas_a_herramientas(self) -> None:
        """Quien integra el agente no debe tener que ejecutar nada."""
        engine = FakeEngine(
            [tool_response("get_patents"), text_response("Tiene 3 patentes en trámite.")]
        )
        client = make_client(engine)
        try:
            body = client.post("/responses", json={"input": "¿Patentes?"}, headers=AUTH).json()

            tipos = {item["type"] for item in body["output"]}
            assert tipos == {"message"}
            assert body["output_text"] == "Tiene 3 patentes en trámite."
        finally:
            client.__exit__(None, None, None)

    def test_tambien_responde_bajo_el_prefijo_v1(self, client: TestClient) -> None:
        """La URL base puede registrarse con o sin '/v1'."""
        response = client.post("/v1/responses", json={"input": "hola"}, headers=AUTH)
        assert response.status_code == 200


class TestRequestTolerance:
    def test_ignora_parametros_extra(self, client: TestClient) -> None:
        """La plataforma permite adjuntar parámetros extra por petición."""
        response = client.post(
            "/responses",
            json={
                "input": "hola",
                "temperature": 0.7,
                "reasoning": {"effort": "medium"},
                "campo_desconocido": True,
            },
            headers=AUTH,
        )
        assert response.status_code == 200

    def test_ignora_el_modelo_que_manda_el_cliente(self, client: TestClient) -> None:
        """El modelo lo decide el servidor, no quien llama."""
        body = client.post(
            "/responses",
            json={"input": "hola", "model": "modelo-carisimo-inventado"},
            headers=AUTH,
        ).json()

        assert body["model"] == "fake-model"


class TestValidation:
    def test_input_vacio_es_invalido(self, client: TestClient) -> None:
        response = client.post("/responses", json={"input": "   "}, headers=AUTH)

        assert response.status_code == 422
        assert response.json()["error"]["type"] == "invalid_request_error"

    def test_falta_input(self, client: TestClient) -> None:
        assert client.post("/responses", json={}, headers=AUTH).status_code == 422

    def test_historial_demasiado_largo(self, client: TestClient) -> None:
        enorme = [{"role": "user", "content": "hola"} for _ in range(201)]
        response = client.post("/responses", json={"input": enorme}, headers=AUTH)

        assert response.status_code == 422




class TestErrorHandling:
    def test_fallo_del_proveedor_no_filtra_detalles(self) -> None:
        class BrokenEngine:
            def respond(self, **_: object) -> None:
                raise LLMEngineError("connection refused a api.openai.com con key sk-abc123")

        app = create_app()
        client = TestClient(app)
        client.__enter__()
        try:
            repository = StaticProfileRepository()
            app.state.answer_question = AnswerProfileQuestion(
                engine=BrokenEngine(),  # type: ignore[arg-type]
                profile_repository=repository,
                tools=ToolRegistry(repository, LexicalProfileSearch(repository.get())),
            )

            response = client.post("/responses", json={"input": "hola"}, headers=AUTH)

            assert response.status_code == 502
            assert "sk-abc123" not in response.text
            assert "api.openai.com" not in response.text
        finally:
            client.__exit__(None, None, None)

    def test_los_errores_usan_la_forma_del_protocolo(self, client: TestClient) -> None:
        body = client.post("/responses", json={"input": ""}, headers=AUTH).json()

        assert "error" in body
        assert {"message", "type", "code"} <= set(body["error"])


class TestRateLimiting:
    def test_corta_al_superar_el_limite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "3")
        get_settings.cache_clear()
        reset_rate_limiter()

        engine = FakeEngine([text_response("ok") for _ in range(10)])
        client = make_client(engine)
        try:
            codes = [
                client.post("/responses", json={"input": "hola"}, headers=AUTH).status_code
                for _ in range(5)
            ]

            assert codes[:3] == [200, 200, 200]
            assert codes[3:] == [429, 429]
        finally:
            client.__exit__(None, None, None)

    def test_el_429_indica_cuando_reintentar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
        get_settings.cache_clear()
        reset_rate_limiter()

        engine = FakeEngine([text_response("ok") for _ in range(5)])
        client = make_client(engine)
        try:
            client.post("/responses", json={"input": "hola"}, headers=AUTH)
            blocked = client.post("/responses", json={"input": "hola"}, headers=AUTH)

            assert blocked.status_code == 429
            assert "Retry-After" in blocked.headers
        finally:
            client.__exit__(None, None, None)


class TestCors:
    def test_sin_cors_por_defecto(self, client: TestClient) -> None:
        """Integración servidor-a-servidor: nada de orígenes de navegador."""
        response = client.post(
            "/responses",
            json={"input": "hola"},
            headers={**AUTH, "Origin": "https://sitio-cualquiera.com"},
        )

        assert "access-control-allow-origin" not in response.headers


class TestProviderRateLimits:
    """El límite del proveedor es transitorio y debe distinguirse de una avería."""

    @staticmethod
    def _client_with(engine_exception: Exception) -> TestClient:
        class FailingEngine:
            def respond(self, **_: object) -> None:
                raise engine_exception

        app = create_app()
        client = TestClient(app)
        client.__enter__()
        repository = StaticProfileRepository()
        app.state.answer_question = AnswerProfileQuestion(
            engine=FailingEngine(),  # type: ignore[arg-type]
            profile_repository=repository,
            tools=ToolRegistry(repository, LexicalProfileSearch(repository.get())),
        )
        return client

    def test_cuota_del_proveedor_devuelve_429_no_502(self) -> None:
        client = self._client_with(LLMRateLimitError("rate limit exceeded", retry_after=17))
        try:
            response = client.post("/responses", json={"input": "hola"}, headers=AUTH)

            assert response.status_code == 429
            assert response.headers["Retry-After"] == "17"
        finally:
            client.__exit__(None, None, None)

    def test_el_429_del_proveedor_no_filtra_detalles(self) -> None:
        client = self._client_with(
            LLMRateLimitError("org-abc123 exceeded 200000 TPM on gpt-4.1-mini")
        )
        try:
            response = client.post("/responses", json={"input": "hola"}, headers=AUTH)

            assert "org-abc123" not in response.text
            assert "TPM" not in response.text
        finally:
            client.__exit__(None, None, None)

    def test_configuracion_invalida_devuelve_503(self) -> None:
        """Credencial o modelo mal configurados: reintentar no lo arregla."""
        client = self._client_with(LLMConfigurationError("model not found"))
        try:
            response = client.post("/responses", json={"input": "hola"}, headers=AUTH)

            assert response.status_code == 503
            assert "model not found" not in response.text
        finally:
            client.__exit__(None, None, None)

    def test_el_limite_por_defecto_cubre_la_suite_de_evals(self) -> None:
        """La suite consume ~26 peticiones; el límite no debe estorbarla."""
        from src.config import get_settings as settings_factory

        settings_factory.cache_clear()
        assert Settings().rate_limit_requests >= 30


class TestAgentCard:
    """Tarjeta A2A: descubrimiento automático sin exponer nada sensible."""

    def test_se_publica_sin_autenticacion(self, client: TestClient) -> None:
        """Un mecanismo de descubrimiento que exigiera credencial sería inútil."""
        response = client.get("/.well-known/agent-card.json")

        assert response.status_code == 200

    def test_declara_los_datos_del_agente(self, client: TestClient) -> None:
        card = client.get("/.well-known/agent-card.json").json()

        assert "Oscar Alejo" in card["name"]
        assert card["version"]
        assert card["skills"][0]["examples"]

    def test_declara_streaming_porque_lo_implementa(self, client: TestClient) -> None:
        """La tarjeta debe reflejar lo que el servicio hace, ni más ni menos."""
        card = client.get("/.well-known/agent-card.json").json()

        assert card["capabilities"]["streaming"] is True

    def test_declara_el_endpoint_de_open_responses(self, client: TestClient) -> None:
        card = client.get("/.well-known/agent-card.json").json()

        assert card["openResponses"]["endpoint"].endswith("/responses")
        assert card["openResponses"]["conversationState"] == "replay_transcript"

    def test_las_interfaces_usan_la_forma_de_la_version_1(
        self, client: TestClient
    ) -> None:
        """En v1.0 cada entrada lleva `protocolBinding`, no `transport`.

        Mezclar el nombre de v0.3 dentro de la estructura de v1.0 hace que un
        validador rechace la tarjeta completa.
        """
        card = client.get("/.well-known/agent-card.json").json()
        interfaces = card["supportedInterfaces"]

        assert interfaces, "debe declararse al menos una interfaz"
        for interfaz in interfaces:
            assert "protocolBinding" in interfaz
            assert "transport" not in interfaz
            assert interfaz["url"]

    def test_la_version_del_protocolo_coincide_con_los_campos(
        self, client: TestClient
    ) -> None:
        card = client.get("/.well-known/agent-card.json").json()

        assert card["protocolVersion"].startswith("1.")

    def test_no_expone_credenciales(self, client: TestClient) -> None:
        """Declara que espera un Bearer, nunca cuál es."""
        cuerpo = client.get("/.well-known/agent-card.json").text

        assert API_KEY not in cuerpo
        assert "sk-" not in cuerpo
        assert card_declara_bearer(cuerpo)


def card_declara_bearer(cuerpo: str) -> bool:
    return '"scheme": "bearer"' in cuerpo or '"scheme":"bearer"' in cuerpo


def _eventos_sse(cuerpo: str) -> list[dict]:
    """Extrae los objetos JSON de un cuerpo SSE, sin el terminador."""
    import json as _json

    eventos = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("data: "):
            continue
        carga = linea[len("data: ") :].strip()
        if carga == "[DONE]":
            continue
        eventos.append(_json.loads(carga))
    return eventos


class TestStreaming:
    """Contrato SSE de Open Responses."""

    def test_content_type_y_terminador(self, client: TestClient) -> None:
        r = client.post("/responses", json={"input": "hola", "stream": True}, headers=AUTH)

        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.text.rstrip().endswith("data: [DONE]")

    def test_secuencia_de_eventos_del_protocolo(self, client: TestClient) -> None:
        eventos = _eventos_sse(
            client.post(
                "/responses", json={"input": "hola", "stream": True}, headers=AUTH
            ).text
        )
        tipos = [e["type"] for e in eventos]

        assert tipos[0] == "response.created"
        assert tipos[1] == "response.in_progress"
        assert "response.output_item.added" in tipos
        assert "response.content_part.added" in tipos
        assert "response.output_text.delta" in tipos
        assert "response.output_text.done" in tipos
        assert "response.content_part.done" in tipos
        assert "response.output_item.done" in tipos
        assert tipos[-1] == "response.completed"

    def test_sequence_number_es_correlativo(self, client: TestClient) -> None:
        eventos = _eventos_sse(
            client.post(
                "/responses", json={"input": "hola", "stream": True}, headers=AUTH
            ).text
        )

        assert [e["sequence_number"] for e in eventos] == list(range(len(eventos)))

    def test_los_deltas_reconstruyen_el_texto_final(self, client: TestClient) -> None:
        eventos = _eventos_sse(
            client.post(
                "/responses", json={"input": "hola", "stream": True}, headers=AUTH
            ).text
        )

        deltas = "".join(
            e["delta"] for e in eventos if e["type"] == "response.output_text.delta"
        )
        completado = next(e for e in eventos if e["type"] == "response.completed")

        assert deltas == "Tiene 15 años de experiencia."
        assert completado["response"]["output_text"] == deltas

    def test_el_id_es_estable_durante_todo_el_flujo(self, client: TestClient) -> None:
        """Un cliente que correlacione por id se rompería si cambiara a mitad."""
        eventos = _eventos_sse(
            client.post(
                "/responses", json={"input": "hola", "stream": True}, headers=AUTH
            ).text
        )
        ids = {e["response"]["id"] for e in eventos if "response" in e}

        assert len(ids) == 1

    def test_requiere_credencial(self, client: TestClient) -> None:
        r = client.post("/responses", json={"input": "hola", "stream": True})

        assert r.status_code == 401

    def test_el_guarda_de_pii_tambien_aplica_en_streaming(self) -> None:
        """Sin esto el streaming sería un agujero en la política de divulgación."""
        engine = FakeEngine([text_response("Su número es +52 555 123 4567, anótalo.")])
        client = make_client(engine)
        try:
            cuerpo = client.post(
                "/responses", json={"input": "su tel?", "stream": True}, headers=AUTH
            ).text
            eventos = _eventos_sse(cuerpo)
            deltas = "".join(
                e["delta"] for e in eventos if e["type"] == "response.output_text.delta"
            )

            # Ni el texto reconstruido ni ningún fragmento suelto contienen dígitos.
            assert "4567" not in deltas
            assert "555" not in deltas
            assert "4567" not in cuerpo
            assert "no divulgado" in deltas
        finally:
            client.__exit__(None, None, None)

    def test_el_ciclo_de_herramientas_funciona_en_streaming(self) -> None:
        engine = FakeEngine(
            [tool_response("get_patents"), text_response("Tiene 3 patentes.")]
        )
        client = make_client(engine)
        try:
            eventos = _eventos_sse(
                client.post(
                    "/responses", json={"input": "¿patentes?", "stream": True}, headers=AUTH
                ).text
            )
            deltas = "".join(
                e["delta"] for e in eventos if e["type"] == "response.output_text.delta"
            )

            assert deltas == "Tiene 3 patentes."
            assert eventos[-1]["type"] == "response.completed"
        finally:
            client.__exit__(None, None, None)


class TestAgentCardDiscovery:
    """Un documento de descubrimiento tiene que poder descubrirse."""

    def test_responde_a_head(self, client: TestClient) -> None:
        """Hay clientes que comprueban existencia antes de descargar."""
        assert client.head("/.well-known/agent-card.json").status_code == 200

    def test_responde_a_options(self, client: TestClient) -> None:
        assert client.options("/.well-known/agent-card.json").status_code == 200

    def test_permite_lectura_desde_navegador(self, client: TestClient) -> None:
        """Sin CORS, un cliente web no puede leer la tarjeta."""
        r = client.get("/.well-known/agent-card.json")

        assert r.headers["access-control-allow-origin"] == "*"

    def test_el_endpoint_de_conversacion_no_abre_cors(self, client: TestClient) -> None:
        """La apertura es solo para la tarjeta, no para el resto del servicio."""
        r = client.post(
            "/responses",
            json={"input": "hola"},
            headers={**AUTH, "Origin": "https://sitio-cualquiera.com"},
        )

        assert "access-control-allow-origin" not in r.headers

    def test_se_sirve_como_json(self, client: TestClient) -> None:
        r = client.get("/.well-known/agent-card.json")

        assert r.headers["content-type"].startswith("application/json")
