from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx

from app_python_automacao.browser_automation import HubsoftBrowserAutomation
from app_python_automacao.cancelamentos_api import CancelamentosClient
from app_python_automacao.hubsoft_api import HubsoftApiClient
from app_python_automacao.models import CancelamentoRecord, HubsoftAtendimento, WorkflowReport
from app_python_automacao.multa_rescisoria import MultaRescisoriaCalculator, format_decimal_brl
from app_python_automacao.settings import Settings
from app_python_automacao.utils import (
    build_negotiation_summary,
    compute_cancelamentos_window,
    filter_cancelamentos,
    filter_faturas_by_detalhamento,
)

LOGGER = logging.getLogger(__name__)


RELATO_ENCERRAMENTO_FASE_1 = (
    "TENTATIVAS DE CONTATO PARA NEGOCIACAO SEM SUCESSO.\n\n"
    "> CONTRATO CANCELADO POR INADIMPLENCIA.\n"
)


class CobrancaWorkflow:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cancelamentos_client = CancelamentosClient(settings)
        self.hubsoft_client = HubsoftApiClient(settings)

    def run_full(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        only_cliente_id: int | None = None,
        dia_inicio: date | None = None,
        dia_fim: date | None = None,
        skip_browser: bool = False,
        headless: bool = True,
    ) -> WorkflowReport:
        if dia_inicio is None or dia_fim is None:
            auto_dia_inicio, auto_dia_fim = compute_cancelamentos_window(date.today())
            dia_inicio = dia_inicio or auto_dia_inicio
            dia_fim = dia_fim or auto_dia_fim

        cancelamentos = self.cancelamentos_client.fetch_cancelamentos(dia_inicio, dia_fim)
        report = WorkflowReport(total_cancelamentos_lidos=len(cancelamentos))

        elegiveis = [
            item
            for item in filter_cancelamentos(cancelamentos, self.settings.motivo_cancelamento_alvo)
            if only_cliente_id is None or item.id_cliente == only_cliente_id
        ]

        if limit is not None:
            elegiveis = elegiveis[:limit]

        report.total_cancelamentos_processados = len(elegiveis)
        if not elegiveis:
            LOGGER.warning("Nenhum cancelamento elegivel encontrado para processar.")
            return report

        return self._process_cancelamentos(
            elegiveis,
            dry_run=dry_run,
            skip_browser=skip_browser,
            headless=headless,
            base_report=report,
        )

    def run_single_service(
        self,
        id_cliente: int,
        id_cliente_servico: int,
        dry_run: bool = False,
        skip_browser: bool = False,
        headless: bool = True,
    ) -> WorkflowReport:
        cancelamento = CancelamentoRecord(
            codigo_cliente=self.settings.teste_codigo_cliente,
            id_cliente=id_cliente,
            id_cliente_servico=id_cliente_servico,
            nome_razaosocial="MODO TESTE / EXECUCAO DIRETA",
            motivo_cancelamento=self.settings.motivo_cancelamento_alvo,
        )
        report = WorkflowReport(total_cancelamentos_lidos=1, total_cancelamentos_processados=1)
        return self._process_cancelamentos(
            [cancelamento],
            dry_run=dry_run,
            skip_browser=skip_browser,
            headless=headless,
            base_report=report,
        )

    def add_observation_only(
        self,
        id_cliente: int,
        protocolo: str,
        dry_run: bool = False,
        headless: bool = True,
    ) -> None:
        with HubsoftBrowserAutomation(self.settings, dry_run=dry_run, headless=headless) as browser:
            browser.add_observation(id_cliente=id_cliente, protocolo=protocolo)

    def _process_cancelamentos(
        self,
        cancelamentos: list[CancelamentoRecord],
        dry_run: bool,
        skip_browser: bool,
        headless: bool,
        base_report: WorkflowReport,
    ) -> WorkflowReport:
        browser_context = (
            HubsoftBrowserAutomation(self.settings, dry_run=dry_run, headless=headless)
            if not skip_browser
            else _NoOpBrowserAutomation()
        )

        with browser_context as browser:
            for cancelamento in cancelamentos:
                LOGGER.info(
                    "Processando cliente %s / cliente_servico %s.",
                    cancelamento.id_cliente,
                    cancelamento.id_cliente_servico,
                )
                atendimentos = self.hubsoft_client.get_pending_cobranca(cancelamento.id_cliente_servico)

                if not atendimentos:
                    base_report.total_sem_atendimento += 1
                    LOGGER.warning(
                        "Nenhum atendimento de cobranca pendente encontrado para cliente_servico %s.",
                        cancelamento.id_cliente_servico,
                    )
                    continue

                atendimento = atendimentos[0]
                base_report.total_atendimentos_encontrados += 1
                if len(atendimentos) > 1:
                    LOGGER.info(
                        "Cliente_servico %s possui %s atendimentos de cobranca pendentes. "
                        "Somente o primeiro sera utilizado: id_atendimento=%s protocolo=%s.",
                        cancelamento.id_cliente_servico,
                        len(atendimentos),
                        atendimento.id_atendimento,
                        atendimento.protocolo,
                    )

                if dry_run:
                    LOGGER.info(
                        "Dry-run: atendimento %s seria relatado, fechado e observado com protocolo %s.",
                        atendimento.id_atendimento,
                        atendimento.protocolo,
                    )
                else:
                    self.hubsoft_client.add_message(
                        atendimento.id_atendimento,
                        RELATO_ENCERRAMENTO_FASE_1,
                    )
                    self.hubsoft_client.close_atendimento(atendimento.id_atendimento)
                    base_report.total_atendimentos_fechados += 1

                atendimentos_cancelamento = self.hubsoft_client.get_pending_cancelamento_inadimplencia(
                    cancelamento.id_cliente_servico
                )
                protocolo_observacao = atendimento.protocolo
                if atendimentos_cancelamento:
                    protocolo_observacao = atendimentos_cancelamento[0].protocolo
                    LOGGER.info(
                        "Observacao do cliente %s sera vinculada ao protocolo do atendimento de cancelamento: %s.",
                        cancelamento.id_cliente,
                        protocolo_observacao,
                    )
                else:
                    LOGGER.warning(
                        "Cliente_servico %s nao possui atendimento de cancelamento pendente. "
                        "Observacao permanecera com o protocolo de cobranca %s.",
                        cancelamento.id_cliente_servico,
                        protocolo_observacao,
                    )

                browser.add_observation(
                    id_cliente=cancelamento.id_cliente,
                    protocolo=protocolo_observacao,
                )
                base_report.total_observacoes_salvas += 0 if dry_run else 1

                self._process_cancelamento_phase_two(
                    cancelamento=cancelamento,
                    atendimentos=atendimentos_cancelamento,
                    dry_run=dry_run,
                    base_report=base_report,
                )

        return base_report

    def _process_cancelamento_phase_two(
        self,
        cancelamento: CancelamentoRecord,
        atendimentos: list[HubsoftAtendimento] | None,
        dry_run: bool,
        base_report: WorkflowReport,
    ) -> None:
        atendimentos = atendimentos or []
        if not atendimentos:
            base_report.total_sem_atendimento_cancelamento += 1
            LOGGER.warning(
                "Nenhum atendimento de cancelamento por inadimplencia pendente encontrado para cliente_servico %s.",
                cancelamento.id_cliente_servico,
            )
            return

        atendimento = atendimentos[0]
        base_report.total_atendimentos_cancelamento_encontrados += 1
        if len(atendimentos) > 1:
            LOGGER.info(
                "Cliente_servico %s possui %s atendimentos de cancelamento pendentes. "
                "Somente o primeiro sera utilizado: id_atendimento=%s protocolo=%s.",
                cancelamento.id_cliente_servico,
                len(atendimentos),
                atendimento.id_atendimento,
                atendimento.protocolo,
            )

        faturas = self.hubsoft_client.get_pending_faturas(cancelamento.id_cliente_servico)
        faturas_validas = filter_faturas_by_detalhamento(
            faturas,
            self.settings.financeiro_descricoes_ignoradas,
        )
        base_report.total_faturas_consideradas += len(faturas_validas)

        multa = self._calculate_multa(cancelamento)
        resumo = build_negotiation_summary(faturas_validas, multa)
        mensagem = self._build_cancelamento_message(resumo)

        if dry_run:
            LOGGER.info(
                "Dry-run fase 2: atendimento %s seria relatado e fechado. "
                "faturas_consideradas=%s valor_multa=R$ %s total_divida=R$ %s",
                atendimento.id_atendimento,
                resumo.quantidade_faturas_consideradas,
                format_decimal_brl(resumo.valor_multa),
                format_decimal_brl(resumo.total_divida),
            )
            return

        self.hubsoft_client.add_message(atendimento.id_atendimento, mensagem)
        try:
            self.hubsoft_client.close_atendimento(atendimento.id_atendimento)
            base_report.total_atendimentos_cancelamento_fechados += 1
        except httpx.HTTPStatusError:
            LOGGER.warning(
                "Atendimento %s nao pode ser finalizado por retorno. Relato alternativo sera registrado.",
                atendimento.id_atendimento,
            )
            self.hubsoft_client.add_message(
                atendimento.id_atendimento,
                "ATENDIMENTO NÃO PODE SER FINALIZADO DEVIDO O.S EM ABERTO - "
                "SERÁ FINALIZADO EM MASSA QUANDO NOVO PROCESSO DO FLUXO DE RETIRADA FOR RODADO",
            )

    def _calculate_multa(self, cancelamento: CancelamentoRecord):
        calculator = MultaRescisoriaCalculator(
            valor_beneficio=Decimal(self.settings.multa_rescisoria_valor_beneficio_padrao.replace(",", ".")),
        )
        result = calculator.calculate(cancelamento.data_venda, cancelamento.data_cancelamento)
        if result.dados_invalidos:
            LOGGER.warning(
                "Calculo da multa rescisoria ficou zerado para cliente_servico %s por falta de dados suficientes "
                "ou valor-beneficio padrao nao configurado.",
                cancelamento.id_cliente_servico,
            )
        return result

    def _build_cancelamento_message(self, resumo) -> str:
        return (
            "> CONTRATO CANCELADO POR INADIMPLÊNCIA.\n"
            "> E-MAIL E WHATSAPP ENVIADOS.\n\n"
            f"VALOR TOTAL DA DÍVIDA: R$ {format_decimal_brl(resumo.total_divida)}\n\n"
            "CASO O(A) CLIENTE ENTRE EM CONTATO, FAVOR INFORMAR SOBRE A PENDÊNCIA FINANCEIRA EM ABERTO E NEGOCIAÇÕES DISPONÍVEIS:\n\n"
            "OPÇÃO 1 - SE O(A) CLIENTE DESEJAR RETORNAR COM O SERVIÇO:\n\n"
            f"FICARÁ ISENTO DA MULTA RESCISÓRIA E O VALOR DO DÉBITO PASSA A SER R$ {format_decimal_brl(resumo.divida_sem_multa)}.\n"
            f"SERÁ CONCEDIDO 50% DE DESCONTO E O VALOR PARA PAGAMENTO FICA EM R$ {format_decimal_brl(resumo.divida_sem_multa_50)} + TAXA DE ATIVAÇÃO (SUJEITO À AVALIAÇÃO).\n"
            "A NEGOCIAÇÃO PODERÁ SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS À FRENTE.\n"
            "DEIXAR O(A) CLIENTE CIENTE QUE A INSTALAÇÃO SÓ OCORRERÁ APÓS O PAGAMENTOS DOS DÉBITOS E ENTREGA DOS EQUIPAMENTOS EM COMODATO (CASO NÃO TENHAM SIDO REMOVIDOS).\n\n"
            "OPÇÃO 2 - SE O(A) CLIENTE DESEJAR SOMENTE LIQUIDAR O DÉBITO:\n\n"
            f"SERÁ CONCEDIDO 40% DE DESCONTO E O VALOR TOTAL PARA PAGAMENTO FICA EM R$ {format_decimal_brl(resumo.divida_40)}.\n"
            "A NEGOCIAÇÃO PODERÁ SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS À FRENTE.\n"
            "DEIXAR O(A) CLIENTE CIENTE SOBRE A DEVOLUÇÃO DOS EQUIPAMENTOS EM COMODATO (CASO NÃO TENHAM SIDO REMOVIDOS).\n\n"
            "> SE O(A) CLIENTE ALEGAR PERDA/DANO, VERIFICAR COM O SETOR DE FATURAMENTO UMA NOVA NEGOCIAÇÃO."
        )


class _NoOpBrowserAutomation:
    def __enter__(self) -> "_NoOpBrowserAutomation":
        LOGGER.info("Modo sem navegador ativo. As etapas Web do Hubsoft serao ignoradas.")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def add_observation(self, id_cliente: int, protocolo: str) -> None:
        LOGGER.info(
            "Skip-browser: observacao do cliente %s com protocolo %s foi ignorada neste teste.",
            id_cliente,
            protocolo,
        )
