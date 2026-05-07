from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any

from app_python_automacao.models import CancelamentoRecord, HubsoftAtendimento


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_accents.upper().split())


def compute_cancelamentos_window(today: date) -> tuple[date, date]:
    current_month_start = today.replace(day=1)
    previous_month_end = current_month_start.fromordinal(current_month_start.toordinal() - 1)
    previous_month_start = previous_month_end.replace(day=1)
    return previous_month_start, today


def filter_cancelamentos(
    records: list[CancelamentoRecord],
    motivo_alvo: str,
) -> list[CancelamentoRecord]:
    target = normalize_text(motivo_alvo)
    return [record for record in records if normalize_text(record.motivo_cancelamento) == target]


def filter_atendimentos_cobranca(
    atendimentos: list[HubsoftAtendimento],
    tipo_alvo: str,
) -> list[HubsoftAtendimento]:
    target = normalize_text(tipo_alvo)
    return [item for item in atendimentos if normalize_text(item.tipo_atendimento) == target]


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if _is_list_of_dicts(payload):
            return payload

        for item in payload:
            nested = extract_items(item)
            if nested:
                return nested

    if isinstance(payload, dict):
        if _looks_like_record(payload):
            return [payload]

        for key in ("data", "dados", "items", "results", "resultado"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        for value in payload.values():
            try:
                nested = extract_items(value)
                if nested:
                    return nested
            except ValueError:
                continue

    raise ValueError("Formato de payload nao suportado para extracao de itens.")


def _is_list_of_dicts(value: list[Any]) -> bool:
    return bool(value) and all(isinstance(item, dict) for item in value)


def _looks_like_record(value: dict[str, Any]) -> bool:
    known_keys = {
        "id_atendimento",
        "protocolo",
        "tipo_atendimento",
        "id_cliente",
        "id_cliente_servico",
        "motivo_cancelamento",
    }
    return any(key in value for key in known_keys)
