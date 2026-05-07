from __future__ import annotations

import logging
from datetime import date

import httpx

from app_python_automacao.models import CancelamentoRecord
from app_python_automacao.settings import Settings
from app_python_automacao.utils import extract_items, filter_cancelamentos

LOGGER = logging.getLogger(__name__)


class CancelamentosClient:
    def __init__(self, settings: Settings, timeout: float = 30.0) -> None:
        self.settings = settings
        self.timeout = timeout

    def fetch_cancelamentos(self, dia_inicio: date, dia_fim: date) -> list[CancelamentoRecord]:
        url = f"{self.settings.cancelamentos_api_url.rstrip('/')}/cancelamentos"
        params = {
            "dia_inicio": dia_inicio.isoformat(),
            "dia_fim": dia_fim.isoformat(),
        }
        headers = {
            "accept": "application/json",
            "x-api-key": self.settings.cancelamentos_api_key,
        }

        LOGGER.info(
            "Consultando API de cancelamentos entre %s e %s.",
            params["dia_inicio"],
            params["dia_fim"],
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()

        items = extract_items(payload)
        records = [CancelamentoRecord.from_dict(item) for item in items]
        LOGGER.info("API de cancelamentos retornou %s registros.", len(records))
        return records

    def fetch_cancelamentos_elegiveis(self, dia_inicio: date, dia_fim: date) -> list[CancelamentoRecord]:
        records = self.fetch_cancelamentos(dia_inicio, dia_fim)
        elegiveis = filter_cancelamentos(records, self.settings.motivo_cancelamento_alvo)
        LOGGER.info(
            "Filtro por motivo de cancelamento reduziu o lote para %s registros.",
            len(elegiveis),
        )
        return elegiveis
