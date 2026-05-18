from __future__ import annotations

import unittest

from app_python_automacao.workflow import CobrancaWorkflow


class WorkflowRetryPolicyTestCase(unittest.TestCase):
    def test_cliente_com_erro_inesperado_nao_deve_ser_marcado_como_processado(self) -> None:
        self.assertFalse(
            CobrancaWorkflow._should_mark_processed(
                fase_1="nao_iniciada",
                fase_1_1="nao_iniciada",
                fase_2="nao_iniciada",
                fase_3="nao_iniciada",
                erro_inesperado=True,
            )
        )

    def test_cliente_com_erro_em_qualquer_fase_nao_deve_ser_marcado_como_processado(self) -> None:
        self.assertFalse(
            CobrancaWorkflow._should_mark_processed(
                fase_1="sucesso",
                fase_1_1="erro",
                fase_2="sucesso",
                fase_3="sucesso",
                erro_inesperado=False,
            )
        )

    def test_cliente_sem_erro_pode_ser_marcado_como_processado(self) -> None:
        self.assertTrue(
            CobrancaWorkflow._should_mark_processed(
                fase_1="sucesso",
                fase_1_1="sucesso",
                fase_2="sucesso",
                fase_3="ignorado_desabilitado",
                erro_inesperado=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
