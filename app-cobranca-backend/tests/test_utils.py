from __future__ import annotations

from datetime import date
import unittest

from app_python_automacao.models import CancelamentoRecord, HubsoftAtendimento
from app_python_automacao.utils import (
    compute_cancelamentos_window,
    extract_items,
    filter_atendimentos_cobranca,
    filter_cancelamentos,
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


if __name__ == "__main__":
    unittest.main()
