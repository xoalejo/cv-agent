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
        for patent in profile.patents:
            blobs.append(f"{patent.title} {patent.file_number}")
        for channel in profile.contact_channels:
            blobs.append(channel.value)

        offenders = [blob for blob in blobs if contains_contact_data(blob)]
        assert offenders == []
