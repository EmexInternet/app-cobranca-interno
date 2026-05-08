from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app_python_automacao.models import (
    CancelamentoNegotiationSummary,
    CancelamentoRecord,
    HubsoftAtendimento,
    HubsoftFatura,
    MultaRescisoriaResult,
)


TWOPLACES = Decimal("0.01")


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_accents.upper().split())


def normalize_phone_br(value: str | None, country_code: str = "55") -> str | None:
    if value is None:
        return None

    digits = re.sub(r"\D+", "", value)
    if not digits:
        return None

    if digits.startswith("0"):
        digits = digits.lstrip("0")

    if digits.startswith(country_code):
        normalized = digits
    elif len(digits) in {10, 11}:
        normalized = f"{country_code}{digits}"
    else:
        normalized = digits

    if len(normalized) < len(country_code) + 10:
        return None
    return normalized


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


def filter_faturas_by_detalhamento(
    faturas: list[HubsoftFatura],
    descricoes_ignoradas: list[str],
) -> list[HubsoftFatura]:
    ignored = {normalize_text(item) for item in descricoes_ignoradas}
    if not ignored:
        return faturas

    filtered: list[HubsoftFatura] = []
    for fatura in faturas:
        descricoes = {normalize_text(item) for item in fatura.detalhamento_descricoes}
        if descricoes.intersection(ignored):
            continue
        filtered.append(fatura)
    return filtered


def build_negotiation_summary(
    faturas: list[HubsoftFatura],
    multa: MultaRescisoriaResult,
) -> CancelamentoNegotiationSummary:
    divida_sem_multa = sum((item.valor for item in faturas), Decimal("0")).quantize(
        TWOPLACES,
        rounding=ROUND_HALF_UP,
    )
    valor_multa = multa.valor_multa.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    total_divida = (divida_sem_multa + valor_multa).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    divida_sem_multa_50 = (divida_sem_multa * Decimal("0.5")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    divida_40 = (total_divida * Decimal("0.6")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    return CancelamentoNegotiationSummary(
        valor_multa=valor_multa,
        total_divida=total_divida,
        divida_sem_multa=divida_sem_multa,
        divida_sem_multa_50=divida_sem_multa_50,
        divida_40=divida_40,
        mensagem_calculo_multa=multa.mensagem_calculo,
        quantidade_faturas_consideradas=len(faturas),
    )


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if not payload:
            return []

        if _is_list_of_dicts(payload):
            return payload

        for item in payload:
            nested = extract_items(item)
            if nested:
                return nested

    if isinstance(payload, dict):
        if _looks_like_record(payload):
            return [payload]

        for key in ("data", "dados", "items", "itens", "results", "resultado"):
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
        "id_fatura",
        "protocolo",
        "tipo_atendimento",
        "id_cliente",
        "id_cliente_servico",
        "motivo_cancelamento",
        "valor",
        "detalhamento",
    }
    return any(key in value for key in known_keys)
