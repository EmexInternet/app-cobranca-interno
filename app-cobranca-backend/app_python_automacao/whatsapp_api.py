from __future__ import annotations

import logging

import httpx

from app_python_automacao.settings import Settings
from app_python_automacao.utils import normalize_phone_br

LOGGER = logging.getLogger(__name__)


class WhatsAppApiClient:
    def __init__(self, settings: Settings, timeout: float = 30.0) -> None:
        self.settings = settings
        self.timeout = timeout

    def is_enabled(self) -> bool:
        return all(
            [
                self.settings.whatsapp_api_enabled,
                self.settings.whatsapp_api_url,
                self.settings.whatsapp_api_token,
                self.settings.whatsapp_hsm_id > 0,
                self.settings.whatsapp_cod_conta > 0,
            ]
        )

    def send_phase_three_hsm(self, nome_cliente: str, telefone: str | None) -> bool:
        if not self.is_enabled():
            LOGGER.info("Fase 3 de WhatsApp desabilitada ou incompleta nas configuracoes.")
            return False

        telefone_normalizado = normalize_phone_br(telefone, self.settings.whatsapp_country_code)
        if not telefone_normalizado:
            LOGGER.warning(
                "WhatsApp nao enviado para cliente %s por telefone ausente ou invalido: %s",
                nome_cliente,
                telefone,
            )
            return False

        payload = {
            "cod_conta": self.settings.whatsapp_cod_conta,
            "hsm": self.settings.whatsapp_hsm_id,
            "variaveis": {"1": nome_cliente},
            "contato": {
                "nome": nome_cliente,
                "telefone": telefone_normalizado,
            },
            "tipo_envio": self.settings.whatsapp_tipo_envio,
        }
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.settings.whatsapp_api_token,
        }

        LOGGER.info(
            "Enviando HSM de WhatsApp para cliente %s no telefone %s.",
            nome_cliente,
            telefone_normalizado,
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.settings.whatsapp_api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

        return True
