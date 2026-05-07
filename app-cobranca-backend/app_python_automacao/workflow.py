from __future__ import annotations

import logging
from datetime import date

from app_python_automacao.browser_automation import HubsoftBrowserAutomation
from app_python_automacao.cancelamentos_api import CancelamentosClient
from app_python_automacao.hubsoft_api import HubsoftApiClient
from app_python_automacao.models import CancelamentoRecord, WorkflowReport
from app_python_automacao.settings import Settings
from app_python_automacao.utils import compute_cancelamentos_window, filter_cancelamentos

LOGGER = logging.getLogger(__name__)


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
        skip_browser: bool = False,
        headless: bool = True,
    ) -> WorkflowReport:
        dia_inicio, dia_fim = compute_cancelamentos_window(date.today())
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
                        self.settings.relato_encerramento,
                    )
                    self.hubsoft_client.close_atendimento(atendimento.id_atendimento)
                    base_report.total_atendimentos_fechados += 1

                browser.add_observation(
                    id_cliente=cancelamento.id_cliente,
                    protocolo=atendimento.protocolo,
                )
                base_report.total_observacoes_salvas += 0 if dry_run else 1

        return base_report


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
