from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
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
class HubsoftFatura:
    id_fatura: int
    status: str
    valor: Decimal
    detalhamento_descricoes: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HubsoftFatura":
        return cls(
            id_fatura=int(data["id_fatura"]),
            status=str(data.get("status", "")),
            valor=_decimal_value(data.get("valor")),
            detalhamento_descricoes=_extract_detalhamento_descricoes(data.get("detalhamento")),
        )


@dataclass(slots=True)
class MultaRescisoriaResult:
    valor_multa: Decimal
    mensagem_calculo: str
    meses_restantes: int
    periodo_desistencia: bool = False
    fidelidade_encerrada: bool = False
    dados_invalidos: bool = False


@dataclass(slots=True)
class CancelamentoNegotiationSummary:
    valor_multa: Decimal
    total_divida: Decimal
    divida_sem_multa: Decimal
    divida_sem_multa_50: Decimal
    divida_40: Decimal
    mensagem_calculo_multa: str
    quantidade_faturas_consideradas: int


@dataclass(slots=True)
class WorkflowReport:
    total_cancelamentos_lidos: int = 0
    total_cancelamentos_processados: int = 0
    total_clientes_ja_processados: int = 0
    total_atendimentos_encontrados: int = 0
    total_atendimentos_fechados: int = 0
    total_observacoes_salvas: int = 0
    total_sem_atendimento: int = 0
    total_atendimentos_cancelamento_encontrados: int = 0
    total_atendimentos_cancelamento_fechados: int = 0
    total_sem_atendimento_cancelamento: int = 0
    total_faturas_consideradas: int = 0
    total_whatsapp_enviado: int = 0
    total_whatsapp_ignorado: int = 0
    total_whatsapp_falhou: int = 0

    def to_log_message(self) -> str:
        return (
            f"cancelamentos_lidos={self.total_cancelamentos_lidos}, "
            f"cancelamentos_processados={self.total_cancelamentos_processados}, "
            f"clientes_ja_processados={self.total_clientes_ja_processados}, "
            f"atendimentos_encontrados={self.total_atendimentos_encontrados}, "
            f"atendimentos_fechados={self.total_atendimentos_fechados}, "
            f"observacoes_salvas={self.total_observacoes_salvas}, "
            f"sem_atendimento={self.total_sem_atendimento}, "
            f"atendimentos_cancelamento_encontrados={self.total_atendimentos_cancelamento_encontrados}, "
            f"atendimentos_cancelamento_fechados={self.total_atendimentos_cancelamento_fechados}, "
            f"sem_atendimento_cancelamento={self.total_sem_atendimento_cancelamento}, "
            f"faturas_consideradas={self.total_faturas_consideradas}, "
            f"whatsapp_enviado={self.total_whatsapp_enviado}, "
            f"whatsapp_ignorado={self.total_whatsapp_ignorado}, "
            f"whatsapp_falhou={self.total_whatsapp_falhou}"
        )


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _decimal_value(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")

    if isinstance(value, Decimal):
        return value

    normalized = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")
    return Decimal(normalized)


def _extract_detalhamento_descricoes(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, dict):
        descricao = value.get("descricao")
        return [str(descricao)] if descricao not in (None, "") else []

    if isinstance(value, list):
        descricoes: list[str] = []
        for item in value:
            if isinstance(item, dict):
                descricao = item.get("descricao")
                if descricao not in (None, ""):
                    descricoes.append(str(descricao))
            elif item not in (None, ""):
                descricoes.append(str(item))
        return descricoes

    return [str(value)]
