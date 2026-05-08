from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app_python_automacao.models import CancelamentoRecord


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = BASE_DIR / "storage" / "processamento_state.json"


@dataclass(slots=True)
class ProcessingState:
    last_dia_fim: str | None
    processed_clients: dict[str, dict[str, Any]]


class ProcessingStateStore:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_STATE_FILE

    def load(self) -> ProcessingState:
        if not self.file_path.exists():
            return ProcessingState(last_dia_fim=None, processed_clients={})

        raw = json.loads(self.file_path.read_text(encoding="utf-8"))
        return ProcessingState(
            last_dia_fim=raw.get("last_dia_fim"),
            processed_clients=raw.get("processed_clients", {}),
        )

    def get_next_dia_inicio(self, fallback: date) -> date:
        state = self.load()
        if not state.last_dia_fim:
            return fallback
        return date.fromisoformat(state.last_dia_fim)

    def is_processed(self, cancelamento: CancelamentoRecord) -> bool:
        state = self.load()
        return self._build_key(cancelamento) in state.processed_clients

    def mark_processed(
        self,
        cancelamento: CancelamentoRecord,
        *,
        fase_1: str,
        fase_1_1: str,
        fase_2: str,
        fase_3: str,
    ) -> None:
        state = self.load()
        key = self._build_key(cancelamento)
        state.processed_clients[key] = {
            "processed_at": datetime.now().isoformat(timespec="seconds"),
            "codigo_cliente": cancelamento.codigo_cliente,
            "id_cliente": cancelamento.id_cliente,
            "id_cliente_servico": cancelamento.id_cliente_servico,
            "nome_cliente": cancelamento.nome_razaosocial,
            "fase_1": fase_1,
            "fase_1_1": fase_1_1,
            "fase_2": fase_2,
            "fase_3": fase_3,
            "data_cancelamento": cancelamento.data_cancelamento,
        }
        self._save(state)

    def update_last_dia_fim(self, dia_fim: date) -> None:
        state = self.load()
        state.last_dia_fim = dia_fim.isoformat()
        self._save(state)

    def _save(self, state: ProcessingState) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_dia_fim": state.last_dia_fim,
            "processed_clients": state.processed_clients,
        }
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _build_key(self, cancelamento: CancelamentoRecord) -> str:
        return f"{cancelamento.codigo_cliente}:{cancelamento.id_cliente}:{cancelamento.id_cliente_servico}"
