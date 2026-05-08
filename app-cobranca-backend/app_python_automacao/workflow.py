from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx

from app_python_automacao.browser_automation import HubsoftBrowserAutomation
from app_python_automacao.cancelamentos_api import CancelamentosClient
from app_python_automacao.error_reporter import ErrorReporter, PhaseStatusEntry
from app_python_automacao.hubsoft_api import HubsoftApiClient
from app_python_automacao.legacy_billing import LegacyBillingRunner
from app_python_automacao.models import CancelamentoRecord, HubsoftAtendimento, WorkflowReport
from app_python_automacao.multa_rescisoria import MultaRescisoriaCalculator, format_decimal_brl
from app_python_automacao.processing_state import ProcessingStateStore
from app_python_automacao.settings import Settings
from app_python_automacao.utils import (
    build_negotiation_summary,
    compute_cancelamentos_window,
    filter_cancelamentos,
    filter_faturas_by_detalhamento,
)
from app_python_automacao.whatsapp_api import WhatsAppApiClient, WhatsAppHsmError

LOGGER = logging.getLogger(__name__)


RELATO_ENCERRAMENTO_FASE_1 = (
    "TENTATIVAS DE CONTATO PARA NEGOCIACAO SEM SUCESSO.\n\n"
    "> CONTRATO CANCELADO POR INADIMPLENCIA.\n"
)

RELATO_FASE_2_ENCERRAMENTO_EM_MASSA = (
    "ATENDIMENTO NAO SERA FINALIZADO NESTE FLUXO INDIVIDUAL. "
    "SERA ENCERRADO EM MASSA QUANDO NOVO PROCESSO DO FLUXO DE RETIRADA FOR RODADO."
)

RELATO_FASE_2_FALHA_ENCERRAMENTO = (
    "ATENDIMENTO NAO PODE SER FINALIZADO DEVIDO O.S EM ABERTO - "
    "SERA FINALIZADO EM MASSA QUANDO NOVO PROCESSO DO FLUXO DE RETIRADA FOR RODADO"
)


