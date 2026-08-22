"""Pruebas de la política de divulgación.

Es la capa que convierte "no reveles el teléfono" en una propiedad del sistema en
lugar de una esperanza sobre el comportamiento del modelo.
"""

from __future__ import annotations

import pytest

from src.domain.policies import (
    ALLOWED_CONTACT_KINDS,
    allowed_contact_channels,
    contains_contact_data,
    redact_contact_data,
)
from src.domain.profile import ContactChannel, Profile


class TestPhoneDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "Su teléfono es +52 555 123 4567",
            "Puedes llamarlo al +525551234567",
            "cel: 555-123-4567",
            "whatsapp 5551234567",
            "Teléfono: 555 123 4567",
            "Contacto directo +52 (555) 123 4567",
        ],
    )
    def test_detecta_formas_de_telefono(self, text: str) -> None:
        assert contains_contact_data(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            # Expedientes de patente: la barra impide que se lean como teléfono.
            "Expediente IMPI MX/a/2024/008296",
            "MX/a/2024/016163 y MX/a/2024/016162",
            # Métricas reales del CV que no deben dispararse.
            "Procesó 17,000+ archivos mensuales",
            "Interconectó más de 140 máquinas",
            "Redujo la pérdida de material 60% en 10 líneas",
            "MBA cursado entre 2020 y 2022",
            "Alcanzó 80% de precisión con 17 variables y 3 componentes",
            "Norma IATF 16949",
            "Contacto: osc.09@hotmail.com",
        ],
    )
    def test_no_produce_falsos_positivos(self, text: str) -> None:
        assert contains_contact_data(text) is False

    def test_redaccion_sustituye_y_conserva_el_resto(self) -> None:
        original = "Puedes escribirle a osc.09@hotmail.com o llamarlo al +52 555 123 4567."
        redacted = redact_contact_data(original, "es")

        assert "4567" not in redacted
        assert "555" not in redacted
        assert "osc.09@hotmail.com" in redacted
        assert "[dato de contacto no divulgado]" in redacted

    def test_redaccion_respeta_el_idioma(self) -> None:
        redacted = redact_contact_data("Call +52 555 123 4567", "en")
        assert "[contact detail not disclosed]" in redacted

    def test_texto_limpio_no_se_altera(self) -> None:
        original = "Tiene 15 años de experiencia y un MBA por EGADE."
        assert redact_contact_data(original, "es") == original


class TestContactChannels:
    def test_filtra_canales_no_permitidos(self) -> None:
        channels = (
            ContactChannel(kind="email", value="a@b.com"),
            ContactChannel(kind="phone", value="+52 555 123 4567"),
            ContactChannel(kind="home_address", value="Calle Falsa 123"),
            ContactChannel(kind="linkedin", value="linkedin.com/in/x"),
        )

        allowed = allowed_contact_channels(channels)
        kinds = {channel.kind for channel in allowed}

        assert kinds == {"email", "linkedin"}
        assert "phone" not in kinds

    def test_la_politica_declara_los_canales_publicables(self) -> None:
        assert frozenset({"email", "linkedin", "github"}) == ALLOWED_CONTACT_KINDS


class TestProfileDataHygiene:
    """El perfil cargado no debe contener el dato que la política protege."""

    def test_el_perfil_no_registra_telefono(self, profile: Profile) -> None:
        kinds = {channel.kind for channel in profile.contact_channels}
        assert "phone" not in kinds

    def test_ningun_texto_del_perfil_parece_telefono(self, profile: Profile) -> None:
        blobs: list[str] = [profile.summary, profile.headline]
        for experience in profile.experiences:
            blobs.extend(experience.achievements)
        for education in profile.education:
            blobs.append(education.degree)
        for channel in profile.contact_channels:
            blobs.append(channel.value)

        offenders = [blob for blob in blobs if contains_contact_data(blob)]
        assert offenders == []


class TestStreamingDisclosureGuard:
    """El guarda que hace segura la emisión por fragmentos.

    Lo que se emite no se puede retirar, así que la propiedad a garantizar es que
    ningún dígito con forma de teléfono salga, ni siquiera troceado entre varios
    fragmentos.
    """

    @staticmethod
    def _emitir(trozos: list[str], idioma: str = "es") -> list[str]:
        from src.domain.streaming_guard import StreamingDisclosureGuard

        guard = StreamingDisclosureGuard(idioma)  # type: ignore[arg-type]
        salida = [guard.feed(t) for t in trozos]
        salida.append(guard.flush())
        return salida

    def test_ningun_fragmento_contiene_digitos_del_telefono(self) -> None:
        partes = self._emitir(["Su número es ", "+52 5", "55 12", "3 45", "67."])

        for parte in partes:
            assert "4567" not in parte
            assert "5551" not in parte

    def test_el_texto_final_queda_redactado(self) -> None:
        completo = "".join(self._emitir(["Llámalo al ", "+52 555 123 4567", " hoy."]))

        assert "4567" not in completo
        assert "no divulgado" in completo
        assert completo.endswith(" hoy.")

    def test_no_retiene_texto_inofensivo(self) -> None:
        completo = "".join(self._emitir(["Tiene 15 años ", "de experiencia."]))

        assert completo == "Tiene 15 años de experiencia."

    def test_deja_pasar_metricas_y_expedientes(self) -> None:
        casos = [
            (["Procesó 17,000", "+ archivos"], "Procesó 17,000+ archivos"),
            (["Expediente MX/a/", "2024/008296"], "Expediente MX/a/2024/008296"),
            (["Norma IATF ", "16949"], "Norma IATF 16949"),
        ]
        for trozos, esperado in casos:
            assert "".join(self._emitir(trozos)) == esperado

    def test_el_email_no_se_ve_afectado(self) -> None:
        completo = "".join(self._emitir(["Escríbele a osc.09", "@hotmail.com"]))

        assert completo == "Escríbele a osc.09@hotmail.com"

    def test_respeta_el_idioma_del_marcador(self) -> None:
        completo = "".join(self._emitir(["Call ", "+52 555 123 4567"], "en"))

        assert "contact detail not disclosed" in completo
