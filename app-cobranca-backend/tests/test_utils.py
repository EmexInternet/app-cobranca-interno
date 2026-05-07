from __future__ import annotations

from datetime import date
from decimal import Decimal
import unittest

from app_python_automacao.models import CancelamentoRecord, HubsoftAtendimento, HubsoftFatura
from app_python_automacao.multa_rescisoria import MultaRescisoriaCalculator, format_decimal_brl
from app_python_automacao.utils import (
    build_negotiation_summary,
    compute_cancelamentos_window,
    extract_items,
    filter_atendimentos_cobranca,
    filter_cancelamentos,
    filter_faturas_by_detalhamento,
    normalize_text,
)


class UtilsTestCase(unittest.TestCase):
    def test_normalize_text_removes_accents_and_extra_spaces(self) -> None:
        self.assertEqual(normalize_text("  Cobrança   Automática "), "COBRANCA AUTOMATICA")

    def test_compute_cancelamentos_window_uses_first_day_of_previous_month(self) -> None:
        dia_inicio, dia_fim = compute_cancelamentos_window(date(2026, 5, 7))
        self.assertEqual(dia_inicio, date(2026, 4, 1))
        self.assertEqual(dia_fim, date(2026, 5, 7))

    def test_filter_cancelamentos_is_accent_insensitive(self) -> None:
        records = [
            CancelamentoRecord(
                codigo_cliente=1,
                id_cliente=10,
                id_cliente_servico=100,
                nome_razaosocial="Cliente A",
                motivo_cancelamento="CANCELAMENTO AUTOMATICO INADIMPLENCIA",
            ),
            CancelamentoRecord(
                codigo_cliente=2,
                id_cliente=20,
                id_cliente_servico=200,
                nome_razaosocial="Cliente B",
                motivo_cancelamento="MUDANCA DE ENDERECO",
            ),
        ]
        filtered = filter_cancelamentos(records, "CANCELAMENTO AUTOMATICO INADIMPLENCIA")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id_cliente, 10)

    def test_filter_atendimentos_cobranca_is_accent_insensitive(self) -> None:
        atendimentos = [
            HubsoftAtendimento(
                id_atendimento=1,
                protocolo="20260507001",
                tipo_atendimento="COBRANCA",
            ),
            HubsoftAtendimento(
                id_atendimento=2,
                protocolo="20260507002",
                tipo_atendimento="SUPORTE",
            ),
        ]
        filtered = filter_atendimentos_cobranca(atendimentos, "COBRANCA")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id_atendimento, 1)

    def test_extract_items_supports_nested_payload(self) -> None:
        payload = {
            "atendimentos": {
                "pendentes": [
                    {
                        "id_atendimento": 99,
                        "protocolo": "202605070099",
                        "tipo_atendimento": "COBRANÇA",
                    }
                ]
            }
        }
        items = extract_items(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id_atendimento"], 99)

    def test_workflow_rule_uses_only_one_atendimento_per_servico(self) -> None:
        atendimentos = [
            HubsoftAtendimento(id_atendimento=1, protocolo="P1", tipo_atendimento="COBRANCA"),
            HubsoftAtendimento(id_atendimento=2, protocolo="P2", tipo_atendimento="COBRANCA"),
            HubsoftAtendimento(id_atendimento=3, protocolo="P3", tipo_atendimento="COBRANCA"),
        ]
        self.assertEqual(atendimentos[0].id_atendimento, 1)
        self.assertEqual(atendimentos[0].protocolo, "P1")

    def test_filter_faturas_by_detalhamento_ignores_multa_and_comodato(self) -> None:
        faturas = [
            HubsoftFatura(id_fatura=1, status="pendente", valor=Decimal("100"), detalhamento_descricoes=["MENSALIDADE"]),
            HubsoftFatura(
                id_fatura=2,
                status="pendente",
                valor=Decimal("200"),
                detalhamento_descricoes=["MULTA RESCISORIA"],
            ),
            HubsoftFatura(
                id_fatura=3,
                status="pendente",
                valor=Decimal("300"),
                detalhamento_descricoes=["EQUIPAMENTO EM COMODATO"],
            ),
        ]
        filtered = filter_faturas_by_detalhamento(
            faturas,
            ["MULTA RESCISORIA", "EQUIPAMENTO EM COMODATO"],
        )
        self.assertEqual([item.id_fatura for item in filtered], [1])

    def test_build_negotiation_summary_calculates_discount_values(self) -> None:
        faturas = [
            HubsoftFatura(id_fatura=1, status="pendente", valor=Decimal("100.00"), detalhamento_descricoes=[]),
            HubsoftFatura(id_fatura=2, status="pendente", valor=Decimal("50.00"), detalhamento_descricoes=[]),
        ]
        multa = MultaRescisoriaCalculator(Decimal("120.00")).calculate("2026-01-01", "2026-03-15")
        resumo = build_negotiation_summary(faturas, multa)
        self.assertEqual(resumo.divida_sem_multa, Decimal("150.00"))
        self.assertEqual(resumo.valor_multa, Decimal("100.00"))
        self.assertEqual(resumo.total_divida, Decimal("250.00"))
        self.assertEqual(resumo.divida_sem_multa_50, Decimal("75.00"))
        self.assertEqual(resumo.divida_40, Decimal("150.00"))

    def test_multa_rescisoria_matches_expected_months_remaining(self) -> None:
        multa = MultaRescisoriaCalculator(Decimal("120.00")).calculate("2026-01-01", "2026-03-15")
        self.assertEqual(multa.meses_restantes, 10)
        self.assertEqual(multa.valor_multa, Decimal("100.00"))
        self.assertIn("VALOR DA MULTA RESCISORIA: R$ 100,00", multa.mensagem_calculo)

    def test_format_decimal_brl_outputs_brazilian_currency_number(self) -> None:
        self.assertEqual(format_decimal_brl(Decimal("1234.5")), "1.234,50")


if __name__ == "__main__":
    unittest.main()
