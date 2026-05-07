from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app_python_automacao.models import MultaRescisoriaResult


TWOPLACES = Decimal("0.01")


@dataclass(slots=True)
class MultaRescisoriaCalculator:
    valor_beneficio: Decimal

    def calculate(self, data_venda: str | None, data_cancelamento: str | None) -> MultaRescisoriaResult:
        venda = _parse_date(data_venda)
        cancelamento = _parse_date(data_cancelamento)
        valor_beneficio = abs(self.valor_beneficio)

        if venda is None or cancelamento is None or valor_beneficio <= 0:
            return MultaRescisoriaResult(
                valor_multa=Decimal("0.00"),
                mensagem_calculo="",
                meses_restantes=0,
                dados_invalidos=True,
            )

        if cancelamento <= venda:
            return MultaRescisoriaResult(
                valor_multa=Decimal("0.00"),
                mensagem_calculo="",
                meses_restantes=0,
                dados_invalidos=True,
            )

        fim_teste = venda + timedelta(days=7)
        if cancelamento <= fim_teste:
            return MultaRescisoriaResult(
                valor_multa=Decimal("0.00"),
                mensagem_calculo="",
                meses_restantes=0,
                periodo_desistencia=True,
            )

        meses_pagos = _full_months_between(venda, cancelamento)
        meses_restantes = 12 - meses_pagos
        if meses_restantes <= 0:
            return MultaRescisoriaResult(
                valor_multa=Decimal("0.00"),
                mensagem_calculo="",
                meses_restantes=0,
                fidelidade_encerrada=True,
            )

        valor_multa = ((valor_beneficio / Decimal("12")) * Decimal(meses_restantes)).quantize(
            TWOPLACES,
            rounding=ROUND_HALF_UP,
        )
        plural = "MES RESTANTE" if meses_restantes == 1 else "MESES RESTANTES"
        mensagem = (
            "CALCULO DA MULTA RESCISORIA\n\n"
            f"DATA DE VENDA: {venda.strftime('%d/%m/%Y')}\n"
            f"DATA DE CANCELAMENTO: {cancelamento.strftime('%d/%m/%Y')}\n"
            f"VALOR DO BENEFICIO: R$ {format_decimal_brl(valor_beneficio)}\n\n"
            f"{meses_restantes} {plural} PARA O FIM DO CONTRATO FIDELIDADE\n\n"
            f"VALOR DA MULTA RESCISORIA: R$ {format_decimal_brl(valor_multa)}"
        )
        return MultaRescisoriaResult(
            valor_multa=valor_multa,
            mensagem_calculo=mensagem,
            meses_restantes=meses_restantes,
        )


def format_decimal_brl(value: Decimal) -> str:
    quantized = value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    integer_part, decimal_part = f"{quantized:.2f}".split(".")
    chunks: list[str] = []
    while integer_part:
        chunks.append(integer_part[-3:])
        integer_part = integer_part[:-3]
    return f"{'.'.join(reversed(chunks))},{decimal_part}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _full_months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)