class CobrancaWorkflow:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cancelamentos_client = CancelamentosClient(settings)
        self.hubsoft_client = HubsoftApiClient(settings)
        self.whatsapp_client = WhatsAppApiClient(settings)
        self.error_reporter = ErrorReporter()
        self.processing_state = ProcessingStateStore()
        self.legacy_billing_runner: LegacyBillingRunner | None = None

    def run_full(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        only_cliente_id: int | None = None,
        dia_inicio: date | None = None,
        dia_fim: date | None = None,
        skip_browser: bool = False,
        skip_phase_two_close: bool = False,
        headless: bool = True,
    ) -> WorkflowReport:
        if dia_inicio is None or dia_fim is None:
            auto_dia_inicio, auto_dia_fim = compute_cancelamentos_window(date.today())
            dia_inicio = dia_inicio or self.processing_state.get_next_dia_inicio(auto_dia_inicio)
            dia_fim = dia_fim or auto_dia_fim

        cancelamentos = self.cancelamentos_client.fetch_cancelamentos(dia_inicio, dia_fim)
        report = WorkflowReport(total_cancelamentos_lidos=len(cancelamentos))

        elegiveis_base = [
            item
            for item in filter_cancelamentos(cancelamentos, self.settings.motivo_cancelamento_alvo)
            if only_cliente_id is None or item.id_cliente == only_cliente_id
        ]

        elegiveis = [item for item in elegiveis_base if not self.processing_state.is_processed(item)]
        report.total_clientes_ja_processados = len(elegiveis_base) - len(elegiveis)
        if report.total_clientes_ja_processados:
            LOGGER.info(
                "%s clientes ja processados foram ignorados por persistencia local.",
                report.total_clientes_ja_processados,
            )

        if limit is not None:
            elegiveis = elegiveis[:limit]

        report.total_cancelamentos_processados = len(elegiveis)
        if not elegiveis:
            LOGGER.warning("Nenhum cancelamento elegivel encontrado para processar.")
            if not dry_run:
                self.processing_state.update_last_dia_fim(dia_fim)
            return report

        report = self._process_cancelamentos(
            elegiveis,
            dry_run=dry_run,
            skip_browser=skip_browser,
            skip_phase_two_close=skip_phase_two_close,
            headless=headless,
            base_report=report,
        )
        if not dry_run:
            self.processing_state.update_last_dia_fim(dia_fim)
        return report

    def run_single_service(
        self,
        id_cliente: int,
        codigo_cliente: int | None,
        id_cliente_servico: int,
        nome_cliente: str = "MODO TESTE / EXECUCAO DIRETA",
        telefone: str | None = None,
        plano: str | None = None,
        numero_plano: int | None = None,
        data_venda: str | None = None,
        data_cancelamento: str | None = None,
        dry_run: bool = False,
        skip_browser: bool = False,
        skip_phase_two_close: bool = False,
        headless: bool = True,
    ) -> WorkflowReport:
        cancelamento = CancelamentoRecord(
            codigo_cliente=codigo_cliente or self.settings.teste_codigo_cliente,
            id_cliente=id_cliente,
            id_cliente_servico=id_cliente_servico,
            nome_razaosocial=nome_cliente,
            telefone_primario=telefone,
            plano=plano,
            numero_plano=numero_plano,
            data_venda=data_venda,
            data_cancelamento=data_cancelamento,
            motivo_cancelamento=self.settings.motivo_cancelamento_alvo,
        )
        report = WorkflowReport(total_cancelamentos_lidos=1, total_cancelamentos_processados=1)
        return self._process_cancelamentos(
            [cancelamento],
            dry_run=dry_run,
            skip_browser=skip_browser,
            skip_phase_two_close=skip_phase_two_close,
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
        skip_phase_two_close: bool,
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
                fase_1_status = "nao_iniciada"
                fase_1_1_status = "nao_iniciada"
                fase_2_status = "nao_iniciada"
                fase_3_status = "nao_iniciada"
                try:
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
                            "Dry-run fase 1: atendimento %s de cobranca seria relatado e fechado. "
                            "O protocolo da observacao sera definido apos consultar o atendimento de cancelamento.",
                            atendimento.id_atendimento,
                        )
                        fase_1_status = "dry_run"
                    else:
                        self.hubsoft_client.add_message(
                            atendimento.id_atendimento,
                            RELATO_ENCERRAMENTO_FASE_1,
                        )
                        self.hubsoft_client.close_atendimento(atendimento.id_atendimento)
                        base_report.total_atendimentos_fechados += 1
                        fase_1_status = "sucesso"

                    try:
                        fase_1_1_status = self._process_phase_one_point_one(
                            cancelamento=cancelamento,
                            dry_run=dry_run,
                            skip_browser=skip_browser,
                            headless=headless,
                        )
                    except Exception as exc:
                        fase_1_1_status = "erro"
                        self.error_reporter.append(
                            cancelamento=cancelamento,
                            status=PhaseStatusEntry(
                                fase_1=fase_1_status,
                                fase_1_1=fase_1_1_status,
                                fase_2="nao_iniciada",
                                fase_3="nao_iniciada",
                                erro="erro na fase 1.1",
                                detalhe=str(exc),
                            ),
                        )
                        LOGGER.exception(
                            "Erro na fase 1.1 para cliente %s / cliente_servico %s. O fluxo seguira para observacao e fase 2.",
                            cancelamento.id_cliente,
                            cancelamento.id_cliente_servico,
                        )

                    atendimentos_cancelamento = self.hubsoft_client.get_pending_cancelamento_inadimplencia(
                        cancelamento.id_cliente_servico,
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

                    fase_2_status, fase_3_status = self._process_cancelamento_phase_two(
                        cancelamento=cancelamento,
                        atendimentos=atendimentos_cancelamento,
                        dry_run=dry_run,
                        skip_phase_two_close=skip_phase_two_close,
                        base_report=base_report,
                    )
                except Exception as exc:
                    self.error_reporter.append(
                        cancelamento=cancelamento,
                        status=PhaseStatusEntry(
                            fase_1=fase_1_status,
                            fase_1_1=fase_1_1_status,
                            fase_2=fase_2_status,
                            fase_3=fase_3_status,
                            erro="erro inesperado no fluxo do cliente",
                            detalhe=str(exc),
                        ),
                    )
                    LOGGER.exception(
                        "Erro ao processar cliente %s / cliente_servico %s. O fluxo seguira para o proximo cliente.",
                        cancelamento.id_cliente,
                        cancelamento.id_cliente_servico,
                    )
                finally:
                    if not dry_run:
                        self.processing_state.mark_processed(
                            cancelamento,
                            fase_1=fase_1_status,
                            fase_1_1=fase_1_1_status,
                            fase_2=fase_2_status,
                            fase_3=fase_3_status,
                        )

        return base_report

    def _process_cancelamento_phase_two(
        self,
        cancelamento: CancelamentoRecord,
        atendimentos: list[HubsoftAtendimento] | None,
        dry_run: bool,
        skip_phase_two_close: bool,
        base_report: WorkflowReport,
    ) -> tuple[str, str]:
        atendimentos = atendimentos or []
        if not atendimentos:
            base_report.total_sem_atendimento_cancelamento += 1
            LOGGER.warning(
                "Nenhum atendimento de cancelamento por inadimplencia pendente encontrado para cliente_servico %s.",
                cancelamento.id_cliente_servico,
            )
            return "sem_atendimento_cancelamento", "nao_iniciada"

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
                "Dry-run fase 2: atendimento %s seria relatado%s. "
                "faturas_consideradas=%s valor_multa=R$ %s total_divida=R$ %s",
                atendimento.id_atendimento,
                " e fechado" if not skip_phase_two_close else " e ficaria pendente para encerramento em massa",
                resumo.quantidade_faturas_consideradas,
                format_decimal_brl(resumo.valor_multa),
                format_decimal_brl(resumo.total_divida),
            )
            return "dry_run", "nao_iniciada"

        self.hubsoft_client.add_message(atendimento.id_atendimento, mensagem)
        if skip_phase_two_close:
            LOGGER.info(
                "Encerramento da fase 2 foi pulado para o atendimento %s. Relato de massa sera registrado.",
                atendimento.id_atendimento,
            )
            self.hubsoft_client.add_message(atendimento.id_atendimento, RELATO_FASE_2_ENCERRAMENTO_EM_MASSA)
        else:
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
                    RELATO_FASE_2_FALHA_ENCERRAMENTO,
                )

        fase_3_status = self._process_phase_three_whatsapp(cancelamento, base_report)
        return "sucesso", fase_3_status

    def _process_phase_one_point_one(
        self,
        *,
        cancelamento: CancelamentoRecord,
        dry_run: bool,
        skip_browser: bool,
        headless: bool,
    ) -> str:
        if not self.settings.phase_1_1_enabled:
            LOGGER.info("Fase 1.1 desabilitada por configuracao.")
            return "desabilitada"

        if skip_browser:
            LOGGER.info("Fase 1.1 ignorada por skip-browser para cliente %s.", cancelamento.id_cliente)
            return "ignorada_skip_browser"

        if self.legacy_billing_runner is None:
            self.legacy_billing_runner = LegacyBillingRunner(self.settings)

        result = self.legacy_billing_runner.run_phase_one_one(
            cancelamento=cancelamento,
            dry_run=dry_run,
            headless=headless,
        )
        LOGGER.info(
            "Fase 1.1 concluida para cliente %s. multa=R$ %s cobranca_principal=%s cobranca_equipamento=%s dry_run=%s",
            cancelamento.id_cliente,
            format_decimal_brl(Decimal(str(result.fine_value))),
            result.principal_charge_created,
            result.equipment_charge_created,
            dry_run,
        )
        return "dry_run" if dry_run else "sucesso"

    def _process_phase_three_whatsapp(
        self,
        cancelamento: CancelamentoRecord,
        base_report: WorkflowReport,
    ) -> str:
        if not self.whatsapp_client.is_enabled():
            base_report.total_whatsapp_ignorado += 1
            LOGGER.info("Fase 3 de WhatsApp desabilitada. Cliente %s sera ignorado.", cancelamento.id_cliente)
            return "ignorado_desabilitado"

        try:
            enviado = self.whatsapp_client.send_phase_three_hsm(
                nome_cliente=cancelamento.nome_razaosocial,
                telefone=cancelamento.telefone_primario,
            )
        except WhatsAppHsmError as exc:
            base_report.total_whatsapp_falhou += 1
            self.error_reporter.append(
                cancelamento=cancelamento,
                status=PhaseStatusEntry(
                    fase_1="sucesso",
                    fase_1_1="sucesso",
                    fase_2="sucesso",
                    fase_3="erro",
                    erro=exc.message,
                    codigo_erro=exc.cod_error,
                    detalhe=f"status_http={exc.status_code}",
                ),
            )
            LOGGER.error(
                "Falha ao enviar WhatsApp da fase 3 para cliente %s. cod_error=%s msg=%s",
                cancelamento.id_cliente,
                exc.cod_error,
                exc.message,
            )
            return "erro"
        except httpx.HTTPError as exc:
            base_report.total_whatsapp_falhou += 1
            self.error_reporter.append(
                cancelamento=cancelamento,
                status=PhaseStatusEntry(
                    fase_1="sucesso",
                    fase_1_1="sucesso",
                    fase_2="sucesso",
                    fase_3="erro",
                    erro="falha http no envio do hsm",
                    detalhe=str(exc),
                ),
            )
            LOGGER.exception(
                "Falha HTTP ao enviar WhatsApp da fase 3 para cliente %s.",
                cancelamento.id_cliente,
            )
            return "erro"

        if enviado:
            base_report.total_whatsapp_enviado += 1
            return "sucesso"
        else:
            base_report.total_whatsapp_ignorado += 1
            return "ignorado"

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
            "> CONTRATO CANCELADO POR INADIMPLENCIA.\n"
            "> MENSAGEM FINANCEIRA REGISTRADA PARA TRATATIVA.\n\n"
            f"VALOR TOTAL DA DIVIDA: R$ {format_decimal_brl(resumo.total_divida)}\n\n"
            "CASO O(A) CLIENTE ENTRE EM CONTATO, FAVOR INFORMAR SOBRE A PENDENCIA FINANCEIRA EM ABERTO E NEGOCIACOES DISPONIVEIS:\n\n"
            "OPCAO 1 - SE O(A) CLIENTE DESEJAR RETORNAR COM O SERVICO:\n\n"
            f"FICARA ISENTO DA MULTA RESCISORIA E O VALOR DO DEBITO PASSA A SER R$ {format_decimal_brl(resumo.divida_sem_multa)}.\n"
            f"SERA CONCEDIDO 50% DE DESCONTO E O VALOR PARA PAGAMENTO FICA EM R$ {format_decimal_brl(resumo.divida_sem_multa_50)} + TAXA DE ATIVACAO (SUJEITO A AVALIACAO).\n"
            "A NEGOCIACAO PODERA SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS A FRENTE.\n"
            "DEIXAR O(A) CLIENTE CIENTE QUE A INSTALACAO SO OCORRERA APOS O PAGAMENTO DOS DEBITOS E ENTREGA DOS EQUIPAMENTOS EM COMODATO (CASO NAO TENHAM SIDO REMOVIDOS).\n\n"
            "OPCAO 2 - SE O(A) CLIENTE DESEJAR SOMENTE LIQUIDAR O DEBITO:\n\n"
            f"SERA CONCEDIDO 40% DE DESCONTO E O VALOR TOTAL PARA PAGAMENTO FICA EM R$ {format_decimal_brl(resumo.divida_40)}.\n"
            "A NEGOCIACAO PODERA SER PAGA POR BOLETO OU NA LOJA COM VENCIMENTO PARA 3 DIAS A FRENTE.\n"
            "DEIXAR O(A) CLIENTE CIENTE SOBRE A DEVOLUCAO DOS EQUIPAMENTOS EM COMODATO (CASO NAO TENHAM SIDO REMOVIDOS).\n\n"
            "> SE O(A) CLIENTE ALEGAR PERDA/DANO, VERIFICAR COM O SETOR DE FATURAMENTO UMA NOVA NEGOCIACAO."
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
