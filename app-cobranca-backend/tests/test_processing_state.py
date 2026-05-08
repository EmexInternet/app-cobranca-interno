from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from app_python_automacao.models import CancelamentoRecord
from app_python_automacao.processing_state import ProcessingStateStore


class ProcessingStateStoreTestCase(unittest.TestCase):
    def _make_state_path(self) -> Path:
        import os

        fd, raw_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        path = Path(raw_path)
        path.unlink(missing_ok=True)
        return path

    def test_get_next_dia_inicio_uses_fallback_when_empty(self) -> None:
        path = self._make_state_path()
        try:
            store = ProcessingStateStore(file_path=path)
            self.assertEqual(store.get_next_dia_inicio(date(2026, 5, 1)), date(2026, 5, 1))
        finally:
            path.unlink(missing_ok=True)

    def test_mark_processed_and_is_processed(self) -> None:
        path = self._make_state_path()
        try:
            store = ProcessingStateStore(file_path=path)
            cancelamento = CancelamentoRecord(
                codigo_cliente=45098,
                id_cliente=44847,
                id_cliente_servico=85830,
                nome_razaosocial="JOAO GABRIEL",
            )
            self.assertFalse(store.is_processed(cancelamento))
            store.mark_processed(
                cancelamento,
                fase_1="sucesso",
                fase_1_1="sucesso",
                fase_2="sucesso",
                fase_3="erro",
            )
            self.assertTrue(store.is_processed(cancelamento))
        finally:
            path.unlink(missing_ok=True)

    def test_update_last_dia_fim_changes_next_dia_inicio(self) -> None:
        path = self._make_state_path()
        try:
            store = ProcessingStateStore(file_path=path)
            store.update_last_dia_fim(date(2026, 5, 8))
            self.assertEqual(store.get_next_dia_inicio(date(2026, 4, 1)), date(2026, 5, 8))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
