from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app_python_automacao.models import CancelamentoRecord


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ERROR_FILE = BASE_DIR / "storage" / "erros_fluxo.txt"


@dataclass(slots=True)
class PhaseStatusEntry:
    fase_1: str
    fase_2: str
    fase_3: str
    erro: str
    codigo_erro: str | None = None
    detalhe: str | None = None


class ErrorReporter:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_ERROR_FILE

    def append(
        self,
        *,
        cancelamento: CancelamentoRecord | None,
        status: PhaseStatusEntry,
        nome_cliente: str | None = None,
        telefone: str | None = None,
    ) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat(timespec="seconds")
        parts = [timestamp]

        if cancelamento is not None:
            parts.extend(
                [
                    f"codigo_cliente={cancelamento.codigo_cliente}",
                    f"id_cliente={cancelamento.id_cliente}",
                    f"id_cliente_servico={cancelamento.id_cliente_servico}",
                    f"nome_cliente={cancelamento.nome_razaosocial}",
                ]
            )
            if cancelamento.telefone_primario:
                parts.append(f"telefone={cancelamento.telefone_primario}")
        else:
            if nome_cliente:
                parts.append(f"nome_cliente={nome_cliente}")
            if telefone:
                parts.append(f"telefone={telefone}")

        parts.extend(
            [
                f"fase_1={status.fase_1}",
                f"fase_2={status.fase_2}",
                f"fase_3={status.fase_3}",
                f"erro={status.erro}",
            ]
        )

        if status.codigo_erro:
            parts.append(f"codigo_erro={status.codigo_erro}")
        if status.detalhe:
            parts.append(f"detalhe={status.detalhe}")

        with self.file_path.open("a", encoding="utf-8") as handler:
            handler.write(" | ".join(parts) + "\n")
