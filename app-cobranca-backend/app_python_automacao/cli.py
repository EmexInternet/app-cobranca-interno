from __future__ import annotations

import argparse
import logging
from datetime import date
import httpx

from app_python_automacao.error_reporter import ErrorReporter, PhaseStatusEntry
from app_python_automacao.logging_utils import setup_logging
from app_python_automacao.settings import Settings
from app_python_automacao.whatsapp_api import WhatsAppApiClient, WhatsAppHsmError
from app_python_automacao.workflow import CobrancaWorkflow

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app_python_automacao",
        description="Automacoes internas da fase 1 do App Cobranca.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    executar = subparsers.add_parser("executar", help="Executa o fluxo completo a partir da API de cancelamentos.")
    executar.add_argument("--dry-run", action="store_true", help="Nao grava alteracoes via API nem no Hubsoft Web.")
    executar.add_argument("--limit", type=int, default=None, help="Limita a quantidade de cancelamentos processados.")
    executar.add_argument("--cliente-id", type=int, default=None, help="Processa apenas um id_cliente especifico.")
    executar.add_argument("--dia-inicio", type=_parse_iso_date, default=None, help="Sobrescreve o dia_inicio da API de cancelamentos no formato YYYY-MM-DD.")
    executar.add_argument("--dia-fim", type=_parse_iso_date, default=None, help="Sobrescreve o dia_fim da API de cancelamentos no formato YYYY-MM-DD.")
    executar.add_argument("--skip-browser", action="store_true", help="Executa somente a parte de API, sem abrir o Chrome.")
    executar.add_argument("--skip-phase-two-close", action="store_true", help="Nao fecha o atendimento de cancelamento na fase 2 e registra o relato de encerramento em massa.")
    executar.add_argument(
        "--skip-phase-two-mass-report",
        action="store_true",
        help="Quando usado com --skip-phase-two-close, nao registra o relato de encerramento em massa.",
    )
    executar.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    atendimento = subparsers.add_parser(
        "atendimento",
        help="Executa o fluxo direto para um cliente_servico especifico, sem consultar a API de cancelamentos.",
    )
    atendimento.add_argument("--cliente-id", type=int, required=True, help="ID do cliente no Hubsoft Web.")
    atendimento.add_argument("--codigo-cliente", type=int, default=None, help="Codigo do cliente vindo da API de cancelamentos.")
    atendimento.add_argument(
        "--cliente-servico-id",
        type=int,
        required=True,
        help="ID do cliente_servico para consulta de atendimentos pendentes.",
    )
    atendimento.add_argument("--nome-cliente", default="MODO TESTE / EXECUCAO DIRETA", help="Nome usado no relato e no disparo do WhatsApp.")
    atendimento.add_argument("--telefone", default=None, help="Telefone do cliente para a fase 3.")
    atendimento.add_argument("--plano", default=None, help="Plano/servico do cliente para a fase 1.1.")
    atendimento.add_argument("--numero-plano", type=int, default=None, help="Numero do plano/servico do cliente para a fase 1.1.")
    atendimento.add_argument("--data-venda", default=None, help="Data da venda para calculo da multa. Aceita DD/MM/YYYY ou YYYY-MM-DD.")
    atendimento.add_argument("--data-cancelamento", default=None, help="Data do cancelamento para calculo da multa. Aceita DD/MM/YYYY ou YYYY-MM-DD.")
    atendimento.add_argument("--dry-run", action="store_true", help="Nao grava alteracoes via API nem no Hubsoft Web.")
    atendimento.add_argument("--skip-browser", action="store_true", help="Executa somente a consulta da API, sem abrir o Chrome.")
    atendimento.add_argument("--skip-phase-two-close", action="store_true", help="Nao fecha o atendimento de cancelamento na fase 2 e registra o relato de encerramento em massa.")
    atendimento.add_argument(
        "--skip-phase-two-mass-report",
        action="store_true",
        help="Quando usado com --skip-phase-two-close, nao registra o relato de encerramento em massa.",
    )
    atendimento.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    fase_1_1 = subparsers.add_parser(
        "fase-1-1",
        help="Executa apenas a fase 1.1 de cobranca/fatura no Hubsoft Web.",
    )
    fase_1_1.add_argument("--cliente-id", type=int, required=True, help="ID do cliente no Hubsoft Web.")
    fase_1_1.add_argument("--codigo-cliente", type=int, default=None, help="Codigo do cliente vindo da API de cancelamentos.")
    fase_1_1.add_argument("--cliente-servico-id", type=int, required=True, help="ID do cliente_servico para registro operacional.")
    fase_1_1.add_argument("--nome-cliente", default="MODO TESTE / FASE 1.1", help="Nome do cliente para registro.")
    fase_1_1.add_argument("--telefone", default=None, help="Telefone do cliente para registro.")
    fase_1_1.add_argument("--plano", required=True, help="Servico / Plano do cliente para a fase 1.1.")
    fase_1_1.add_argument("--numero-plano", type=int, default=None, help="Numero do plano/servico do cliente.")
    fase_1_1.add_argument("--data-venda", required=True, help="Data da venda para calculo da multa. Aceita DD/MM/YYYY ou YYYY-MM-DD.")
    fase_1_1.add_argument("--data-cancelamento", required=True, help="Data do cancelamento para calculo da multa. Aceita DD/MM/YYYY ou YYYY-MM-DD.")
    fase_1_1.add_argument("--dry-run", action="store_true", help="Preenche a automacao sem salvar as cobrancas/faturas.")
    fase_1_1.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    observacao = subparsers.add_parser(
        "observacao",
        help="Adiciona apenas a observacao obrigatoria no cadastro do cliente.",
    )
    observacao.add_argument("--cliente-id", type=int, required=True, help="ID do cliente no Hubsoft Web.")
    observacao.add_argument("--protocolo", required=True, help="Protocolo a ser escrito na observacao.")
    observacao.add_argument("--dry-run", action="store_true", help="Nao clica em salvar no Hubsoft Web.")
    observacao.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    whatsapp = subparsers.add_parser(
        "whatsapp-hsm",
        help="Testa apenas o envio do HSM de WhatsApp, sem executar as fases 1 e 2.",
    )
    whatsapp.add_argument("--nome-cliente", required=True, help="Nome que sera enviado na variavel do HSM.")
    whatsapp.add_argument("--telefone", required=True, help="Telefone do cliente para envio do HSM.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = Settings.load()
    setup_logging(settings.log_dir, settings.log_level)
    workflow = CobrancaWorkflow(settings)

    LOGGER.info("Comando selecionado: %s", args.command)

    if args.command == "executar":
        report = workflow.run_full(
            dry_run=args.dry_run,
            limit=args.limit,
            only_cliente_id=args.cliente_id,
            dia_inicio=args.dia_inicio,
            dia_fim=args.dia_fim,
            skip_browser=args.skip_browser,
            skip_phase_two_close=args.skip_phase_two_close,
            skip_phase_two_mass_report=args.skip_phase_two_mass_report,
            headless=not args.headful,
        )
        LOGGER.info("Execucao finalizada. %s", report.to_log_message())
        return 0

    if args.command == "atendimento":
        report = workflow.run_single_service(
            id_cliente=args.cliente_id,
            codigo_cliente=args.codigo_cliente,
            id_cliente_servico=args.cliente_servico_id,
            nome_cliente=args.nome_cliente,
            telefone=args.telefone,
            plano=args.plano,
            numero_plano=args.numero_plano,
            data_venda=args.data_venda,
            data_cancelamento=args.data_cancelamento,
            dry_run=args.dry_run,
            skip_browser=args.skip_browser,
            skip_phase_two_close=args.skip_phase_two_close,
            skip_phase_two_mass_report=args.skip_phase_two_mass_report,
            headless=not args.headful,
        )
        LOGGER.info("Execucao finalizada. %s", report.to_log_message())
        return 0

    if args.command == "observacao":
        workflow.add_observation_only(
            id_cliente=args.cliente_id,
            protocolo=args.protocolo,
            dry_run=args.dry_run,
            headless=not args.headful,
        )
        LOGGER.info("Observacao concluida para cliente %s.", args.cliente_id)
        return 0

    if args.command == "fase-1-1":
        error_reporter = ErrorReporter()
        try:
            status = workflow.run_phase_one_point_one_only(
                id_cliente=args.cliente_id,
                codigo_cliente=args.codigo_cliente,
                id_cliente_servico=args.cliente_servico_id,
                nome_cliente=args.nome_cliente,
                telefone=args.telefone,
                plano=args.plano,
                numero_plano=args.numero_plano,
                data_venda=args.data_venda,
                data_cancelamento=args.data_cancelamento,
                dry_run=args.dry_run,
                headless=not args.headful,
            )
        except Exception as exc:
            error_reporter.append(
                cancelamento=None,
                nome_cliente=args.nome_cliente,
                telefone=args.telefone,
                status=PhaseStatusEntry(
                    fase_1="nao_aplicavel",
                    fase_1_1="erro",
                    fase_2="nao_aplicavel",
                    fase_3="nao_aplicavel",
                    erro="erro na fase 1.1",
                    detalhe=str(exc),
                ),
            )
            LOGGER.exception("Execucao isolada da fase 1.1 falhou para cliente %s.", args.cliente_id)
            return 1

        LOGGER.info("Fase 1.1 concluida para cliente %s com status=%s.", args.cliente_id, status)
        return 0

    if args.command == "whatsapp-hsm":
        whatsapp_client = WhatsAppApiClient(settings)
        error_reporter = ErrorReporter()
        try:
            enviado = whatsapp_client.send_phase_three_hsm(
                nome_cliente=args.nome_cliente,
                telefone=args.telefone,
            )
        except WhatsAppHsmError as exc:
            error_reporter.append(
                cancelamento=None,
                nome_cliente=args.nome_cliente,
                telefone=args.telefone,
                status=PhaseStatusEntry(
                    fase_1="nao_aplicavel",
                    fase_1_1="nao_aplicavel",
                    fase_2="nao_aplicavel",
                    fase_3="erro",
                    erro=exc.message,
                    codigo_erro=exc.cod_error,
                    detalhe=f"status_http={exc.status_code}",
                ),
            )
            LOGGER.error(
                "Teste de HSM falhou para %s. cod_error=%s msg=%s",
                args.nome_cliente,
                exc.cod_error,
                exc.message,
            )
            return 1
        except httpx.HTTPError as exc:
            error_reporter.append(
                cancelamento=None,
                nome_cliente=args.nome_cliente,
                telefone=args.telefone,
                status=PhaseStatusEntry(
                    fase_1="nao_aplicavel",
                    fase_1_1="nao_aplicavel",
                    fase_2="nao_aplicavel",
                    fase_3="erro",
                    erro="falha http no envio do hsm",
                    detalhe=str(exc),
                ),
            )
            LOGGER.error("Teste de HSM falhou para %s. detalhe=%s", args.nome_cliente, exc)
            return 1
        if enviado:
            LOGGER.info("Teste de HSM concluido com sucesso para %s.", args.nome_cliente)
            return 0
        LOGGER.warning("Teste de HSM nao foi enviado para %s.", args.nome_cliente)
        return 1

    parser.error("Comando invalido.")
    return 2


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use o formato YYYY-MM-DD.") from exc
