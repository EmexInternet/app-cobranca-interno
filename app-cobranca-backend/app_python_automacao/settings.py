from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class Settings:
    cancelamentos_api_url: str
    cancelamentos_api_key: str
    hubsoft_api_url: str
    hubsoft_api_port: int
    hubsoft_client_id: str
    hubsoft_client_secret: str
    hubsoft_username: str
    hubsoft_password: str
    hubsoft_web_url: str
    hubsoft_web_email: str
    hubsoft_web_password: str
    hubsoft_chrome_binary_path: str
    hubsoft_storage_dir: str
    hubsoft_storage_state: str
    hubsoft_login_post_enter_wait_ms: int
    hubsoft_login_timeout_ms: int
    hubsoft_observacao_post_save_wait_ms: int
    hubsoft_element_timeout_seconds: int
    log_level: str
    log_dir: str
    timezone: str
    motivo_cancelamento_alvo: str
    tipo_atendimento_alvo: str
    id_motivo_fechamento_atendimento: int
    descricao_fechamento_atendimento: str
    status_fechamento_atendimento: str
    tipo_atendimento_cancelamento_alvo: str
    financeiro_descricoes_ignoradas: list[str]
    multa_rescisoria_valor_beneficio_padrao: str
    phase_1_1_enabled: bool
    legacy_browser: str
    legacy_browser_profile_dir: str
    legacy_browser_profile_name: str
    legacy_selenium_timeout: int
    legacy_selenium_validation_interval: int
    legacy_selenium_max_wait: int
    legacy_default_descricao_cobranca: str
    legacy_default_tipo_servico_cobranca: str
    legacy_default_forma_cobranca: str
    legacy_multa_cli_script: str
    legacy_equipment_charge_service_type: str
    legacy_equipment_charge_description: str
    legacy_equipment_charge_value: float
    whatsapp_api_enabled: bool
    whatsapp_api_url: str
    whatsapp_api_token: str
    whatsapp_cod_conta: int
    whatsapp_hsm_id: int
    whatsapp_tipo_envio: int
    whatsapp_country_code: str
    teste_codigo_cliente: int
    teste_id_cliente: int

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")

        settings = cls(
            cancelamentos_api_url=os.getenv("CANCELAMENTOS_API_URL", "http://200.229.156.16:3002"),
            cancelamentos_api_key=os.getenv("CANCELAMENTOS_API_KEY", ""),
            hubsoft_api_url=os.getenv("HUBSOFT_API_URL", "https://api.emex.hubsoft.com.br"),
            hubsoft_api_port=int(os.getenv("HUBSOFT_API_PORT", "443")),
            hubsoft_client_id=os.getenv("HUBSOFT_CLIENT_ID", ""),
            hubsoft_client_secret=os.getenv("HUBSOFT_CLIENT_SECRET", ""),
            hubsoft_username=os.getenv("HUBSOFT_USERNAME", ""),
            hubsoft_password=os.getenv("HUBSOFT_PASSWORD", ""),
            hubsoft_web_url=os.getenv("HUBSOFT_WEB_URL", "https://emex.hubsoft.com.br"),
            hubsoft_web_email=os.getenv("HUBSOFT_WEB_EMAIL", ""),
            hubsoft_web_password=os.getenv("HUBSOFT_WEB_PASSWORD", ""),
            hubsoft_chrome_binary_path=os.getenv("HUBSOFT_CHROME_BINARY_PATH", ""),
            hubsoft_storage_dir=os.getenv("HUBSOFT_STORAGE_DIR", str(BASE_DIR / "storage" / "browser-profile")),
            hubsoft_storage_state=os.getenv("HUBSOFT_STORAGE_STATE", str(BASE_DIR / "storage" / "hubsoft-state.json")),
            hubsoft_login_post_enter_wait_ms=int(os.getenv("HUBSOFT_LOGIN_POST_ENTER_WAIT_MS", "6000")),
            hubsoft_login_timeout_ms=int(os.getenv("HUBSOFT_LOGIN_TIMEOUT_MS", "20000")),
            hubsoft_observacao_post_save_wait_ms=int(
                os.getenv("HUBSOFT_OBSERVACAO_POST_SAVE_WAIT_MS")
                or os.getenv("HUBSOFT_OBSERVACAO_PRE_SAVE_WAIT_MS", "2000")
            ),
            hubsoft_element_timeout_seconds=int(os.getenv("HUBSOFT_ELEMENT_TIMEOUT_SECONDS", "15")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", str(BASE_DIR / "logs")),
            timezone=os.getenv("TIMEZONE", "America/Sao_Paulo"),
            motivo_cancelamento_alvo=os.getenv(
                "MOTIVO_CANCELAMENTO_ALVO",
                "CANCELAMENTO AUTOMATICO INADIMPLENCIA",
            ),
            tipo_atendimento_alvo=os.getenv("TIPO_ATENDIMENTO_ALVO", "COBRANCA"),
            id_motivo_fechamento_atendimento=int(os.getenv("ID_MOTIVO_FECHAMENTO_ATENDIMENTO", "17")),
            descricao_fechamento_atendimento=os.getenv(
                "DESCRICAO_FECHAMENTO_ATENDIMENTO",
                "CONTRATO CANCELADO POR INADIMPLENCIA",
            ),
            status_fechamento_atendimento=os.getenv("STATUS_FECHAMENTO_ATENDIMENTO", "concluido"),
            tipo_atendimento_cancelamento_alvo=os.getenv(
                "TIPO_ATENDIMENTO_CANCELAMENTO_ALVO",
                "CANCELAMENTO INADIMPLENCIA",
            ),
            financeiro_descricoes_ignoradas=_split_csv_env(
                os.getenv(
                    "FINANCEIRO_DESCRICOES_IGNORADAS",
                    "MULTA RESCISORIA,EQUIPAMENTO EM COMODATO",
                )
            ),
            multa_rescisoria_valor_beneficio_padrao=os.getenv("MULTA_RESCISORIA_VALOR_BENEFICIO_PADRAO", "600.00"),
            phase_1_1_enabled=_parse_bool(os.getenv("PHASE_1_1_ENABLED", "true")),
            legacy_browser=os.getenv("LEGACY_BROWSER", "chrome").strip().lower(),
            legacy_browser_profile_dir=os.getenv(
                "LEGACY_BROWSER_PROFILE_DIR",
                str(BASE_DIR / "storage" / "legacy-chromium-profile"),
            ),
            legacy_browser_profile_name=os.getenv("LEGACY_BROWSER_PROFILE_NAME", "Default").strip() or "Default",
            legacy_selenium_timeout=int(os.getenv("LEGACY_SELENIUM_TIMEOUT", "30")),
            legacy_selenium_validation_interval=int(os.getenv("LEGACY_SELENIUM_VALIDATION_INTERVAL", "10")),
            legacy_selenium_max_wait=int(os.getenv("LEGACY_SELENIUM_MAX_WAIT", "60")),
            legacy_default_descricao_cobranca=os.getenv(
                "LEGACY_DEFAULT_DESCRICAO_COBRANCA",
                "MULTA RESCISORIA",
            ),
            legacy_default_tipo_servico_cobranca=os.getenv(
                "LEGACY_DEFAULT_TIPO_SERVICO_COBRANCA",
                "MULTA RESCISORIA",
            ),
            legacy_default_forma_cobranca=os.getenv(
                "LEGACY_DEFAULT_FORMA_COBRANCA",
                "BOLETO INTERNO - EMEX",
            ),
            legacy_multa_cli_script=os.getenv("LEGACY_MULTA_CLI_SCRIPT", ""),
            legacy_equipment_charge_service_type=os.getenv(
                "LEGACY_EQUIPMENT_CHARGE_SERVICE_TYPE",
                "EQUIPAMENTO EM COMODATO",
            ),
            legacy_equipment_charge_description=os.getenv(
                "LEGACY_EQUIPMENT_CHARGE_DESCRIPTION",
                "MULTA DE EQUIPAMENTO EM COMODATO",
            ),
            legacy_equipment_charge_value=float(os.getenv("LEGACY_EQUIPMENT_CHARGE_VALUE", "300")),
            whatsapp_api_enabled=_parse_bool(os.getenv("WHATSAPP_API_ENABLED", "true")),
            whatsapp_api_url=os.getenv("WHATSAPP_API_URL", "https://emex.matrixdobrasil.ai/rest/v1/sendHsm"),
            whatsapp_api_token=os.getenv("WHATSAPP_API_TOKEN", ""),
            whatsapp_cod_conta=int(os.getenv("WHATSAPP_COD_CONTA", "1")),
            whatsapp_hsm_id=int(os.getenv("WHATSAPP_HSM_ID", "43")),
            whatsapp_tipo_envio=int(os.getenv("WHATSAPP_TIPO_ENVIO", "2")),
            whatsapp_country_code=os.getenv("WHATSAPP_COUNTRY_CODE", "55"),
            teste_codigo_cliente=int(os.getenv("TESTE_CODIGO_CLIENTE", "45098")),
            teste_id_cliente=int(os.getenv("TESTE_ID_CLIENTE", "44847")),
        )
        settings.validate()
        return settings

    @property
    def hubsoft_api_base_url(self) -> str:
        base = self.hubsoft_api_url.rstrip("/")
        if base.endswith(f":{self.hubsoft_api_port}"):
            return base
        return f"{base}:{self.hubsoft_api_port}"

    def validate(self) -> None:
        required_fields = {
            "CANCELAMENTOS_API_KEY": self.cancelamentos_api_key,
            "HUBSOFT_CLIENT_ID": self.hubsoft_client_id,
            "HUBSOFT_CLIENT_SECRET": self.hubsoft_client_secret,
            "HUBSOFT_USERNAME": self.hubsoft_username,
            "HUBSOFT_PASSWORD": self.hubsoft_password,
            "HUBSOFT_WEB_EMAIL": self.hubsoft_web_email,
            "HUBSOFT_WEB_PASSWORD": self.hubsoft_web_password,
        }
        missing = [key for key, value in required_fields.items() if not value]
        if missing:
            missing_fields = ", ".join(missing)
            raise RuntimeError(f"Variaveis obrigatorias nao preenchidas: {missing_fields}")


def _split_csv_env(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "sim", "yes", "on"}
