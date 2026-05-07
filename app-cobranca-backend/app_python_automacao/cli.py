from __future__ import annotations

import argparse
import logging

from app_python_automacao.logging_utils import setup_logging
from app_python_automacao.settings import Settings
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
    executar.add_argument("--skip-browser", action="store_true", help="Executa somente a parte de API, sem abrir o Chrome.")
    executar.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    atendimento = subparsers.add_parser(
        "atendimento",
        help="Executa o fluxo direto para um cliente_servico especifico, sem consultar a API de cancelamentos.",
    )
    atendimento.add_argument("--cliente-id", type=int, required=True, help="ID do cliente no Hubsoft Web.")
    atendimento.add_argument(
        "--cliente-servico-id",
        type=int,
        required=True,
        help="ID do cliente_servico para consulta de atendimentos pendentes.",
    )
    atendimento.add_argument("--dry-run", action="store_true", help="Nao grava alteracoes via API nem no Hubsoft Web.")
    atendimento.add_argument("--skip-browser", action="store_true", help="Executa somente a consulta da API, sem abrir o Chrome.")
    atendimento.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

    observacao = subparsers.add_parser(
        "observacao",
        help="Adiciona apenas a observacao obrigatoria no cadastro do cliente.",
    )
    observacao.add_argument("--cliente-id", type=int, required=True, help="ID do cliente no Hubsoft Web.")
    observacao.add_argument("--protocolo", required=True, help="Protocolo a ser escrito na observacao.")
    observacao.add_argument("--dry-run", action="store_true", help="Nao clica em salvar no Hubsoft Web.")
    observacao.add_argument("--headful", action="store_true", help="Abre o Chrome com interface visual.")

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
            skip_browser=args.skip_browser,
            headless=not args.headful,
        )
        LOGGER.info("Execucao finalizada. %s", report.to_log_message())
        return 0

    if args.command == "atendimento":
        report = workflow.run_single_service(
            id_cliente=args.cliente_id,
            id_cliente_servico=args.cliente_servico_id,
            dry_run=args.dry_run,
            skip_browser=args.skip_browser,
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

    parser.error("Comando invalido.")
    return 2
