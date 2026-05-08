from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class Settings:
    emex_api_url: str = os.getenv("EMEX_API_URL", "https://api.emex.hubsoft.com.br").rstrip("/")
    emex_api_port: str = os.getenv("EMEX_API_PORT", "443")
    emex_client_id: str = os.getenv("EMEX_CLIENT_ID", "")
    emex_client_secret: str = os.getenv("EMEX_CLIENT_SECRET", "")
    emex_username: str = os.getenv("EMEX_USERNAME", "")
    emex_password: str = os.getenv("EMEX_PASSWORD", "")

    hubsoft_web_base_url: str = os.getenv("HUBSOFT_WEB_BASE_URL", "https://emex.hubsoft.com.br").rstrip("/")
    hubsoft_web_username: str = os.getenv("HUBSOFT_WEB_USERNAME", "")
    hubsoft_web_password: str = os.getenv("HUBSOFT_WEB_PASSWORD", "")
    cancelados_api_url: str = os.getenv("CANCELADOS_API_URL", "http://200.229.156.16:3002").rstrip("/")
    cancelados_start_date: str = os.getenv("CANCELADOS_START_DATE", "").strip()
    cancelados_auth_type: str = os.getenv("CANCELADOS_AUTH_TYPE", "header").strip().lower()
    cancelados_username: str = os.getenv("CANCELADOS_USERNAME", "").strip()
    cancelados_password: str = os.getenv("CANCELADOS_PASSWORD", "").strip()
    cancelados_auth_header: str = os.getenv("CANCELADOS_AUTH_HEADER", "x-api-key").strip()
    cancelados_auth_query_param: str = os.getenv("CANCELADOS_AUTH_QUERY_PARAM", "senha").strip()

    browser: str = os.getenv("BROWSER", "chrome").strip().lower()
    browser_binary_path: str = os.getenv("BROWSER_BINARY_PATH", "").strip()
    browser_profile_dir: str = os.getenv("BROWSER_PROFILE_DIR", ".selenium-profile").strip()
    browser_profile_name: str = os.getenv("BROWSER_PROFILE_NAME", "Default").strip() or "Default"
    headless: bool = _as_bool(os.getenv("HEADLESS"), default=False)
    selenium_timeout: int = int(os.getenv("SELENIUM_TIMEOUT", "30"))
    selenium_validation_interval: int = int(os.getenv("SELENIUM_VALIDATION_INTERVAL", "10"))
    selenium_max_wait: int = int(os.getenv("SELENIUM_MAX_WAIT", "60"))
    default_id_cliente: int = int(os.getenv("DEFAULT_ID_CLIENTE", "44847"))
    default_valor_cobranca: float = float(os.getenv("DEFAULT_VALOR_COBRANCA", "10"))
    default_descricao_cobranca: str = os.getenv("DEFAULT_DESCRICAO_COBRANCA", "MULTA RESCISORIA")
    default_tipo_servico_cobranca: str = os.getenv("DEFAULT_TIPO_SERVICO_COBRANCA", "MULTA RESCISORIA").strip()
    default_forma_cobranca: str = os.getenv("DEFAULT_FORMA_COBRANCA", "BOLETO INTERNO - EMEX").strip()
    equipment_charge_description: str = os.getenv(
        "EQUIPMENT_CHARGE_DESCRIPTION",
        "MULTA DE EQUIPAMENTO EM COMODATO",
    ).strip()
    equipment_charge_service_type: str = os.getenv(
        "EQUIPMENT_CHARGE_SERVICE_TYPE",
        "EQUIPAMENTO EM COMODATO",
    ).strip()
    equipment_charge_value: float = float(os.getenv("EQUIPMENT_CHARGE_VALUE", "300"))
    multa_benefit_value: float = float(os.getenv("MULTA_BENEFIT_VALUE", "600"))
    multa_cli_script: str = os.getenv("MULTA_CLI_SCRIPT", "scripts/calculate_multa.js").strip()
    withdrawal_state_file: str = os.getenv("WITHDRAWAL_STATE_FILE", "state/withdrawal_state.json").strip()
    withdrawal_errors_file: str = os.getenv("WITHDRAWAL_ERRORS_FILE", "logs/withdrawal_errors.csv").strip()
    withdrawal_processed_file: str = os.getenv("WITHDRAWAL_PROCESSED_FILE", "logs/withdrawal_processed.csv").strip()
    atendimento_descricao: str = os.getenv(
        "ATENDIMENTO_DESCRICAO",
        "RETIRADA DE EQUIPAMENTOS EM COMODATO",
    ).strip()
    atendimento_mensagem: str = os.getenv(
        "ATENDIMENTO_MENSAGEM",
        "ATENDIMENTO DE RETIRADA GERADO AUTOMATICAMENTE APOS CLIENTE CANCELADO",
    ).strip()
    atendimento_tipo_ordem_servico: int = int(os.getenv("ATENDIMENTO_TIPO_ORDEM_SERVICO", "5"))
    atendimento_ids_tecnicos: int = int(os.getenv("ATENDIMENTO_IDS_TECNICOS", "189"))
    atendimento_tipo_atendimento: int = int(os.getenv("ATENDIMENTO_TIPO_ATENDIMENTO", "707"))
    atendimento_status: int = int(os.getenv("ATENDIMENTO_STATUS", "1"))
    atendimento_usuario_responsavel: int = int(os.getenv("ATENDIMENTO_USUARIO_RESPONSAVEL", "730"))
    atendimento_origem_contato: int = int(os.getenv("ATENDIMENTO_ORIGEM_CONTATO", "15"))

    @property
    def emex_api_base_url(self) -> str:
        return f"{self.emex_api_url}:{self.emex_api_port}"

    @property
    def withdrawal_state_path(self) -> Path:
        return Path(self.withdrawal_state_file)

    @property
    def withdrawal_errors_path(self) -> Path:
        return Path(self.withdrawal_errors_file)

    @property
    def withdrawal_processed_path(self) -> Path:
        return Path(self.withdrawal_processed_file)

    @property
    def resolved_cancelados_start_date(self) -> str:
        return self.cancelados_start_date or date.today().isoformat()

    @property
    def resolved_web_username(self) -> str:
        return self.hubsoft_web_username or self.emex_username

    @property
    def resolved_web_password(self) -> str:
        return self.hubsoft_web_password or self.emex_password

    def validate_api_credentials(self) -> None:
        required = {
            "EMEX_CLIENT_ID": self.emex_client_id,
            "EMEX_CLIENT_SECRET": self.emex_client_secret,
            "EMEX_USERNAME": self.emex_username,
            "EMEX_PASSWORD": self.emex_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Variaveis ausentes para a API: {', '.join(missing)}")

    def validate_web_credentials(self) -> None:
        required = {
            "HUBSOFT_WEB_USERNAME/EMEX_USERNAME": self.resolved_web_username,
            "HUBSOFT_WEB_PASSWORD/EMEX_PASSWORD": self.resolved_web_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Variaveis ausentes para o login web: {', '.join(missing)}")


settings = Settings()
