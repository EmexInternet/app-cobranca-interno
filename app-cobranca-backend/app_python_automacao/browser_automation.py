from __future__ import annotations

import logging
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app_python_automacao.settings import Settings

LOGGER = logging.getLogger(__name__)


Locator = tuple[str, str]


class HubsoftBrowserAutomation:
    """Controla o Hubsoft Web via Selenium com sessao persistente do Chrome."""

    def __init__(self, settings: Settings, dry_run: bool = False, headless: bool = True) -> None:
        self.settings = settings
        self.dry_run = dry_run
        self.headless = headless
        self._driver: WebDriver | None = None
        self._wait: WebDriverWait | None = None

    def __enter__(self) -> "HubsoftBrowserAutomation":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._driver is not None:
            return

        storage_dir = Path(self.settings.hubsoft_storage_dir).resolve()
        storage_dir.mkdir(parents=True, exist_ok=True)

        options = Options()
        options.add_argument(f"--user-data-dir={storage_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--window-size=1440,1200")
        if self.headless:
            options.add_argument("--headless=new")
        if self.settings.hubsoft_chrome_binary_path:
            options.binary_location = self.settings.hubsoft_chrome_binary_path

        try:
            self._driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise RuntimeError(
                "Nao foi possivel iniciar o Chrome via Selenium. "
                f"Verifique HUBSOFT_CHROME_BINARY_PATH e use um perfil limpo em {storage_dir}."
            ) from exc

        self._wait = WebDriverWait(self._driver, self.settings.hubsoft_element_timeout_seconds)
        LOGGER.info("Chrome iniciado com perfil persistente em %s", storage_dir)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
            self._wait = None

    def ensure_logged_in(self, target_url: str | None = None) -> None:
        driver = self._require_driver()
        protected_url = target_url or self.settings.hubsoft_web_url.rstrip("/")
        login_url = f"{self.settings.hubsoft_web_url.rstrip('/')}/login"

        LOGGER.info("Verificando sessao no Hubsoft Web.")
        driver.get(protected_url)
        time.sleep(1)

        if self._is_login_url(driver.current_url):
            LOGGER.info("Sessao invalida ou expirada. Realizando login.")
            driver.get(login_url)
            time.sleep(1)
            self._perform_login()
            if target_url:
                driver.get(target_url)
                time.sleep(1)
        else:
            LOGGER.info("Sessao persistente reutilizada com sucesso.")

    def add_observation(self, id_cliente: int, protocolo: str) -> None:
        target_url = f"{self.settings.hubsoft_web_url.rstrip('/')}/cliente/editar/{id_cliente}/cadastro"
        self.ensure_logged_in(target_url=target_url)

        LOGGER.info("Cadastro do cliente %s carregado. Iniciando abertura da aba OBS.", id_cliente)
        time.sleep(2)

        self._open_obs_tab()
        time.sleep(1)

        self._click_adicionar()
        time.sleep(1)

        observation_text = f"CLIENTE POSSUI PENDENCIA FINANCEIRA NO PROTOCOLO {protocolo}"
        self._fill_first(
            "campo Observacao",
            observation_text,
            [
                (By.XPATH, "//textarea"),
                (By.XPATH, "//textarea[contains(@name, 'observ') or contains(@id, 'observ')]"),
            ],
        )
        time.sleep(1)

        self._enable_visualizacao_obrigatoria()
        time.sleep(1)

        if self.dry_run:
            LOGGER.info(
                "Dry-run ativo. Observacao preparada para cliente %s com protocolo %s, sem salvar.",
                id_cliente,
                protocolo,
            )
            return

        self._click_first(
            "botao Salvar",
            [
                (By.XPATH, "//button[contains(., 'SALVAR') or contains(., 'Salvar')]"),
                (By.XPATH, "//*[contains(normalize-space(), 'SALVAR') or contains(normalize-space(), 'Salvar')]"),
            ],
        )
        LOGGER.info(
            "Aguardando %sms apos clicar em Salvar para o Hubsoft concluir a gravacao.",
            self.settings.hubsoft_observacao_post_save_wait_ms,
        )
        time.sleep(self.settings.hubsoft_observacao_post_save_wait_ms / 1000)
        LOGGER.info("Observacao obrigatoria salva para cliente %s.", id_cliente)

    def _perform_login(self) -> None:
        self._fill_first(
            "campo email",
            self.settings.hubsoft_web_email,
            [
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.XPATH, "//input[contains(@name, 'email') or contains(@id, 'email')]"),
            ],
        )
        time.sleep(1)

        self._click_first(
            "botao validar",
            [
                (By.XPATH, "//button[contains(., 'Validar')]"),
                (By.XPATH, "//*[contains(normalize-space(), 'Validar')]"),
            ],
        )
        time.sleep(1)

        self._fill_first(
            "campo senha",
            self.settings.hubsoft_web_password,
            [
                (By.CSS_SELECTOR, "input[type='password']"),
                (
                    By.XPATH,
                    "//input[contains(@name, 'senha') or contains(@name, 'password') or "
                    "contains(@id, 'senha') or contains(@id, 'password')]",
                ),
            ],
        )
        time.sleep(1)

        self._click_first(
            "botao entrar",
            [
                (By.XPATH, "//button[contains(., 'Entrar')]"),
                (By.XPATH, "//*[contains(normalize-space(), 'Entrar')]"),
            ],
        )
        LOGGER.info(
            "Aguardando %sms apos clicar em Entrar para o Hubsoft concluir o carregamento.",
            self.settings.hubsoft_login_post_enter_wait_ms,
        )
        time.sleep(self.settings.hubsoft_login_post_enter_wait_ms / 1000)
        self._wait_for_login_completion()

        driver = self._require_driver()
        if self._is_login_url(driver.current_url):
            raise RuntimeError("Nao foi possivel concluir o login no Hubsoft Web.")

        LOGGER.info("Login no Hubsoft Web concluido.")

    def _wait_for_login_completion(self) -> None:
        driver = self._require_driver()
        timeout_s = self.settings.hubsoft_login_timeout_ms / 1000

        try:
            WebDriverWait(driver, timeout_s).until(lambda current: not self._is_login_url(current.current_url))
        except TimeoutException:
            LOGGER.debug("A URL nao saiu de /login dentro do timeout configurado.")

        end_time = time.time() + timeout_s
        while time.time() < end_time:
            try:
                if driver.execute_script("return document.readyState") == "complete":
                    break
            except WebDriverException:
                pass
            time.sleep(0.5)

        if self._is_login_url(driver.current_url):
            time.sleep(2)

    def _is_login_url(self, url: str) -> bool:
        return "/login" in url.lower()

    def _open_obs_tab(self) -> None:
        self._wait_for_obs_context()
        quick_timeout = min(2.0, float(self.settings.hubsoft_element_timeout_seconds))

        driver = self._require_driver()
        for _ in range(2):
            try:
                clicked = driver.execute_script(
                    """
                    const buttonFromAria = document.querySelector("button span[aria-label*='Observ'], button span[aria-label*='observ']");
                    if (!buttonFromAria) return false;
                    const target = buttonFromAria.closest('button');
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center', inline: 'center' });
                    ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
                      target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                    });
                    return true;
                    """
                )
                if clicked and self._wait_for_obs_selected(timeout_seconds=quick_timeout):
                    LOGGER.info("Aba OBS acionada via botao com aria-label Observacoes.")
                    return
            except WebDriverException:
                LOGGER.debug("Falha na tentativa direta de abrir OBS via aria-label.")
            time.sleep(0.4)

        candidates = [
            (By.XPATH, "//span[contains(@aria-label, 'Observ')]/ancestor::button[1]"),
            (By.XPATH, "//button[.//span[contains(@aria-label, 'Observ')]]"),
            (By.XPATH, "//*[normalize-space()='ANEXOS']/following-sibling::*[self::button or self::a or self::div][.//span[contains(@aria-label, 'Observ')]][1]"),
            (By.XPATH, "//*[normalize-space()='CONTATOS']/preceding-sibling::*[self::button or self::a or self::div][.//span[contains(@aria-label, 'Observ')]][1]"),
            (By.XPATH, "//span[normalize-space()='OBS']"),
        ]

        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                if not self._try_click_obs_candidate(element):
                    continue
                if self._wait_for_obs_selected(timeout_seconds=quick_timeout):
                    LOGGER.info("Aba OBS acionada com sucesso.")
                    return

        for _ in range(3):
            try:
                clicked = driver.execute_script(
                    """
                    const normalize = (value) =>
                      (value || '')
                        .normalize('NFD')
                        .replace(/[\\u0300-\\u036f]/g, '')
                        .trim()
                        .toLowerCase();

                    const isVisible = (el) => {
                      const rect = el.getBoundingClientRect();
                      const style = window.getComputedStyle(el);
                      return rect.width > 0 && rect.height > 0 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none';
                    };

                    const clickElement = (el) => {
                      ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
                        el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                      });
                    };

                    const buttonFromAria = document.querySelector("button span[aria-label*='Observ'], button span[aria-label*='observ']");
                    if (buttonFromAria && buttonFromAria.closest('button')) {
                      const target = buttonFromAria.closest('button');
                      target.scrollIntoView({ block: 'center', inline: 'center' });
                      clickElement(target);
                      return true;
                    }

                    const elements = Array.from(document.querySelectorAll('a, button, span, div, li'));
                    const target = elements.find(el => {
                      if (!isVisible(el)) return false;
                      const text = normalize(el.innerText);
                      const title = normalize(el.getAttribute('title'));
                      const aria = normalize(el.getAttribute('aria-label'));
                      return text === 'obs' || text === 'observacoes' || title === 'observacoes' || aria === 'observacoes';
                    });

                    if (!target) return false;
                    const clickable = target.closest('button, a, div, span, li') || target;
                    clickable.scrollIntoView({ block: 'center', inline: 'center' });
                    clickElement(clickable);
                    return true;
                    """
                )
                if clicked and self._wait_for_obs_selected(timeout_seconds=quick_timeout):
                    LOGGER.info("Aba OBS acionada via busca JavaScript por texto/aria-label.")
                    return
            except WebDriverException:
                LOGGER.debug("Falha na tentativa de abrir OBS via JavaScript.")
            time.sleep(0.8)

        raise RuntimeError("Nao foi possivel localizar aba OBS.")

    def _try_click_obs_candidate(self, element: WebElement) -> bool:
        try:
            if not element.is_displayed():
                return False
            target = self._resolve_click_target(element)
            self._scroll_into_view(target)
            ActionChains(self._require_driver()).move_to_element(target).pause(0.2).click().perform()
            return True
        except WebDriverException:
            try:
                self._require_driver().execute_script("arguments[0].click();", self._resolve_click_target(element))
                return True
            except WebDriverException:
                return False

    def _click_adicionar(self) -> None:
        quick_timeout = min(4.0, float(self.settings.hubsoft_element_timeout_seconds))
        driver = self._require_driver()

        for _ in range(2):
            try:
                clicked = driver.execute_script(
                    """
                    const normalize = (value) =>
                      (value || '')
                        .normalize('NFD')
                        .replace(/[\\u0300-\\u036f]/g, '')
                        .trim()
                        .toLowerCase();

                    const isVisible = (el) => {
                      const rect = el.getBoundingClientRect();
                      const style = window.getComputedStyle(el);
                      return rect.width > 0 && rect.height > 0 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none';
                    };

                    const directButton = document.querySelector("button[ng-click*='gotoAdicionarObservacao']");
                    const target = directButton && isVisible(directButton)
                      ? directButton
                      : Array.from(document.querySelectorAll('button')).find(
                          el => isVisible(el) && normalize(el.innerText).includes('adicionar')
                        );
                    if (!target) return false;
                    target.scrollIntoView({ block: 'center', inline: 'center' });
                    ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
                      target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                    });
                    return true;
                    """
                )
                if clicked and self._wait_for_observation_modal(timeout_seconds=quick_timeout):
                    LOGGER.info("Botao ADICIONAR acionado via botao visivel no DOM.")
                    return
            except WebDriverException:
                LOGGER.debug("Falha na tentativa direta de clicar em ADICIONAR via DOM.")
            time.sleep(0.4)

        candidates = [
            (By.XPATH, "//button[contains(@ng-click, 'gotoAdicionarObservacao')]"),
            (By.XPATH, "//button[.//span[normalize-space()='Adicionar']]"),
            (By.XPATH, "//button[contains(., 'ADICIONAR')]"),
            (By.XPATH, "//button[.//*[contains(normalize-space(), 'ADICIONAR')]]"),
            (By.XPATH, "//*[@role='button' and contains(normalize-space(), 'ADICIONAR')]"),
        ]

        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if not element.is_displayed():
                        continue
                    target = self._resolve_click_target(element)
                    self._scroll_into_view(target)
                    ActionChains(self._require_driver()).move_to_element(target).pause(0.2).click().perform()
                    if self._wait_for_observation_modal(timeout_seconds=quick_timeout):
                        LOGGER.info("Botao ADICIONAR acionado via clique simulado.")
                        return
                except WebDriverException:
                    try:
                        self._require_driver().execute_script("arguments[0].click();", self._resolve_click_target(element))
                        if self._wait_for_observation_modal(timeout_seconds=quick_timeout):
                            LOGGER.info("Botao ADICIONAR acionado via clique JavaScript.")
                            return
                    except WebDriverException:
                        continue
        for _ in range(3):
            try:
                clicked = driver.execute_script(
                    """
                    const isVisible = (el) => {
                      const rect = el.getBoundingClientRect();
                      const style = window.getComputedStyle(el);
                      return rect.width > 0 && rect.height > 0 &&
                        style.visibility !== 'hidden' &&
                        style.display !== 'none';
                    };

                    const clickElement = (el) => {
                      ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
                        el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                      });
                    };

                    const elements = Array.from(document.querySelectorAll('button, [role="button"]'));
                    const target = elements.find(el => isVisible(el) && (el.innerText || '').trim().includes('ADICIONAR'));
                    if (!target) return false;
                    const clickable = target.closest('button, [role="button"]') || target;
                    clickable.scrollIntoView({ block: 'center', inline: 'center' });
                    clickElement(clickable);
                    return true;
                    """
                )
                if clicked and self._wait_for_observation_modal(timeout_seconds=quick_timeout):
                    LOGGER.info("Botao ADICIONAR acionado via busca JavaScript por texto.")
                    return
            except WebDriverException:
                LOGGER.debug("Falha na tentativa de clicar em ADICIONAR via JavaScript.")
            time.sleep(0.6)

        raise RuntimeError("Nao foi possivel localizar botao ADICIONAR.")

    def _obs_panel_is_open(self) -> bool:
        candidates = [
            (By.XPATH, "//button[contains(., 'ADICIONAR')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'ADICIONAR')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'Nao existem observacoes nesse cliente')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'Não existem observações nesse cliente')]"),
        ]
        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

    def _wait_for_obs_context(self) -> None:
        end_time = time.time() + min(3.0, float(self.settings.hubsoft_element_timeout_seconds))
        while time.time() < end_time:
            if self._any_visible(
                [
                    (By.XPATH, "//*[normalize-space()='ANEXOS']"),
                    (By.XPATH, "//*[normalize-space()='CONTATOS']"),
                    (By.XPATH, "//span[contains(@aria-label, 'Observ')]"),
                    (By.XPATH, "//span[normalize-space()='OBS']"),
                ]
            ):
                return
            time.sleep(0.2)
        LOGGER.debug("Contexto das abas do cadastro nao apareceu rapidamente; seguindo com tentativas diretas.")

    def _wait_for_obs_panel(self) -> bool:
        end_time = time.time() + self.settings.hubsoft_element_timeout_seconds
        while time.time() < end_time:
            if self._obs_panel_is_open():
                return True
            time.sleep(0.4)
        return False

    def _wait_for_obs_selected(self, timeout_seconds: float | None = None) -> bool:
        timeout = timeout_seconds or float(self.settings.hubsoft_element_timeout_seconds)
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._obs_tab_is_selected() or self._obs_panel_is_open():
                return True
            time.sleep(0.3)
        return False

    def _obs_tab_is_selected(self) -> bool:
        candidates = [
            (By.XPATH, "//button[contains(@class, 'md-accent')][.//span[contains(@aria-label, 'Observ')]]"),
            (By.XPATH, "//span[contains(@aria-label, 'Observ')]/ancestor::button[contains(@class, 'md-accent') or contains(@class, 'md-selected')][1]"),
            (By.XPATH, "//button[contains(@class, 'md-accent')][.//*[normalize-space()='OBS']]"),
            (By.XPATH, "//*[normalize-space()='OBS']/ancestor::button[contains(@class, 'md-accent') or contains(@class, 'md-selected')][1]"),
        ]
        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

    def _wait_for_observation_modal(self, timeout_seconds: float | None = None) -> bool:
        timeout = timeout_seconds or float(self.settings.hubsoft_element_timeout_seconds)
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._observation_modal_is_open():
                return True
            time.sleep(0.3)
        return False

    def _observation_modal_is_open(self) -> bool:
        candidates = [
            (By.XPATH, "//textarea"),
            (By.XPATH, "//*[contains(normalize-space(), 'Adicionar Observacao')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'Adicionar Observação')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'Visualizacao obrigatoria?')]"),
            (By.XPATH, "//*[contains(normalize-space(), 'Visualização obrigatória?')]"),
        ]
        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

    def _enable_visualizacao_obrigatoria(self) -> None:
        if self._visualizacao_ja_esta_ativa():
            LOGGER.info("Visualizacao obrigatoria ja estava marcada como Sim.")
            return

        if self._click_visualizacao_switch_once() or self._click_visualizacao_once():
            if self._wait_for_visualizacao_ativa():
                LOGGER.info("Toggle de visualizacao obrigatoria acionado com clique unico.")
                return
            LOGGER.debug("Clique no toggle foi executado, mas o texto ainda nao mudou para Sim.")

        checkbox_candidates = [
            (By.CSS_SELECTOR, "input[type='checkbox']"),
            (By.XPATH, "//input[@type='checkbox']"),
        ]
        for by, selector in checkbox_candidates:
            for element in self._find_elements(by, selector):
                try:
                    if not element.is_displayed():
                        continue
                    self._scroll_into_view(element)
                    if not element.is_selected():
                        element.click()
                    if self._wait_for_visualizacao_ativa():
                        LOGGER.info("Toggle de visualizacao obrigatoria acionado via checkbox.")
                        return
                except WebDriverException:
                    continue

        raise RuntimeError("Nao foi possivel localizar toggle de visualizacao obrigatoria.")

    def _click_visualizacao_once(self) -> bool:
        label_candidates = [
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria? Nao')]"),
            (By.XPATH, "//*[contains(., 'Visualização obrigatória? Não')]"),
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria?')]"),
            (By.XPATH, "//*[contains(., 'Visualização obrigatória?')]"),
        ]

        for by, selector in label_candidates:
            for element in self._find_elements(by, selector):
                try:
                    if not element.is_displayed():
                        continue
                    self._scroll_into_view(element)
                    ActionChains(self._require_driver()).move_to_element(element).click().perform()
                    time.sleep(0.7)
                    return True
                except WebDriverException:
                    try:
                        self._require_driver().execute_script("arguments[0].click();", element)
                        time.sleep(0.7)
                        return True
                    except WebDriverException:
                        continue
        return False

    def _visualizacao_ja_esta_ativa(self) -> bool:
        candidates = [
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria? Sim')]"),
            (By.XPATH, "//*[contains(., 'Visualização obrigatória? Sim')]"),
        ]
        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

    def _wait_for_visualizacao_ativa(self) -> bool:
        end_time = time.time() + 3.0
        while time.time() < end_time:
            if self._visualizacao_ja_esta_ativa():
                return True
            time.sleep(0.2)
        return False

    def _click_visualizacao_switch_once(self) -> bool:
        switch_candidates = [
            (By.XPATH, "//md-switch[.//*[contains(., 'Visualizacao obrigatoria?')]]"),
            (By.XPATH, "//md-switch[.//*[contains(., 'VisualizaÃ§Ã£o obrigatÃ³ria?')]]"),
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria?')]/ancestor::md-switch[1]"),
            (By.XPATH, "//*[contains(., 'VisualizaÃ§Ã£o obrigatÃ³ria?')]/ancestor::md-switch[1]"),
        ]

        for by, selector in switch_candidates:
            for element in self._find_elements(by, selector):
                try:
                    if not element.is_displayed():
                        continue
                    target = self._resolve_visualizacao_target(element)
                    self._scroll_into_view(target)
                    ActionChains(self._require_driver()).move_to_element(target).pause(0.2).click().perform()
                    time.sleep(0.5)
                    return True
                except WebDriverException:
                    try:
                        target = self._resolve_visualizacao_target(element)
                        self._require_driver().execute_script("arguments[0].click();", target)
                        time.sleep(0.5)
                        return True
                    except WebDriverException:
                        continue

        try:
            clicked = self._require_driver().execute_script(
                """
                const normalize = (value) =>
                  (value || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .trim()
                    .toLowerCase();

                const isVisible = (el) => {
                  const rect = el.getBoundingClientRect();
                  const style = window.getComputedStyle(el);
                  return rect.width > 0 && rect.height > 0 &&
                    style.visibility !== 'hidden' &&
                    style.display !== 'none';
                };

                const switchNode = Array.from(document.querySelectorAll('md-switch')).find(el => {
                  if (!isVisible(el)) return false;
                  const text = normalize(el.innerText);
                  return text.includes('visualizacao obrigatoria');
                });
                if (!switchNode) return false;
                const target = switchNode.querySelector('.md-container, .md-bar, .md-thumb-container') || switchNode;
                target.scrollIntoView({ block: 'center', inline: 'center' });
                ['mouseover', 'mousedown', 'mouseup', 'click'].forEach(type => {
                  target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                });
                return true;
                """
            )
            if clicked:
                time.sleep(0.5)
                return True
        except WebDriverException:
            LOGGER.debug("Falha na tentativa de clicar no md-switch via JavaScript.")
        return False

    def _resolve_visualizacao_target(self, element: WebElement) -> WebElement:
        try:
            target = self._require_driver().execute_script(
                """
                const root = arguments[0].closest('md-switch') || arguments[0];
                return root.querySelector('.md-container, .md-bar, .md-thumb-container') || root;
                """,
                element,
            )
            if isinstance(target, WebElement):
                return target
        except WebDriverException:
            pass
        return element

    def _click_first(self, description: str, locators: list[Locator]) -> None:
        for by, selector in locators:
            try:
                element = self._wait_clickable(by, selector)
                self._scroll_into_view(element)
                element.click()
                LOGGER.debug("Clique realizado em %s.", description)
                return
            except (TimeoutException, WebDriverException):
                continue
        raise RuntimeError(f"Nao foi possivel localizar {description}.")

    def _fill_first(self, description: str, value: str, locators: list[Locator]) -> None:
        for by, selector in locators:
            try:
                element = self._wait_visible(by, selector)
                self._scroll_into_view(element)
                element.clear()
                element.send_keys(value)
                LOGGER.debug("Preenchimento realizado em %s.", description)
                return
            except (TimeoutException, WebDriverException):
                continue
        raise RuntimeError(f"Nao foi possivel localizar {description}.")

    def _wait_clickable(self, by: str, selector: str) -> WebElement:
        wait = self._require_wait()
        return wait.until(EC.element_to_be_clickable((by, selector)))

    def _wait_visible(self, by: str, selector: str) -> WebElement:
        wait = self._require_wait()
        return wait.until(EC.visibility_of_element_located((by, selector)))

    def _find_elements(self, by: str, selector: str) -> list[WebElement]:
        driver = self._require_driver()
        try:
            return driver.find_elements(by, selector)
        except NoSuchElementException:
            return []

    def _any_visible(self, locators: list[Locator]) -> bool:
        for by, selector in locators:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

    def _scroll_into_view(self, element: WebElement) -> None:
        try:
            self._require_driver().execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except WebDriverException:
            return

    def _resolve_click_target(self, element: WebElement) -> WebElement:
        try:
            target = self._require_driver().execute_script(
                """
                return arguments[0].closest('button, a, [role="button"], div, span, li') || arguments[0];
                """,
                element,
            )
            if isinstance(target, WebElement):
                return target
        except WebDriverException:
            pass
        return element

    def _require_driver(self) -> WebDriver:
        if self._driver is None:
            raise RuntimeError("Browser nao foi iniciado.")
        return self._driver

    def _require_wait(self) -> WebDriverWait:
        if self._wait is None:
            raise RuntimeError("Browser nao foi iniciado.")
        return self._wait
