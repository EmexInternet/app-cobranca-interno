from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

from app.models import ClientInfo, ServiceInfo
from app_python_automacao.models import CancelamentoRecord
from app_python_automacao.settings import Settings


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIR = REPO_ROOT / "migração"


@dataclass(slots=True)
class LegacyPhaseOneOneResult:
    fine_value: float
    principal_charge_created: bool
    equipment_charge_created: bool
    raw_result: dict


class LegacyBillingRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ensure_repo_root()
        self.legacy_config = importlib.import_module("migração.config")
        self.legacy_hubsoft_web = importlib.import_module("migração.hubsoft_web")
        self.legacy_multa_calculator = importlib.import_module("migração.multa_calculator")

    def run_phase_one_one(
        self,
        *,
        cancelamento: CancelamentoRecord,
        dry_run: bool,
        headless: bool,
    ) -> LegacyPhaseOneOneResult:
        plan_name = (cancelamento.plano or "").strip()
        if not plan_name:
            raise RuntimeError("Plano do cliente nao informado para a fase 1.1.")

        if not cancelamento.data_venda or not cancelamento.data_cancelamento:
            raise RuntimeError("Datas de venda/cancelamento ausentes para a fase 1.1.")

        legacy_settings = self._build_legacy_settings(headless=headless)
        client = ClientInfo(
            id_cliente=cancelamento.id_cliente,
            service=ServiceInfo(
                service_display_name=plan_name,
                numero_plano=cancelamento.numero_plano,
            ),
        )

        multa_calculator = self.legacy_multa_calculator.MultaCalculator(legacy_settings)
        multa_result = multa_calculator.calculate(
            sale_date=cancelamento.data_venda,
            cancel_date=cancelamento.data_cancelamento,
        )
        fine_value = float(multa_result.get("fineValue") or 0)

        automation = self.legacy_hubsoft_web.HubsoftBillingAutomation(
            legacy_settings,
            dry_run=dry_run,
        )
        try:
            if fine_value > 0:
                raw_result = automation.run(
                    client,
                    fine_value,
                    legacy_settings.default_descricao_cobranca,
                    include_equipment_charge=True,
                )
                principal_charge_created = True
                equipment_charge_created = bool(raw_result.get("equipment_billing_result"))
            else:
                raw_result = automation.run_equipment_billing_only(client=client)
                principal_charge_created = False
                equipment_charge_created = True
        finally:
            automation.close()

        return LegacyPhaseOneOneResult(
            fine_value=fine_value,
            principal_charge_created=principal_charge_created,
            equipment_charge_created=equipment_charge_created,
            raw_result=raw_result,
        )

    def _build_legacy_settings(self, *, headless: bool):
        script_path = self.settings.legacy_multa_cli_script.strip()
        if not script_path:
            script_path = str((LEGACY_DIR / "scripts" / "calculate_multa.js").resolve())

        profile_dir = self.settings.legacy_browser_profile_dir.strip() or self.settings.hubsoft_storage_dir

        return self.legacy_config.Settings(
            hubsoft_web_base_url=self.settings.hubsoft_web_url.rstrip("/"),
            hubsoft_web_username=self.settings.hubsoft_web_email,
            hubsoft_web_password=self.settings.hubsoft_web_password,
            browser=self.settings.legacy_browser,
            browser_binary_path=self.settings.hubsoft_chrome_binary_path,
            browser_profile_dir=profile_dir,
            browser_profile_name=self.settings.legacy_browser_profile_name,
            headless=headless,
            selenium_timeout=self.settings.legacy_selenium_timeout,
            selenium_validation_interval=self.settings.legacy_selenium_validation_interval,
            selenium_max_wait=self.settings.legacy_selenium_max_wait,
            default_descricao_cobranca=self.settings.legacy_default_descricao_cobranca,
            default_tipo_servico_cobranca=self.settings.legacy_default_tipo_servico_cobranca,
            default_forma_cobranca=self.settings.legacy_default_forma_cobranca,
            multa_benefit_value=float(self.settings.multa_rescisoria_valor_beneficio_padrao.replace(",", ".")),
            multa_cli_script=script_path,
            equipment_charge_service_type=self.settings.legacy_equipment_charge_service_type,
            equipment_charge_description=self.settings.legacy_equipment_charge_description,
            equipment_charge_value=self.settings.legacy_equipment_charge_value,
        )

    @staticmethod
    def _ensure_repo_root() -> None:
        root = str(REPO_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
