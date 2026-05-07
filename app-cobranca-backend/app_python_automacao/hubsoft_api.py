from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app_python_automacao.models import HubsoftAtendimento
from app_python_automacao.settings import Settings
from app_python_automacao.utils import extract_items, filter_atendimentos_cobranca

LOGGER = logging.getLogger(__name__)


@dataclass
class AuthToken:
    access_token: str
    refresh_token: str | None
    token_type: str


class HubsoftApiClient:
    def __init__(self, settings: Settings, timeout: float = 30.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self._token: AuthToken | None = None

    def authenticate(self) -> AuthToken:
        url = f"{self.settings.hubsoft_api_base_url}/oauth/token"
        payload = {
            "grant_type": "password",
            "client_id": self.settings.hubsoft_client_id,
            "client_secret": self.settings.hubsoft_client_secret,
            "username": self.settings.hubsoft_username,
            "password": self.settings.hubsoft_password,
        }

        LOGGER.info("Autenticando na API do Hubsoft.")
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.json()

        self._token = AuthToken(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data["token_type"],
        )
        return self._token

    def get_pending_cobranca(self, id_cliente_servico: int) -> list[HubsoftAtendimento]:
        token = self._require_token()
        url = (
            f"{self.settings.hubsoft_api_base_url}/api/v1/integracao/cliente/atendimento"
            "?busca=id_cliente_servico"
            f"&termo_busca={id_cliente_servico}"
            "&apenas_pendente=sim"
        )

        LOGGER.info("Consultando atendimentos pendentes do cliente_servico %s.", id_cliente_servico)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._auth_headers(token))
            response.raise_for_status()
            payload = response.json()

        items = extract_items(payload)
        atendimentos = [HubsoftAtendimento.from_dict(item) for item in items]
        cobranca = filter_atendimentos_cobranca(atendimentos, self.settings.tipo_atendimento_alvo)
        LOGGER.info(
            "Cliente_servico %s retornou %s atendimentos de cobranca pendentes.",
            id_cliente_servico,
            len(cobranca),
        )
        return cobranca

    def add_message(self, id_atendimento: int, mensagem: str) -> None:
        token = self._require_token()
        url = (
            f"{self.settings.hubsoft_api_base_url}/api/v1/integracao/atendimento/"
            f"adicionar_mensagem/{id_atendimento}"
        )

        LOGGER.info("Adicionando relato no atendimento %s.", id_atendimento)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                url,
                json={"mensagem": mensagem},
                headers={
                    **self._auth_headers(token),
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

    def close_atendimento(self, id_atendimento: int) -> None:
        token = self._require_token()
        url = f"{self.settings.hubsoft_api_base_url}/api/v1/integracao/atendimento/{id_atendimento}"
        payload = {
            "parametros_fechamento": {
                "id_motivo_fechamento_atendimento": self.settings.id_motivo_fechamento_atendimento,
                "descricao_fechamento": self.settings.descricao_fechamento_atendimento,
                "status_fechamento": self.settings.status_fechamento_atendimento,
            },
            "fechar_atendimento": True,
        }

        LOGGER.info("Fechando atendimento %s.", id_atendimento)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.put(
                url,
                json=payload,
                headers={
                    **self._auth_headers(token),
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

    def _auth_headers(self, token: AuthToken) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"{token.token_type} {token.access_token}",
        }

    def _require_token(self) -> AuthToken:
        if self._token is None:
            return self.authenticate()
        return self._token
