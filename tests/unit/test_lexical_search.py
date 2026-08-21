"""Pruebas de la búsqueda con procedencia.

La búsqueda es el mecanismo de grounding: lo que importa no es solo que encuentre
el fragmento correcto, sino que devuelva de dónde salió.
"""

from __future__ import annotations

from src.domain.fragment import Section
from src.infrastructure.lexical_search import LexicalProfileSearch


class TestRecall:
    def test_encuentra_rag_en_varias_empresas(self, search: LexicalProfileSearch) -> None:
        results = search.search("RAG", limit=5)

        assert results, "RAG aparece en el CV y debería encontrarse"
        companies = {r.context for r in results}
        # RAG aparece tanto en ABBA Networks como en Remote Data Consulting.
        assert len([c for c in companies if c]) >= 2

    def test_consulta_en_ingles_encuentra_contenido_en_espanol(
        self, search: LexicalProfileSearch
    ) -> None:
        spanish = search.search("trazabilidad industrial", limit=3)
        english = search.search("industrial traceability", limit=3)

        assert spanish and english
        # El índice cubre ambos idiomas, así que ambas consultas llegan al mismo
        # material: la de Arbomex.
        assert any(r.context == "Arbomex S.A. de C.V." for r in spanish)
        assert any(r.context == "Arbomex S.A. de C.V." for r in english)

    def test_devuelve_el_texto_en_el_idioma_pedido(
        self, search: LexicalProfileSearch
    ) -> None:
        spanish = search.search("Databricks", language="es", limit=1)
        english = search.search("Databricks", language="en", limit=1)

        assert spanish and english
        assert "archivos mensuales" in spanish[0].text
        assert "files monthly" in english[0].text

    def test_tolera_acentos_y_mayusculas(self, search: LexicalProfileSearch) -> None:
        con_acento = search.search("automatización", limit=3)
        sin_acento = search.search("AUTOMATIZACION", limit=3)

        assert con_acento
        assert {r.text for r in con_acento} == {r.text for r in sin_acento}

    def test_encuentra_patentes(self, search: LexicalProfileSearch) -> None:
        results = search.search("patentes blockchain biométrica", limit=3)
        assert any(r.section is Section.PATENTS for r in results)


class TestProvenance:
    def test_cada_fragmento_trae_su_procedencia(
        self, search: LexicalProfileSearch
    ) -> None:
        results = search.search("Kubernetes", limit=3)

        assert results
        for fragment in results:
            assert fragment.citation
            assert fragment.section.value in fragment.citation

    def test_la_cita_incluye_la_empresa_cuando_aplica(
        self, search: LexicalProfileSearch
    ) -> None:
        results = search.search("SAP 140 máquinas", limit=1)

        assert results
        assert results[0].citation == "experiencia · Arbomex S.A. de C.V."


class TestEdgeCases:
    def test_consulta_vacia_no_devuelve_nada(self, search: LexicalProfileSearch) -> None:
        assert search.search("") == []
        assert search.search("   ") == []

    def test_consulta_solo_de_palabras_vacias_no_devuelve_nada(
        self, search: LexicalProfileSearch
    ) -> None:
        assert search.search("de la que con") == []

    def test_tema_ausente_del_cv_no_devuelve_nada(
        self, search: LexicalProfileSearch
    ) -> None:
        # El CV no menciona nada de repostería.
        assert search.search("repostería francesa croissants") == []

    def test_respeta_el_limite(self, search: LexicalProfileSearch) -> None:
        assert len(search.search("datos", limit=2)) <= 2

    def test_el_orden_es_estable(self, search: LexicalProfileSearch) -> None:
        primera = [f.text for f in search.search("Python automatización", limit=5)]
        segunda = [f.text for f in search.search("Python automatización", limit=5)]
        assert primera == segunda
