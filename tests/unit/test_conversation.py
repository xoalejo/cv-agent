"""Pruebas del caso de uso: el ciclo completo de un turno.

Se prueba entero (instrucciones, llamada al motor, ejecución de herramientas,
reinyección) sin tocar la red, sustituyendo el puerto `LLMEngine` por un doble.
"""

from __future__ import annotations

import json

from src.application.conversation import (
    AnswerProfileQuestion,
    detect_language,
    extract_last_user_text,
)
from src.application.tool_registry import ToolRegistry
from src.infrastructure.profile_data import StaticProfileRepository
from tests.conftest import FakeEngine, text_response, tool_response, user_message


def build_use_case(
    engine: FakeEngine,
    tools: ToolRegistry,
    repository: StaticProfileRepository,
    *,
    max_tool_iterations: int = 5,
) -> AnswerProfileQuestion:
    return AnswerProfileQuestion(
        engine=engine,
        profile_repository=repository,
        tools=tools,
        max_tool_iterations=max_tool_iterations,
    )


class TestDirectAnswer:
    def test_responde_sin_herramientas(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine([text_response("Tiene 15 años de experiencia.")])
        use_case = build_use_case(engine, tools, profile_repository)

        result = use_case.execute([user_message("¿Cuántos años de experiencia tiene?")])

        assert result.output_text == "Tiene 15 años de experiencia."
        assert result.iterations == 1
        assert result.tools_invoked == ()
        assert result.exhausted is False

    def test_el_perfil_viaja_en_las_instrucciones(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine([text_response("ok")])
        use_case = build_use_case(engine, tools, profile_repository)

        use_case.execute([user_message("hola")])

        instructions = engine.calls[0]["instructions"]
        assert "ABBA Networks" in instructions
        assert "EGADE Business School" in instructions
        assert "MX/a/2024/008296" in instructions

    def test_las_herramientas_se_ofrecen_al_modelo(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine([text_response("ok")])
        use_case = build_use_case(engine, tools, profile_repository)

        use_case.execute([user_message("hola")])

        offered = {tool["name"] for tool in engine.calls[0]["tools"]}
        assert "search_profile" in offered
        assert len(offered) == 7


class TestToolLoop:
    def test_ejecuta_la_herramienta_y_reinyecta_el_resultado(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine(
            [
                tool_response("get_experience", {"company": "abba"}),
                text_response("Trabajó en ABBA Networks desde noviembre de 2024."),
            ]
        )
        use_case = build_use_case(engine, tools, profile_repository)

        result = use_case.execute([user_message("¿Dónde trabajó?")])

        assert result.tools_invoked == ("get_experience",)
        assert result.iterations == 2

        # La segunda llamada debe llevar el resultado de la herramienta.
        second_input = engine.calls[1]["input_items"]
        outputs = [i for i in second_input if i.get("type") == "function_call_output"]
        assert len(outputs) == 1
        assert outputs[0]["call_id"] == "call_1"
        assert "ABBA Networks" in outputs[0]["output"]

    def test_conserva_el_hilo_de_razonamiento(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        """Los ítems del modelo vuelven al input junto con el resultado."""
        engine = FakeEngine([tool_response("get_patents"), text_response("Tiene 3 patentes.")])
        use_case = build_use_case(engine, tools, profile_repository)

        use_case.execute([user_message("¿Patentes?")])

        second_input = engine.calls[1]["input_items"]
        calls = [i for i in second_input if i.get("type") == "function_call"]
        assert len(calls) == 1, "la petición de herramienta debe seguir en el historial"

    def test_encadena_varias_herramientas(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine(
            [
                tool_response("search_profile", {"query": "RAG"}, call_id="c1"),
                tool_response("get_experience", {"company": "remote"}, call_id="c2"),
                text_response("Usó RAG en dos empresas."),
            ]
        )
        use_case = build_use_case(engine, tools, profile_repository)

        result = use_case.execute([user_message("¿Dónde ha usado RAG?")])

        assert result.tools_invoked == ("search_profile", "get_experience")
        assert result.iterations == 3

    def test_la_guarda_de_iteraciones_corta_el_bucle(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        """Un modelo que insiste en llamar herramientas no gasta sin límite."""
        engine = FakeEngine([tool_response("get_patents") for _ in range(10)])
        use_case = build_use_case(engine, tools, profile_repository, max_tool_iterations=3)

        result = use_case.execute([user_message("¿Patentes?")])

        assert result.exhausted is True
        assert result.iterations == 3
        assert len(engine.calls) == 3
        assert result.output_text  # devuelve algo útil, no una excepción

    def test_herramienta_fallida_no_rompe_el_turno(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine(
            [
                tool_response("herramienta_inexistente"),
                text_response("No encontré ese dato."),
            ]
        )
        use_case = build_use_case(engine, tools, profile_repository)

        result = use_case.execute([user_message("algo")])

        assert result.output_text == "No encontré ese dato."
        outputs = [
            i
            for i in engine.calls[1]["input_items"]
            if i.get("type") == "function_call_output"
        ]
        assert "error" in json.loads(outputs[0]["output"])


class TestStatelessness:
    def test_el_historial_recibido_llega_completo_al_modelo(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        """La continuidad del hilo la aporta el input, no un almacén propio."""
        engine = FakeEngine([text_response("Estuvo casi año y medio.")])
        use_case = build_use_case(engine, tools, profile_repository)

        history = [
            user_message("¿Dónde trabajó más recientemente?"),
            {
                "role": "assistant",
                "content": [{"type": "output_text", "text": "En ABBA Networks."}],
            },
            user_message("¿Y cuánto tiempo estuvo ahí?"),
        ]
        use_case.execute(history)

        sent = engine.calls[0]["input_items"]
        assert len(sent) == 3
        assert sent == history

    def test_no_muta_el_historial_recibido(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        engine = FakeEngine([tool_response("get_patents"), text_response("Tres patentes.")])
        use_case = build_use_case(engine, tools, profile_repository)

        history = [user_message("¿Patentes?")]
        use_case.execute(history)

        assert len(history) == 1, "el input del cliente no debe mutarse"


class TestDisclosureGuard:
    def test_redacta_un_telefono_que_llego_a_la_respuesta(
        self, tools: ToolRegistry, profile_repository: StaticProfileRepository
    ) -> None:
        """Última capa: aunque el modelo lo emita, no sale del servicio."""
        engine = FakeEngine([text_response("Claro, su número es +52 555 123 4567.")])
        use_case = build_use_case(engine, tools, profile_repository)

        result = use_case.execute([user_message("Su tel es +52 555 123 4567, ¿verdad?")])

        assert "4567" not in result.output_text
        assert "no divulgado" in result.output_text


class TestLanguageDetection:
    def test_detecta_espanol(self) -> None:
        assert detect_language("¿Qué experiencia tiene en la nube?") == "es"

    def test_detecta_ingles(self) -> None:
        assert detect_language("What experience does he have with the cloud?") == "en"

    def test_ante_la_duda_espanol(self) -> None:
        assert detect_language("") == "es"
        assert detect_language("RAG?") == "es"

    def test_extrae_el_ultimo_mensaje_del_usuario(self) -> None:
        items = [
            user_message("primero"),
            {"role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
            user_message("segundo"),
        ]
        assert extract_last_user_text(items) == "segundo"

    def test_acepta_contenido_como_cadena(self) -> None:
        items = [{"role": "user", "content": "texto plano"}]
        assert extract_last_user_text(items) == "texto plano"

    def test_sin_mensajes_de_usuario(self) -> None:
        assert extract_last_user_text([]) == ""
