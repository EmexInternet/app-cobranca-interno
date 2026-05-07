from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CancelamentoRecord:
    codigo_cliente: int
    id_cliente: int
    id_cliente_servico: int
    nome_razaosocial: str
    telefone_primario: str | None = None
    email_principal: str | None = None
    numero_plano: int | None = None
    plano: str | None = None
    data_venda: str | None = None
    data_cancelamento: str | None = None
    motivo_cancelamento: str = ""
    cidade: str | None = None
    bairro: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CancelamentoRecord":
        return cls(
            codigo_cliente=int(data["codigo_cliente"]),
            id_cliente=int(data["id_cliente"]),
            id_cliente_servico=int(data["id_cliente_servico"]),
            nome_razaosocial=str(data.get("nome_razaosocial", "")),
            telefone_primario=data.get("telefone_primario"),
            email_principal=data.get("email_principal"),
            numero_plano=_optional_int(data.get("numero_plano")),
            plano=data.get("plano"),
            data_venda=data.get("data_venda"),
            data_cancelamento=data.get("data_cancelamento"),
            motivo_cancelamento=str(data.get("motivo_cancelamento", "")),
            cidade=data.get("cidade"),
            bairro=data.get("bairro"),
        )


@dataclass(slots=True)
class HubsoftAtendimento:
    id_atendimento: int
    protocolo: str
    descricao_abertura: str | None = None
    tipo_atendimento: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HubsoftAtendimento":
        return cls(
            id_atendimento=int(data["id_atendimento"]),
            protocolo=str(data["protocolo"]),
            descricao_abertura=data.get("descricao_abertura"),
            tipo_atendimento=str(data.get("tipo_atendimento", "")),
        )


@dataclass(slots=True)
class WorkflowReport:
    total_cancelamentos_lidos: int = 0
    total_cancelamentos_processados: int = 0
    total_atendimentos_encontrados: int = 0
    total_atendimentos_fechados: int = 0
    total_observacoes_salvas: int = 0
    total_sem_atendimento: int = 0

    def to_log_message(self) -> str:
        return (
            f"cancelamentos_lidos={self.total_cancelamentos_lidos}, "
            f"cancelamentos_processados={self.total_cancelamentos_processados}, "
            f"atendimentos_encontrados={self.total_atendimentos_encontrados}, "
            f"atendimentos_fechados={self.total_atendimentos_fechados}, "
            f"observacoes_salvas={self.total_observacoes_salvas}, "
            f"sem_atendimento={self.total_sem_atendimento}"
        )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
