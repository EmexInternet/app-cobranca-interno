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

        storage_dir = Path(self.settings.hubsoft_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        options = Options()
        options.add_argument(f"--user-data-dir={storage_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1200")
        if self.headless:
            options.add_argument("--headless=new")
        if self.settings.hubsoft_chrome_binary_path:
            options.binary_location = self.settings.hubsoft_chrome_binary_path

        self._driver = webdriver.Chrome(options=options)
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
        driver = self._require_driver()
        target_url = f"{self.settings.hubsoft_web_url.rstrip('/')}/cliente/editar/{id_cliente}/cadastro"
        self.ensure_logged_in(target_url=target_url)

        LOGGER.info("Abrindo cadastro do cliente %s para adicionar observacao.", id_cliente)
        driver.get(target_url)
        time.sleep(1)

        self._click_first(
            "aba OBS",
            [
                (By.XPATH, "//*[normalize-space()='OBS']"),
                (By.XPATH, "//*[contains(normalize-space(), 'OBS')]"),
            ],
        )
        time.sleep(1)

        self._click_first(
            "botao ADICIONAR",
            [
                (By.XPATH, "//button[contains(., 'ADICIONAR')]"),
                (By.XPATH, "//*[contains(normalize-space(), 'ADICIONAR')]"),
            ],
        )
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
                (By.XPATH, "//input[contains(@name, 'senha') or contains(@name, 'password') or contains(@id, 'senha') or contains(@id, 'password')]"),
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

    def _enable_visualizacao_obrigatoria(self) -> None:
        if self._visualizacao_ja_esta_ativa():
            LOGGER.info("Visualizacao obrigatoria ja estava marcada como Sim.")
            return

        if self._click_visualizacao_once():
            LOGGER.info("Toggle de visualizacao obrigatoria acionado com clique unico.")
            return

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
                    return
                except WebDriverException:
                    continue

        raise RuntimeError("Nao foi possivel localizar toggle de visualizacao obrigatoria.")

    def _click_visualizacao_once(self) -> bool:
        label_candidates = [
            (By.XPATH, "//*[contains(., 'Visualização obrigatória? Não')]"),
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria? Nao')]"),
            (By.XPATH, "//*[contains(., 'Visualização obrigatória?')]"),
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria?')]"),
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
            (By.XPATH, "//*[contains(., 'Visualização obrigatória? Sim')]"),
            (By.XPATH, "//*[contains(., 'Visualizacao obrigatoria? Sim')]"),
        ]
        for by, selector in candidates:
            for element in self._find_elements(by, selector):
                try:
                    if element.is_displayed():
                        return True
                except WebDriverException:
                    continue
        return False

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

    def _scroll_into_view(self, element: WebElement) -> None:
        try:
            self._require_driver().execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except WebDriverException:
            return

    def _require_driver(self) -> WebDriver:
        if self._driver is None:
            raise RuntimeError("Browser nao foi iniciado.")
        return self._driver

    def _require_wait(self) -> WebDriverWait:
        if self._wait is None:
            raise RuntimeError("Browser nao foi iniciado.")
        return self._wait
