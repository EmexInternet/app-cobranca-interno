from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Error, Page, Playwright, sync_playwright

from app_python_automacao.settings import Settings

LOGGER = logging.getLogger(__name__)


class HubsoftBrowserAutomation:
    """Controla o Hubsoft Web via Chromium com sessao persistente."""

    def __init__(self, settings: Settings, dry_run: bool = False, headless: bool = True) -> None:
        self.settings = settings
        self.dry_run = dry_run
        self.headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "HubsoftBrowserAutomation":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._context is not None:
            return

        storage_dir = Path(self.settings.hubsoft_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(storage_dir),
            headless=self.headless,
            slow_mo=200,
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        LOGGER.info("Chromium iniciado com perfil persistente em %s", storage_dir)

    def close(self) -> None:
        if self._context is not None:
            try:
                self._context.storage_state(path=self.settings.hubsoft_storage_state)
            except Error:
                LOGGER.debug("Nao foi possivel salvar storage_state nesta execucao.", exc_info=True)
            self._context.close()
            self._context = None

        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

        self._page = None

    def ensure_logged_in(self, target_url: str | None = None) -> None:
        page = self._require_page()
        protected_url = target_url or self.settings.hubsoft_web_url.rstrip("/")
        login_url = f"{self.settings.hubsoft_web_url.rstrip('/')}/login"

        LOGGER.info("Verificando sessao no Hubsoft Web.")
        page.goto(protected_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        if self._is_login_url(page.url):
            LOGGER.info("Sessao invalida ou expirada. Realizando login.")
            page.goto(login_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            self._perform_login(page)
            if target_url:
                page.goto(target_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
        else:
            LOGGER.info("Sessao persistente reutilizada com sucesso.")

    def add_observation(self, id_cliente: int, protocolo: str) -> None:
        page = self._require_page()
        target_url = f"{self.settings.hubsoft_web_url.rstrip('/')}/cliente/editar/{id_cliente}/cadastro"
        self.ensure_logged_in(target_url=target_url)

        LOGGER.info("Abrindo cadastro do cliente %s para adicionar observacao.", id_cliente)
        page.goto(target_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        self._click_first(
            page,
            "aba OBS",
            [
                lambda: page.get_by_role("tab", name=re.compile(r"^OBS$", re.I)),
                lambda: page.get_by_text(re.compile(r"^OBS$", re.I)),
                lambda: page.locator("text=/^OBS$/i"),
            ],
        )
        page.wait_for_timeout(1000)

        self._click_first(
            page,
            "botao ADICIONAR",
            [
                lambda: page.get_by_role("button", name=re.compile(r"ADICIONAR", re.I)),
                lambda: page.get_by_text(re.compile(r"ADICIONAR", re.I)),
                lambda: page.locator("text=/ADICIONAR/i"),
            ],
        )
        page.wait_for_timeout(1000)

        observation_text = f"CLIENTE POSSUI PENDENCIA FINANCEIRA NO PROTOCOLO {protocolo}"
        self._fill_first(
            page,
            "campo Observacao",
            observation_text,
            [
                lambda: page.get_by_label(re.compile(r"Observ", re.I)),
                lambda: page.locator("textarea"),
                lambda: page.locator("textarea[name*='observ' i]"),
            ],
        )
        page.wait_for_timeout(1000)

        self._enable_visualizacao_obrigatoria(page)
        page.wait_for_timeout(1000)

        if self.dry_run:
            LOGGER.info(
                "Dry-run ativo. Observacao preparada para cliente %s com protocolo %s, sem salvar.",
                id_cliente,
                protocolo,
            )
            return

        self._click_first(
            page,
            "botao Salvar",
            [
                lambda: page.get_by_role("button", name=re.compile(r"Salvar", re.I)),
                lambda: page.get_by_text(re.compile(r"Salvar", re.I)),
                lambda: page.locator("text=/Salvar/i"),
            ],
        )
        LOGGER.info(
            "Aguardando %sms apos clicar em Salvar para o Hubsoft concluir a gravacao.",
            self.settings.hubsoft_observacao_post_save_wait_ms,
        )
        page.wait_for_timeout(self.settings.hubsoft_observacao_post_save_wait_ms)
        LOGGER.info("Observacao obrigatoria salva para cliente %s.", id_cliente)

    def _perform_login(self, page: Page) -> None:
        self._fill_first(
            page,
            "campo email",
            self.settings.hubsoft_web_email,
            [
                lambda: page.get_by_label(re.compile(r"Email", re.I)),
                lambda: page.get_by_role("textbox", name=re.compile(r"Email", re.I)),
                lambda: page.locator("input[type='email']"),
                lambda: page.locator("input[name*='email' i]"),
            ],
        )
        time.sleep(1)

        self._click_first(
            page,
            "botao validar",
            [
                lambda: page.get_by_role("button", name=re.compile(r"Validar", re.I)),
                lambda: page.get_by_text(re.compile(r"Validar", re.I)),
                lambda: page.locator("text=/Validar/i"),
            ],
        )
        time.sleep(1)

        self._fill_first(
            page,
            "campo senha",
            self.settings.hubsoft_web_password,
            [
                lambda: page.get_by_label(re.compile(r"Senha", re.I)),
                lambda: page.get_by_role("textbox", name=re.compile(r"Senha", re.I)),
                lambda: page.locator("input[type='password']"),
                lambda: page.locator("input[name*='senha' i], input[name*='password' i]"),
            ],
        )
        time.sleep(1)

        self._click_first(
            page,
            "botao entrar",
            [
                lambda: page.get_by_role("button", name=re.compile(r"Entrar", re.I)),
                lambda: page.get_by_text(re.compile(r"Entrar", re.I)),
                lambda: page.locator("text=/Entrar/i"),
            ],
        )
        LOGGER.info(
            "Aguardando %sms apos clicar em Entrar para o Hubsoft concluir o carregamento.",
            self.settings.hubsoft_login_post_enter_wait_ms,
        )
        page.wait_for_timeout(self.settings.hubsoft_login_post_enter_wait_ms)
        self._wait_for_login_completion(page)

        if self._is_login_url(page.url):
            raise RuntimeError("Nao foi possivel concluir o login no Hubsoft Web.")

        LOGGER.info("Login no Hubsoft Web concluido.")

    def _wait_for_login_completion(self, page: Page) -> None:
        timeout_ms = self.settings.hubsoft_login_timeout_ms

        try:
            page.wait_for_url(re.compile(r"^(?!.*\/login).*$"), timeout=timeout_ms)
        except Error:
            LOGGER.debug("A URL nao saiu de /login dentro do timeout configurado.")

        for state in ("domcontentloaded", "load", "networkidle"):
            try:
                page.wait_for_load_state(state, timeout=timeout_ms)
            except Error:
                LOGGER.debug("Load state %s nao foi atingido dentro do timeout.", state)

        if self._is_login_url(page.url):
            page.wait_for_timeout(2000)

    def _is_login_url(self, url: str) -> bool:
        return "/login" in url.lower()

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser nao foi iniciado.")
        return self._page

    def _enable_visualizacao_obrigatoria(self, page: Page) -> None:
        if self._visualizacao_ja_esta_ativa(page):
            LOGGER.info("Visualizacao obrigatoria ja estava marcada como Sim.")
            return

        if self._click_visualizacao_once(page):
            LOGGER.info("Toggle de visualizacao obrigatoria acionado com clique unico.")
            return

        checkbox_candidates = [
            page.locator("input[type='checkbox']:visible"),
            page.locator("[role='dialog'] input[type='checkbox']"),
            page.locator(".modal input[type='checkbox']"),
        ]
        for locator in checkbox_candidates:
            try:
                if locator.count() == 0:
                    continue
                checkbox = locator.first
                checkbox.check(force=True)
                page.wait_for_timeout(500)
                if self._visualizacao_ja_esta_ativa(page):
                    LOGGER.info("Toggle de visualizacao obrigatoria marcado via checkbox.")
                    return
            except Error:
                continue

        click_candidates = [
            lambda: page.get_by_text(re.compile(r"Visualiza..o obrigat..ria\\?\\s*N..o", re.I)),
            lambda: page.locator("label").filter(has_text=re.compile(r"Visualiza..o obrigat..ria", re.I)),
            lambda: page.locator("text=/Visualiza..o obrigat..ria/i"),
            lambda: page.locator("[role='dialog']").locator("span, div, label").filter(
                has_text=re.compile(r"Visualiza..o obrigat..ria", re.I)
            ),
        ]
        for factory in click_candidates:
            try:
                locator = factory()
                locator.first.wait_for(state="visible", timeout=3000)
                locator.first.click(force=True)
                page.wait_for_timeout(500)
                LOGGER.info("Toggle de visualizacao obrigatoria acionado via clique de fallback.")
                return
            except Error:
                continue

        raise RuntimeError("Nao foi possivel localizar toggle de visualizacao obrigatoria.")

    def _click_visualizacao_once(self, page: Page) -> bool:
        label_candidates = [
            page.get_by_text(re.compile(r"Visualização obrigatória\?\s*Não", re.I)),
            page.get_by_text(re.compile(r"Visualizacao obrigatoria\?\s*Nao", re.I)),
            page.get_by_text(re.compile(r"Visualiza..o obrigat..ria\?\s*N..o", re.I)),
            page.get_by_text(re.compile(r"Visualização obrigatória\?", re.I)),
            page.get_by_text(re.compile(r"Visualizacao obrigatoria\?", re.I)),
            page.get_by_text(re.compile(r"Visualiza..o obrigat..ria\?", re.I)),
            page.locator("label").filter(has_text=re.compile(r"Visualiza..o obrigat..ria", re.I)),
            page.locator("[role='dialog']").locator("span, div, label").filter(
                has_text=re.compile(r"Visualiza..o obrigat..ria", re.I)
            ),
        ]

        for locator in label_candidates:
            try:
                target = locator.first
                target.wait_for(state="visible", timeout=3000)
                target.click(force=True)
                page.wait_for_timeout(700)
                return True
            except Error:
                continue

        return False

    def _visualizacao_ja_esta_ativa(self, page: Page) -> bool:
        locators = [
            page.get_by_text(re.compile(r"Visualiza..o obrigat..ria\\?\\s*Sim", re.I)),
            page.locator("text=/Visualiza..o obrigat..ria\\?\\s*Sim/i"),
        ]
        for locator in locators:
            try:
                if locator.first.is_visible(timeout=1000):
                    return True
            except Error:
                continue
        return False

    def _click_first(self, page: Page, description: str, factories: list) -> None:
        for factory in factories:
            try:
                locator = factory()
                locator.first.wait_for(state="visible", timeout=3000)
                locator.first.click()
                LOGGER.debug("Clique realizado em %s.", description)
                return
            except Error:
                continue

        raise RuntimeError(f"Nao foi possivel localizar {description}.")

    def _fill_first(self, page: Page, description: str, value: str, factories: list) -> None:
        for factory in factories:
            try:
                locator = factory()
                locator.first.wait_for(state="visible", timeout=3000)
                locator.first.fill(value)
                LOGGER.debug("Preenchimento realizado em %s.", description)
                return
            except Error:
                continue

        raise RuntimeError(f"Nao foi possivel localizar {description}.")
