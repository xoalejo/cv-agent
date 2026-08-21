"""Pruebas del registro de herramientas.

Dos cosas importan aquí: que cada herramienta devuelva los datos correctos, y que
un mal argumento se convierta en dato ("error") en lugar de en excepción, para que
el modelo pueda corregir y reintentar sin tumbar la conversación.
"""

from __future__ import annotations

import json

from src.application.tool_registry import TOOL_DEFINITIONS, ToolRegistry


class TestDefinitions:
    def test_expone_las_siete_herramientas(self) -> None:
        names = {definition["name"] for definition in TOOL_DEFINITIONS}
        assert names == {
            "search_profile",
            "get_experience",
            "get_projects",
            "get_certifications",
            "get_patents",
            "get_tech_stack",
            "get_contact_info",
        }

    def test_toda_definicion_tiene_forma_valida(self) -> None:
        for definition in TOOL_DEFINITIONS:
            assert definition["type"] == "function"
            assert definition["description"].strip()
            assert definition["parameters"]["type"] == "object"

    def test_ninguna_herramienta_sale_a_la_red(self) -> None:
        """El registro no expone herramientas con fuentes externas.

        Es lo que garantiza que ningún dato no confiable entre al contexto.
        """
        names = {definition["name"] for definition in TOOL_DEFINITIONS}
        assert not {n for n in names if "github" in n or "web" in n or "search_web" in n}


class TestExecution:
    def test_experiencia_completa(self, tools: ToolRegistry) -> None:
        payload = tools.execute("get_experience", "{}")
        result = payload["result"]

        assert len(result) == 3
        assert {e["company"] for e in result} == {
            "ABBA Networks S.A.P.I. de C.V.",
            "Remote Data Consulting",
            "Arbomex S.A. de C.V.",
        }

    def test_experiencia_por_empresa_parcial(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_experience", json.dumps({"company": "abba"}))["result"]

        assert result["company"] == "ABBA Networks S.A.P.I. de C.V."
        assert result["period"] == "Nov 2024 – Abr 2026"
        assert len(result["achievements"]) == 7

    def test_las_herramientas_devuelven_el_contenido_en_espanol(
        self, tools: ToolRegistry
    ) -> None:
        """El CV es la fuente canónica; traducir es tarea del modelo al responder."""
        result = tools.execute("get_experience", json.dumps({"company": "arbomex"}))[
            "result"
        ]
        assert result["role"] == "Ingeniero de Proyectos en Automatización"

    def test_ningun_parametro_de_idioma_en_las_definiciones(self) -> None:
        """Sin doble versión del contenido, elegir idioma dejó de tener sentido."""
        for definition in TOOL_DEFINITIONS:
            assert "language" not in definition["parameters"].get("properties", {})

    def test_empresa_inexistente_devuelve_error_util(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_experience", json.dumps({"company": "Google"}))["result"]

        assert "error" in result
        # El error incluye las opciones válidas para que el modelo se corrija.
        assert len(result["available"]) == 3

    def test_patentes(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_patents", "{}")["result"]

        assert len(result["patents"]) == 3
        assert {p["file_number"] for p in result["patents"]} == {
            "MX/a/2024/008296",
            "MX/a/2024/016163",
            "MX/a/2024/016162",
        }

    def test_certificaciones(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_certifications", "{}")["result"]
        names = {c["name"] for c in result}

        assert "Certified ScrumMaster® (CSM)" in names
        assert len(result) == 4

    def test_stack_por_categoria(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_tech_stack", json.dumps({"category": "cloud"}))["result"]

        assert "Docker" in " ".join(result["skills"])
        assert "GCP" in result["skills"]

    def test_proyectos(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_projects", "{}")["result"]

        assert len(result) == 1
        assert "Multi-Agente" in result[0]["name"]

    def test_busqueda_devuelve_procedencia(self, tools: ToolRegistry) -> None:
        result = tools.execute("search_profile", json.dumps({"query": "Pinecone"}))["result"]

        assert result["matches"]
        for match in result["matches"]:
            assert match["source"]

    def test_busqueda_sin_coincidencias_lo_dice(self, tools: ToolRegistry) -> None:
        result = tools.execute(
            "search_profile", json.dumps({"query": "repostería francesa"})
        )["result"]

        assert result["matches"] == []
        assert "no cubre" in result["note"].lower()


class TestContactPolicy:
    def test_contacto_solo_devuelve_canales_permitidos(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_contact_info", "{}")["result"]
        kinds = {channel["kind"] for channel in result["channels"]}

        assert kinds == {"email", "linkedin", "github"}
        assert "phone" not in kinds

    def test_ninguna_herramienta_puede_devolver_un_telefono(
        self, tools: ToolRegistry
    ) -> None:
        """Barrido sobre todas las herramientas: el dato no existe en el sistema."""
        from src.domain.policies import contains_contact_data

        payloads = [
            tools.execute("get_experience", "{}"),
            tools.execute("get_projects", "{}"),
            tools.execute("get_certifications", "{}"),
            tools.execute("get_patents", "{}"),
            tools.execute("get_tech_stack", "{}"),
            tools.execute("get_contact_info", "{}"),
            tools.execute("search_profile", json.dumps({"query": "contacto teléfono"})),
        ]

        for payload in payloads:
            serialized = json.dumps(payload, ensure_ascii=False)
            assert not contains_contact_data(serialized)


class TestErrorHandling:
    def test_herramienta_inexistente(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_salary", "{}")
        assert "error" in result

    def test_json_invalido_no_lanza(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_experience", "{esto no es json}")
        assert "error" in result

    def test_argumentos_no_objeto(self, tools: ToolRegistry) -> None:
        result = tools.execute("get_experience", "[1, 2, 3]")
        assert "error" in result

    def test_argumentos_vacios_equivalen_a_sin_argumentos(
        self, tools: ToolRegistry
    ) -> None:
        assert "result" in tools.execute("get_certifications", "")

    def test_toda_salida_es_serializable(self, tools: ToolRegistry) -> None:
        for name in (
            "get_experience",
            "get_projects",
            "get_certifications",
            "get_patents",
            "get_tech_stack",
            "get_contact_info",
        ):
            json.dumps(tools.execute(name, "{}"), ensure_ascii=False)
