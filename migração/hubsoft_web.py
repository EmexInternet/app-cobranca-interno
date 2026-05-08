from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from migração.config import Settings
from app.models import ClientInfo
from migração.selenium_helpers import BrowserSession, build_driver


class HubsoftBillingAutomation:
    def __init__(self, settings: Settings, *, dry_run: bool = False) -> None:
        self.settings = settings
        self.settings.validate_web_credentials()
        self.driver = build_driver(settings)
        self.browser = BrowserSession(
            self.driver,
            settings.selenium_timeout,
            validation_interval=settings.selenium_validation_interval,
            max_wait=settings.selenium_max_wait,
            logger=self._log,
        )
        self.dry_run = dry_run

    def close(self) -> None:
        self.driver.quit()

    def run(
        self,
        client: ClientInfo,
        valor_cobranca: float,
        descricao_cobranca: str,
        *,
        include_equipment_charge: bool = False,
    ) -> dict:
        self._log("Abrindo login e autenticando no Hubsoft.")
        self.login_if_needed(client.id_cliente)
        self._log("Navegando para a aba financeira do cliente.")
        self.navigate_to_financial_tab(client.id_cliente)
        self._log("Preenchendo formulario de cobranca.")
        charge_reference = self.create_charge(
            client,
            valor_cobranca,
            descricao_cobranca,
            service_reference=client.service.service_display_name,
            service_number=client.service.numero_plano,
        )
        self._log("Preenchendo formulario de fatura.")
        self.create_invoice(client, charge_reference)
        equipment_billing_result = None
        if include_equipment_charge:
            equipment_billing_result = self.run_equipment_billing_only(client=client)
        return {
            "id_cliente": client.id_cliente,
            "plano": client.service.service_display_name,
            "valor_cobranca": valor_cobranca,
            "descricao_cobranca": descricao_cobranca,
            "charge_reference": charge_reference,
            "equipment_billing_result": equipment_billing_result,
            "dry_run": self.dry_run,
        }

    def run_charge_only(
        self,
        *,
        client: ClientInfo,
        valor_cobranca: float,
        descricao_cobranca: str,
        service_reference: str,
        service_number: int | None,
    ) -> dict:
        self._log("Abrindo login e autenticando no Hubsoft.")
        self.login_if_needed(client.id_cliente)
        self._log("Navegando para a aba financeira do cliente.")
        self.navigate_to_financial_tab(client.id_cliente)
        self._log("Preenchendo formulario de cobranca.")
        charge_reference = self.create_charge(
            client,
            valor_cobranca,
            descricao_cobranca,
            service_reference=service_reference,
            service_number=service_number,
        )
        return {
            "id_cliente": client.id_cliente,
            "plano": service_reference,
            "valor_cobranca": valor_cobranca,
            "descricao_cobranca": descricao_cobranca,
            "charge_reference": charge_reference,
            "dry_run": self.dry_run,
        }

    def run_invoice_only(
        self,
        *,
        client: ClientInfo,
        charge_reference: dict,
        include_equipment_charge: bool = False,
    ) -> dict:
        self._log("Abrindo login e autenticando no Hubsoft.")
        self.login_if_needed(client.id_cliente)
        self._log("Navegando para a aba financeira do cliente.")
        self.navigate_to_financial_tab(client.id_cliente)
        self._log("Preenchendo formulario de fatura.")
        self.create_invoice(client, charge_reference)
        equipment_billing_result = None
        if include_equipment_charge:
            equipment_billing_result = self.run_equipment_billing_only(client=client)
        return {
            "id_cliente": client.id_cliente,
            "plano": client.service.service_display_name,
            "charge_reference": charge_reference,
            "equipment_billing_result": equipment_billing_result,
            "dry_run": self.dry_run,
        }

    def run_equipment_billing_only(self, *, client: ClientInfo) -> dict:
        self._log("Abrindo login e autenticando no Hubsoft.")
        self.login_if_needed(client.id_cliente)
        self._log("Navegando para a aba financeira do cliente.")
        self.navigate_to_financial_tab(client.id_cliente)
        self._log("Preenchendo formulario de cobranca de equipamento em comodato.")
        equipment_charge_reference = self.create_charge(
            client,
            self.settings.equipment_charge_value,
            self.settings.equipment_charge_description,
            service_reference=client.service.service_display_name,
            service_number=client.service.numero_plano,
            service_type=self.settings.equipment_charge_service_type,
        )
        self._log("Preenchendo formulario de fatura da cobranca de equipamento em comodato.")
        self.create_invoice(client, equipment_charge_reference)
        return {
            "id_cliente": client.id_cliente,
            "plano": client.service.service_display_name,
            "equipment_charge_reference": equipment_charge_reference,
            "dry_run": self.dry_run,
        }

    def login_if_needed(self, id_cliente: int) -> None:
        target_url = f"{self.settings.hubsoft_web_base_url}/cliente/editar/{id_cliente}/financeiro#cobrancas"
        self.browser.open(target_url)
        self._log(f"URL inicial: {self.driver.current_url}")

        login_fields = [
            (By.NAME, "username"),
            (By.NAME, "email"),
            (By.ID, "username"),
            (By.ID, "email"),
            (By.XPATH, "//input[@type='email']"),
        ]
        password_fields = [
            (By.NAME, "password"),
            (By.ID, "password"),
            (By.XPATH, "//input[@type='password']"),
        ]

        is_login_page = "/login" in self.driver.current_url or self.browser.element_exists(login_fields)
        if not is_login_page and not self.browser.element_exists(password_fields):
            self._log("Sessao ja autenticada.")
            return

        if self.browser.element_exists(login_fields):
            self._log("Preenchendo email/login.")
            username_input = self.browser.wait_for_visible_any(login_fields)
            self.browser.set_value(username_input, self.settings.resolved_web_username)
            self._set_remember_me_if_available()
            self._click_validate_button()

        self._log("Preenchendo senha.")
        password_input = self.browser.wait_for_visible_any(password_fields)
        self.browser.set_value(password_input, self.settings.resolved_web_password)
        self._set_remember_me_if_available()
        self._click_enter_button()

        self.browser.until("Login ainda nao concluiu", lambda driver: "/login" not in driver.current_url)
        self._log(f"Login concluido. URL atual: {self.driver.current_url}")
        self.browser.open(target_url)
        self.browser.wait_url_contains(f"/cliente/editar/{id_cliente}")

    def navigate_to_financial_tab(self, id_cliente: int) -> None:
        target_url = f"{self.settings.hubsoft_web_base_url}/cliente/editar/{id_cliente}/financeiro#cobrancas"
        self.browser.open(target_url)
        self._log(f"Pagina de financeiro aberta: {self.driver.current_url}")
        self.browser.wait_url_contains(f"/cliente/editar/{id_cliente}")
        self.browser.wait_for_any(
            [
                (By.XPATH, "//*[contains(normalize-space(.), 'Financeiro do Cliente')]"),
                (By.XPATH, "//*[contains(normalize-space(.), 'Cobrancas')]"),
            ]
        )

    def create_charge(
        self,
        client: ClientInfo,
        valor_cobranca: float,
        descricao_cobranca: str,
        *,
        service_reference: str | None = None,
        service_number: int | None = None,
        service_type: str | None = None,
    ) -> dict:
        self.open_add_menu_and_choose("COBRANCA")
        self._log("Modal de cobranca solicitado.")
        dialog = self._wait_for_charge_dialog()
        due_date = datetime.now().strftime("%d/%m/%Y")

        self._select_charge_service_type(dialog, service_type=service_type)
        self._select_dialog_service(
            dialog,
            service_reference or client.service.service_display_name,
            service_number=service_number if service_number is not None else client.service.numero_plano,
        )
        self._set_dialog_date(dialog, "Vencimento", due_date)
        self._set_dialog_input(dialog, "descricao", descricao_cobranca)
        self._set_dialog_input(dialog, "valor", f"{valor_cobranca:.2f}", money=True)
        self._wait_for_charge_submit_enabled(dialog)

        if self.dry_run:
            self._log("Dry-run ativo: cobranca preenchida sem clicar em gerar.")
            self._reset_after_dry_run(client.id_cliente)
            return {
                "descricao": descricao_cobranca,
                "valor": valor_cobranca,
                "vencimento": due_date,
                "id": None,
                "created": False,
            }

        self._click_charge_submit(dialog)
        self.browser.until("Modal de cobranca ainda esta aberto", lambda driver: not driver.find_elements(By.XPATH, "//md-dialog"))
        self.wait_for_save_feedback()
        charge_reference = {
            "id": None,
            "descricao": descricao_cobranca,
            "valor": valor_cobranca,
            "vencimento": due_date,
            "created": True,
        }

        try:
            self._refresh_financial_grid()
            located_charge = self._find_created_charge_reference(descricao_cobranca, valor_cobranca, due_date)
            charge_reference.update(located_charge)
            self._log(f"Cobranca localizada para vinculacao: {charge_reference}")
        except RuntimeError:
            self._log("Cobranca criada, mas nao localizada na grade principal. Vou seguir usando descricao, valor e vencimento para vincular na fatura.")

        return charge_reference

    def create_invoice(self, client: ClientInfo, charge_reference: dict) -> None:
        if self.dry_run:
            self._log("Dry-run ativo: etapa de fatura foi pulada porque a cobranca nao foi gerada de fato.")
            return

        self.open_add_menu_and_choose("FATURA")
        self._log("Modal de fatura solicitado.")
        dialog = self._wait_for_invoice_dialog()

        self._select_dialog_service(
            dialog,
            client.service.service_display_name,
            service_number=client.service.numero_plano,
        )
        self._ensure_invoice_billing_method(dialog)
        self._set_dialog_date(dialog, "Vencimento", charge_reference["vencimento"])
        self._select_invoice_charge(dialog, charge_reference)
        self._wait_for_invoice_submit_enabled(dialog)

        self._click_invoice_submit(dialog)
        self.browser.until("Modal de fatura ainda esta aberto", lambda driver: not driver.find_elements(By.XPATH, "//md-dialog"))
        self.wait_for_save_feedback()

    def open_add_menu_and_choose(self, item_text: str) -> None:
        add_button = self.browser.wait_for_clickable_any(
            [
                (By.XPATH, "//button[@aria-label='Adicionar']"),
                (By.XPATH, "//button[contains(@aria-label, 'Adicionar')]"),
            ]
        )
        self.browser.click(add_button)

        if item_text == "COBRANCA":
            locators = [
                (By.XPATH, "//button[@aria-label='Cobrança']"),
                (By.XPATH, "//button[@aria-label='Cobranca']"),
                (By.XPATH, "//button[.//span[normalize-space()='Cobrança']]"),
                (By.XPATH, "//button[.//span[normalize-space()='Cobranca']]"),
            ]
        else:
            locators = [
                (By.XPATH, "//button[@aria-label='Fatura']"),
                (By.XPATH, "//button[.//span[normalize-space()='Fatura']]"),
            ]

        self.browser.click_any(locators)

    def wait_for_save_feedback(self) -> None:
        try:
            self.browser.wait_for_any(
                [
                    (By.XPATH, "//*[contains(., 'sucesso')]"),
                    (By.XPATH, "//*[contains(., 'Sucesso')]"),
                    (By.XPATH, "//*[contains(., 'gerada')]"),
                    (By.XPATH, "//*[contains(., 'Gerada')]"),
                    (By.XPATH, "//*[contains(., 'salva')]"),
                    (By.XPATH, "//*[contains(., 'Salva')]"),
                ]
            )
        except TimeoutException:
            pass

    def dump_debug_state(self, file_path: str | Path) -> None:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        state = {
            "url": self.driver.current_url,
            "title": self.driver.title,
        }
        Path(file_path).write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _click_validate_button(self) -> None:
        button = self.browser.wait_for_clickable_any(
            [
                (By.XPATH, "//button[@aria-label='Validar']"),
                (By.XPATH, "//button[.//span[normalize-space()='Validar']]"),
                (By.XPATH, "//button[normalize-space()='Validar']"),
            ]
        )
        self.browser.click(button)
        self._log("Botao clicado na etapa de email: VALIDAR")

    def _click_enter_button(self) -> None:
        button = self.browser.wait_for_clickable_any(
            [
                (By.XPATH, "//button[@aria-label='Entrar']"),
                (By.XPATH, "//button[.//span[normalize-space()='Entrar']]"),
                (By.XPATH, "//button[normalize-space()='Entrar']"),
            ]
        )
        self.browser.click(button)
        self._log("Botao clicado na etapa de senha: ENTRAR")

    def _set_remember_me_if_available(self) -> None:
        candidates = [
            "//md-checkbox[@aria-label='Lembrar-me']",
            "//input[@type='checkbox']/ancestor::md-checkbox[1]",
            "//*[contains(normalize-space(.), 'Lembrar-me')]/preceding::md-checkbox[1]",
        ]
        for xpath in candidates:
            elements = self.driver.find_elements(By.XPATH, xpath)
            if not elements:
                continue
            element = elements[0]
            aria_checked = (element.get_attribute("aria-checked") or "").lower()
            checked = element.get_attribute("checked")
            if aria_checked == "true" or checked:
                return
            try:
                self.browser.click(element)
                self._log("Checkbox 'Lembrar-me' ativado.")
                return
            except Exception:
                continue

    def _wait_for_charge_dialog(self):
        return self._wait_for_dialog(
            [
                (By.XPATH, "//md-dialog[@aria-label='Cobrança']"),
                (By.XPATH, "//md-dialog[@aria-label='Cobranca']"),
                (By.XPATH, "//md-dialog[contains(., 'Nova Cobrança')]"),
                (By.XPATH, "//md-dialog[contains(., 'Nova Cobranca')]"),
            ],
            "Modal de cobranca ainda nao apareceu",
        )

    def _wait_for_invoice_dialog(self):
        return self._wait_for_dialog(
            [
                (By.XPATH, "//md-dialog[@aria-label='Fatura']"),
                (By.XPATH, "//md-dialog[contains(., 'Adicionar Fatura')]"),
            ],
            "Modal de fatura ainda nao apareceu",
        )

    def _select_charge_service_type(self, dialog, *, service_type: str | None = None) -> None:
        target_type = (service_type or self.settings.default_tipo_servico_cobranca).strip()
        if not target_type:
            return

        type_select = self._wait_dialog_element(
            dialog,
            [
                ".//md-select[@name='tipo_servico']",
                ".//md-select[contains(@name, 'tipo_servico')]",
                ".//md-select[contains(@aria-label, 'Tipo de Servi?o')]",
                ".//md-select[contains(@aria-label, 'Tipo de Servico')]",
                ".//md-input-container[.//label[contains(normalize-space(.), 'Tipo de Servi?o')]]//md-select[1]",
                ".//md-input-container[.//label[contains(normalize-space(.), 'Tipo de Servico')]]//md-select[1]",
                ".//label[contains(normalize-space(.), 'Tipo de Servi?o')]/following::md-select[1]",
                ".//label[contains(normalize-space(.), 'Tipo de Servico')]/following::md-select[1]",
            ],
            "Campo 'Tipo de servico' do modal ainda nao carregou",
        )
        self.browser.click(type_select)
        self._log(f"Selecionando tipo de servico: {target_type}")
        option = self._wait_visible_open_option(target_type)
        self.browser.click(option)

    def _select_dialog_service(self, dialog, service_name: str, *, service_number: int | None = None) -> None:
        service_select = self._wait_dialog_element(
            dialog,
            [
                ".//md-select[@name='cliente_servico']",
                ".//md-select[contains(@name, 'cliente_servico')]",
                ".//md-select[contains(@aria-label, 'Serviço / Plano')]",
                ".//md-select[contains(@aria-label, 'Servico / Plano')]",
                ".//md-input-container[.//label[contains(normalize-space(.), 'Serviço / Plano')]]//md-select[1]",
                ".//md-input-container[.//label[contains(normalize-space(.), 'Servico / Plano')]]//md-select[1]",
                ".//label[contains(normalize-space(.), 'Serviço / Plano')]/following::md-select[1]",
                ".//label[contains(normalize-space(.), 'Servico / Plano')]/following::md-select[1]",
                ".//*[contains(normalize-space(.), 'Serviço / Plano')]/ancestor::md-input-container[1]//md-select[1]",
                ".//*[contains(normalize-space(.), 'Servico / Plano')]/ancestor::md-input-container[1]//md-select[1]",
            ],
            "Campo 'Servico / Plano' do modal ainda nao carregou",
        )
        self.browser.click(service_select)
        self._log(f"Selecionando servico/plano: {service_name}")

        normalized_name = service_name.upper().replace("MBITS", "MBPS")
        normalized_prefix = normalized_name.split(" - ")[0].strip()
        locators = []
        if service_number is not None:
            locators.extend(
                [
                    (By.XPATH, f"//md-option[contains(normalize-space(.), '({service_number})')]"),
                    (
                        By.XPATH,
                        f"//md-option[contains(translate(normalize-space(.), "
                        f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{service_number}')]",
                    ),
                ]
            )
        if normalized_name:
            locators.extend(
                [
                    (
                        By.XPATH,
                        f"//md-option[contains(translate(normalize-space(.), "
                        f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{normalized_name}') "
                        "and contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'HABILITADO')]",
                    ),
                    (
                        By.XPATH,
                        f"//md-option[contains(translate(normalize-space(.), "
                        f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{normalized_name}')]",
                    ),
                ]
            )
        if normalized_prefix and normalized_prefix != normalized_name:
            locators.extend(
                [
                    (
                        By.XPATH,
                        f"//md-option[contains(translate(normalize-space(.), "
                        f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{normalized_prefix}') "
                        "and contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'HABILITADO')]",
                    ),
                    (
                        By.XPATH,
                        f"//md-option[contains(translate(normalize-space(.), "
                        f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{normalized_prefix}')]",
                    ),
                ]
            )

        option = self.browser.wait_for_visible_any(locators)
        self.browser.click(option)

    def _ensure_invoice_billing_method(self, dialog) -> None:
        target_method = self.settings.default_forma_cobranca.strip()
        billing_select_locators = [
            ".//md-select[contains(@aria-label, 'Forma de Cobrança')]",
            ".//md-select[contains(@aria-label, 'Forma de Cobranca')]",
            ".//label[contains(normalize-space(.), 'Forma de Cobrança')]/following::md-select[1]",
            ".//label[contains(normalize-space(.), 'Forma de Cobranca')]/following::md-select[1]",
        ]
        billing_select = self._wait_dialog_element(
            dialog,
            billing_select_locators,
            "Campo 'Forma de cobranca' do modal de fatura ainda nao carregou",
        )

        current_label = self._current_billing_method_label(dialog, billing_select_locators)
        if target_method and target_method.lower() in current_label.lower():
            self._log(f"Forma de cobranca ja selecionada: {current_label}")
            return

        self._log(f"Selecionando forma de cobranca: {target_method}")
        self.browser.click(billing_select)
        self._filter_open_select_options(target_method)
        option = self._wait_visible_open_option(target_method)
        self.browser.click(option)
        self.browser.until(
            f"Forma de cobranca ainda nao ficou como '{target_method}'",
            lambda driver: target_method.lower() in self._current_billing_method_label(dialog, billing_select_locators).lower(),
        )
        self._log(f"Forma de cobranca confirmada: {self._current_billing_method_label(dialog, billing_select_locators)}")

    def _set_dialog_date(self, dialog, label_text: str, date_display: str) -> None:
        date_input = self._wait_dialog_element(
            dialog,
            [
                f".//label[contains(normalize-space(), '{label_text}')]/following::input[contains(@class, 'md-datepicker-input')][1]",
            ],
            f"Campo '{label_text}' do modal ainda nao carregou",
        )
        self.browser.set_value_via_js(date_input, date_display)

    def _set_dialog_input(self, dialog, field_name: str, value: str, *, money: bool = False) -> None:
        input_element = self._wait_dialog_element(
            dialog,
            [f".//*[@name='{field_name}']"],
            f"Campo '{field_name}' do modal ainda nao carregou",
        )
        final_value = value.replace(".", ",") if money else value
        try:
            self.browser.set_value(input_element, final_value)
        except Exception:
            self.browser.set_value_via_js(input_element, final_value)

    def _find_charge_submit_button(self, dialog):
        return self._wait_dialog_element(
            dialog,
            [
                ".//button[.//span[contains(normalize-space(.), 'Gerar Cobran') and contains(normalize-space(.), 'Avulsa')]]",
                ".//button[contains(normalize-space(.), 'Gerar Cobran') and contains(normalize-space(.), 'Avulsa')]",
            ],
            "Botao 'Gerar Cobranca Avulsa' ainda nao apareceu",
        )

    def _wait_for_charge_submit_enabled(self, dialog) -> None:
        self.browser.until(
            "Botao 'Gerar Cobranca Avulsa' ainda esta desabilitado",
            lambda driver: self._find_charge_submit_button(dialog).get_attribute("disabled") in (None, "false"),
        )

    def _click_charge_submit(self, dialog) -> None:
        self.browser.click(self._find_charge_submit_button(dialog))

    def _find_invoice_submit_button(self, dialog):
        return self._wait_dialog_element(
            dialog,
            [
                ".//button[.//span[normalize-space()='Salvar']]",
                ".//button[normalize-space()='Salvar']",
            ],
            "Botao 'Salvar' da fatura ainda nao apareceu",
        )

    def _wait_for_invoice_submit_enabled(self, dialog) -> None:
        self.browser.until(
            "Botao 'Salvar' ainda esta desabilitado",
            lambda driver: self._find_invoice_submit_button(dialog).get_attribute("disabled") in (None, "false"),
        )

    def _click_invoice_submit(self, dialog) -> None:
        self.browser.click(self._find_invoice_submit_button(dialog))

    def _refresh_financial_grid(self) -> None:
        try:
            refresh_button = self.driver.find_element(By.XPATH, "//button[@aria-label='Recarregar Tudo']")
            self.browser.click(refresh_button)
        except NoSuchElementException:
            return

    def _find_created_charge_reference(self, descricao: str, valor: float, vencimento: str) -> dict:
        normalized_value_variants = self._normalized_brl_value_variants(valor)

        rows = self.driver.find_elements(By.XPATH, "//hubsoft-cliente-financeiro-cobranca//tbody/tr")
        for row in rows:
            row_text = row.text
            if descricao.lower() not in row_text.lower():
                continue
            if vencimento not in row_text:
                continue
            if not any(value in row_text for value in normalized_value_variants):
                continue

            columns = row.find_elements(By.XPATH, "./td")
            charge_id = columns[0].text.strip() if columns else ""
            return {
                "id": charge_id or None,
                "descricao": descricao,
                "valor": valor,
                "vencimento": vencimento,
                "created": True,
            }

        raise RuntimeError("A cobranca gerada nao foi localizada na grade do financeiro para vinculacao na fatura.")

    def _select_invoice_charge(self, dialog, charge_reference: dict) -> None:
        row = self._wait_for_invoice_charge_row(dialog, charge_reference)
        self._log(f"Selecionando cobranca vinculada na fatura. Linha: {row.text}")

        checkbox_candidates = [
            ".//input[@type='checkbox']",
            ".//md-checkbox",
            ".//td[1]//div[contains(@class, 'md-container')]",
            ".//td[1]",
        ]
        for selector in checkbox_candidates:
            elements = row.find_elements(By.XPATH, selector)
            if not elements:
                continue
            self.browser.click(elements[0])
            return

        raise RuntimeError("Nao foi possivel marcar a cobranca para vinculacao na fatura.")

    def _wait_for_invoice_charge_row(self, dialog, charge_reference: dict):
        value_variants = self._normalized_brl_value_variants(charge_reference["valor"])

        def locate(driver):
            current_dialog = self._resolve_dialog(dialog)
            rows = current_dialog.find_elements(By.XPATH, ".//tbody/tr")
            for row in rows:
                row_text = row.text
                if charge_reference.get("id") and charge_reference["id"] not in row_text:
                    continue
                if charge_reference["descricao"].lower() not in row_text.lower():
                    continue
                if charge_reference["vencimento"] not in row_text:
                    continue
                if not any(value in row_text for value in value_variants):
                    continue
                return row
            return False

        return self.browser.until(
            "Cobranca criada ainda nao apareceu na tabela de vinculacao da fatura",
            locate,
        )

    @staticmethod
    def _normalized_brl_value_variants(valor: float) -> set[str]:
        return {
            f"R${valor:.2f}".replace(".", ","),
            f"R$ {valor:.2f}".replace(".", ","),
            f"R${valor:.2f}",
            f"R$ {valor:.2f}",
            f"{valor:.2f}".replace(".", ","),
            f"{valor:.2f}",
        }

    def _current_billing_method_label(self, dialog, xpaths: list[str]) -> str:
        selected_value_xpaths = [
            ".//*[contains(@class, 'md-text')][normalize-space()]",
            ".//md-select-value//*[normalize-space()]",
            ".//span[normalize-space()]",
        ]

        for _ in range(3):
            try:
                current_select = self._wait_dialog_element(
                    dialog,
                    xpaths,
                    "Campo 'Forma de cobranca' do modal de fatura ainda nao carregou",
                )
                parts = []
                for xpath in selected_value_xpaths:
                    for element in current_select.find_elements(By.XPATH, xpath):
                        try:
                            text = element.text.strip()
                        except StaleElementReferenceException:
                            continue
                        if text:
                            parts.append(text)

                try:
                    aria_label = (current_select.get_attribute("aria-label") or "").strip()
                except StaleElementReferenceException:
                    continue

                if aria_label:
                    parts.append(aria_label)

                label = " ".join(part for part in parts if part).strip()
                if label:
                    return label
            except StaleElementReferenceException:
                continue

        return ""

    def _filter_open_select_options(self, target_method: str) -> None:
        filter_inputs = self.driver.find_elements(
            By.XPATH,
            "//input[contains(@placeholder, 'Filtrar') and not(@disabled)]",
        )
        for filter_input in filter_inputs:
            if not filter_input.is_displayed():
                continue
            try:
                self.browser.set_value(filter_input, target_method)
                return
            except Exception:
                try:
                    self.browser.set_value_via_js(filter_input, target_method)
                    return
                except Exception:
                    continue

    def _wait_visible_open_option(self, target_method: str):
        exact_option_literal = self._xpath_literal(target_method.upper())

        def locate(driver):
            candidates = driver.find_elements(
                By.XPATH,
                f"//*[self::md-option or self::div or self::span][translate(normalize-space(.), "
                f"'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')={exact_option_literal}]",
            )
            for candidate in candidates:
                try:
                    if not candidate.is_displayed():
                        continue
                    clickable_ancestors = candidate.find_elements(
                        By.XPATH,
                        "./ancestor-or-self::md-option[1] | ./ancestor-or-self::*[@role='option'][1] | ./ancestor-or-self::li[1]",
                    )
                    for clickable in clickable_ancestors:
                        try:
                            if clickable.is_displayed():
                                return clickable
                        except StaleElementReferenceException:
                            continue
                    return candidate
                except StaleElementReferenceException:
                    continue
            return False

        return self.browser.until(
            f"Opcao visivel '{target_method}' nao apareceu no dropdown aberto",
            locate,
        )

    def _reset_after_dry_run(self, id_cliente: int) -> None:
        dialog_buttons = [
            (By.XPATH, "//md-dialog//button[.//span[normalize-space()='Cancelar']]"),
            (By.XPATH, "//md-dialog//button[normalize-space()='Cancelar']"),
            (By.XPATH, "//md-dialog//button[.//span[normalize-space()='Fechar']]"),
            (By.XPATH, "//md-dialog//button[normalize-space()='Fechar']"),
        ]

        for locator in dialog_buttons:
            try:
                buttons = self.driver.find_elements(*locator)
            except Exception:
                buttons = []
            for button in buttons:
                try:
                    if button.is_displayed():
                        self.browser.click(button)
                        self.browser.until(
                            "Modal ainda aberto apos dry-run",
                            lambda driver: not any(
                                element.is_displayed()
                                for element in driver.find_elements(By.XPATH, "//md-dialog")
                            ),
                        )
                        self.navigate_to_financial_tab(id_cliente)
                        return
                except Exception:
                    continue

        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
        except Exception:
            pass

        self.navigate_to_financial_tab(id_cliente)

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"

    def _wait_dialog_element(self, dialog, xpaths: list[str], description: str):
        def locate(driver):
            current_dialog = self._resolve_dialog(dialog)
            for xpath in xpaths:
                elements = current_dialog.find_elements(By.XPATH, xpath)
                for element in elements:
                    try:
                        if element.is_displayed():
                            return element
                    except StaleElementReferenceException:
                        return False
            return False

        return self.browser.until(description, locate)

    def _wait_for_dialog(self, locators, description: str):
        return self.browser.until(
            description,
            lambda driver: next(
                (
                    element
                    for locator in locators
                    for element in driver.find_elements(*locator)
                    if element.is_displayed()
                ),
                False,
            ),
        )

    def _resolve_dialog(self, dialog):
        try:
            if dialog.is_displayed():
                return dialog
        except StaleElementReferenceException:
            pass

        visible_dialogs = [
            element
            for element in self.driver.find_elements(By.XPATH, "//md-dialog")
            if element.is_displayed()
        ]
        if not visible_dialogs:
            raise NoSuchElementException("Nenhum md-dialog visivel foi encontrado para continuar o preenchimento.")
        return visible_dialogs[-1]

    @staticmethod
    def _log(message: str) -> None:
        print(f"[hubsoft] {message}", flush=True)
