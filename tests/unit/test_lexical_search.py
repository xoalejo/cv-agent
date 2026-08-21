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

    def test_la_consulta_en_espanol_encuentra_el_material(
        self, search: LexicalProfileSearch
    ) -> None:
        results = search.search("trazabilidad industrial", limit=3)

        assert results
        assert any(r.context == "Arbomex S.A. de C.V." for r in results)

    def test_los_terminos_tecnicos_funcionan_en_cualquier_idioma(
        self, search: LexicalProfileSearch
    ) -> None:
        """Los nombres propios de tecnología no se traducen, así que coinciden igual."""
        for termino in ("Databricks", "Kubernetes", "Pinecone", "RAG"):
            assert search.search(termino, limit=1), f"{termino} debería encontrarse"

    def test_el_corpus_esta_en_espanol(self, search: LexicalProfileSearch) -> None:
        """El prompt instruye consultar en español; esta prueba fija esa premisa.

        Una consulta con vocabulario únicamente en inglés no recupera el
        fragmento equivalente: es la contrapartida conocida de mantener una sola
        versión del contenido, y por eso el modelo traduce la consulta antes de
        buscar.
        """
        assert search.search("archivos mensuales", limit=1)
        assert search.search("monthly files reporting", limit=1) == []

    def test_tolera_acentos_y_mayusculas(self, search: LexicalProfileSearch) -> None:
        con_acento = search.search("automatización", limit=3)
        sin_acento = search.search("AUTOMATIZACION", limit=3)

        assert con_acento
        assert {r.text for r in con_acento} == {r.text for r in sin_acento}

    def test_encuentra_patentes(self, search: LexicalProfileSearch) -> None:
        results = search.search("patentes blockchain biométrica", limit=3)
        assert any(r.section is Section.PATENTS for r in results)


class TestProvenance:
    def test_cada_fragmento_trae_su_procedencia(self, search: LexicalProfileSearch) -> None:
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

    def test_tema_ausente_del_cv_no_devuelve_nada(self, search: LexicalProfileSearch) -> None:
        # El CV no menciona nada de repostería.
        assert search.search("repostería francesa croissants") == []

    def test_respeta_el_limite(self, search: LexicalProfileSearch) -> None:
        assert len(search.search("datos", limit=2)) <= 2

    def test_el_orden_es_estable(self, search: LexicalProfileSearch) -> None:
        primera = [f.text for f in search.search("Python automatización", limit=5)]
        segunda = [f.text for f in search.search("Python automatización", limit=5)]
        assert primera == segunda
