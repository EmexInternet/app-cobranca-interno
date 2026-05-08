from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app_python_automacao.error_reporter import ErrorReporter, PhaseStatusEntry
from app_python_automacao.models import CancelamentoRecord


class ErrorReporterTestCase(unittest.TestCase):
    def test_append_writes_human_readable_error_line(self) -> None:
        fd, raw_path = tempfile.mkstemp(suffix=".txt")
        import os

        os.close(fd)
        Path(raw_path).unlink(missing_ok=True)
        target = Path(raw_path)
        try:
            reporter = ErrorReporter(file_path=target)
            cancelamento = CancelamentoRecord(
                codigo_cliente=45098,
                id_cliente=44847,
                id_cliente_servico=85830,
                nome_razaosocial="JOAO GABRIEL",
                telefone_primario="(24) 99915-7259",
            )
            reporter.append(
                cancelamento=cancelamento,
                status=PhaseStatusEntry(
                    fase_1="sucesso",
                    fase_1_1="sucesso",
                    fase_2="sucesso",
                    fase_3="erro",
                    erro="Contato possui atendimento ativo",
                    codigo_erro="13",
                    detalhe="status_http=400",
                ),
            )

            content = target.read_text(encoding="utf-8")
            self.assertIn("codigo_cliente=45098", content)
            self.assertIn("fase_1=sucesso", content)
            self.assertIn("fase_1_1=sucesso", content)
            self.assertIn("fase_2=sucesso", content)
            self.assertIn("fase_3=erro", content)
            self.assertIn("codigo_erro=13", content)
            self.assertIn("erro=Contato possui atendimento ativo", content)
        finally:
            Path(raw_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
