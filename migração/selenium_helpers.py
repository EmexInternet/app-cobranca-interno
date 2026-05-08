from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
import time
from typing import Any, Callable

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    JavascriptException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver import Chrome, Edge, Firefox
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from migração.config import Settings

Locator = tuple[str, str]


def build_driver(settings: Settings) -> WebDriver:
    profile_dir = _resolve_profile_dir(settings.browser_profile_dir)

    if settings.browser == "firefox":
        options = FirefoxOptions()
        if settings.headless:
            options.add_argument("-headless")
        if settings.browser_binary_path:
            options.binary_location = settings.browser_binary_path
        if profile_dir:
            options.add_argument("-profile")
            options.add_argument(profile_dir)
        driver = Firefox(options=options)
        driver.set_page_load_timeout(settings.selenium_max_wait)
        return driver

    if settings.browser == "edge":
        options = EdgeOptions()
        if settings.headless:
            options.add_argument("--headless=new")
        if settings.browser_binary_path:
            options.binary_location = settings.browser_binary_path
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument(f"--profile-directory={settings.browser_profile_name}")
        options.add_argument("--window-size=1600,1200")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        driver = Edge(options=options)
        driver.set_page_load_timeout(settings.selenium_max_wait)
        return driver

    options = ChromeOptions()
    if settings.headless:
        options.add_argument("--headless=new")
    if settings.browser_binary_path:
        options.binary_location = settings.browser_binary_path
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument(f"--profile-directory={settings.browser_profile_name}")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    driver = Chrome(options=options)
    driver.set_page_load_timeout(settings.selenium_max_wait)
    return driver


def _resolve_profile_dir(raw_profile_dir: str) -> str:
    if not raw_profile_dir:
        return ""

    expanded = os.path.expandvars(os.path.expanduser(raw_profile_dir))
    profile_path = Path(expanded)
    if not profile_path.is_absolute():
        profile_path = Path.cwd() / profile_path

    profile_path.mkdir(parents=True, exist_ok=True)
    return str(profile_path.resolve())


class BrowserSession:
    def __init__(
        self,
        driver: WebDriver,
        timeout: int,
        *,
        validation_interval: int = 10,
        max_wait: int = 60,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)
        self.validation_interval = max(1, validation_interval)
        self.max_wait = max(self.validation_interval, max_wait)
        self.logger = logger

    def _log(self, message: str) -> None:
        if self.logger is not None:
            self.logger(message)
        else:
            print(f"[wait] {message}", flush=True)

    def until(self, description: str, condition: Callable[[WebDriver], Any]) -> Any:
        started_at = time.monotonic()
        attempts = 0
        last_error: Exception | None = None

        while True:
            elapsed = int(time.monotonic() - started_at)
            remaining = self.max_wait - elapsed
            if remaining <= 0:
                break

            attempts += 1
            window_timeout = min(self.validation_interval, remaining)
            try:
                return WebDriverWait(self.driver, window_timeout, poll_frequency=0.5).until(condition)
            except TimeoutException as error:
                last_error = error
                waited_so_far = min(attempts * self.validation_interval, self.max_wait)
                self._log(f"{description}: aguardando {waited_so_far}/{self.max_wait}s")

        raise TimeoutException(f"{description}: tempo limite de {self.max_wait}s excedido.") from last_error

    def open(self, url: str) -> None:
        self.driver.get(url)

    def wait_for_any(self, locators: Iterable[Locator]) -> WebElement:
        locators = list(locators)
        return self.until(
            f"Nenhum elemento encontrado para os locators: {locators}",
            lambda driver: next(
                (
                    elements[0]
                    for locator in locators
                    for elements in [driver.find_elements(*locator)]
                    if elements
                ),
                False,
            ),
        )

    def wait_for_visible_any(self, locators: Iterable[Locator]) -> WebElement:
        locators = list(locators)
        return self.until(
            f"Nenhum elemento visivel encontrado para os locators: {locators}",
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

    def wait_for_clickable_any(self, locators: Iterable[Locator]) -> WebElement:
        locators = list(locators)
        return self.until(
            f"Nenhum elemento clicavel encontrado para os locators: {locators}",
            lambda driver: next(
                (
                    element
                    for locator in locators
                    for element in driver.find_elements(*locator)
                    if element.is_displayed() and element.is_enabled()
                ),
                False,
            ),
        )

    def click_any(self, locators: Iterable[Locator]) -> WebElement:
        element = self.wait_for_clickable_any(locators)
        self.click(element)
        return element

    def click(self, element: WebElement) -> None:
        try:
            element.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            self.driver.execute_script("arguments[0].click();", element)

    def set_value(self, element: WebElement, value: str) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        try:
            element.clear()
        except Exception:
            pass
        element.send_keys(value)

    def set_value_via_js(self, element: WebElement, value: str) -> None:
        script = """
            const element = arguments[0];
            const value = arguments[1];
            element.focus();
            element.value = value;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.blur();
        """
        self.driver.execute_script(script, element, value)

    def find_near_label(self, label_text: str, tag_names: tuple[str, ...] = ("input", "textarea", "select")) -> WebElement:
        label_xpath = (
            "//*[self::label or self::span or self::div or self::p]"
            f"[contains(translate(normalize-space(.),"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÀÃÂÉÊÍÓÔÕÚÇ',"
            "'abcdefghijklmnopqrstuvwxyzáàãâéêíóôõúç'),"
            f"'{label_text.lower()}')]"
        )
        tag_predicate = " or ".join([f"self::{tag_name}" for tag_name in tag_names])
        candidates = [
            (
                By.XPATH,
                f"{label_xpath}/following::*[{tag_predicate}][1]",
            ),
            (
                By.XPATH,
                f"{label_xpath}/ancestor::*[self::div or self::td or self::fieldset][1]//*[{tag_predicate}][1]",
            ),
        ]
        return self.wait_for_visible_any(candidates)

    def select_by_visible_text_or_custom(self, label_text: str, option_text: str) -> None:
        element = self.find_near_label(label_text, ("select", "input", "div"))
        tag_name = element.tag_name.lower()

        if tag_name == "select":
            Select(element).select_by_visible_text(option_text)
            return

        clickable_dropdowns = [element]
        try:
            clickable_dropdowns.append(
                element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'select') or contains(@class, 'dropdown')][1]")
            )
        except NoSuchElementException:
            pass
        for dropdown in clickable_dropdowns:
            try:
                self.click(dropdown)
                break
            except Exception:
                continue

        option_locators = [
            (
                By.XPATH,
                f"//*[self::li or self::span or self::div][normalize-space(.)='{option_text}']",
            ),
            (
                By.XPATH,
                f"//*[self::li or self::span or self::div][contains(normalize-space(.), '{option_text}')]",
            ),
        ]
        self.click_any(option_locators)

    def click_button_by_text(self, text: str) -> None:
        locators = [
            (By.XPATH, f"//button[normalize-space(.)='{text}']"),
            (By.XPATH, f"//a[normalize-space(.)='{text}']"),
            (By.XPATH, f"//*[@role='button'][normalize-space(.)='{text}']"),
            (By.XPATH, f"//button[contains(normalize-space(.), '{text}')]"),
            (By.XPATH, f"//a[contains(normalize-space(.), '{text}')]"),
        ]
        self.click_any(locators)

    def click_menu_item(self, text: str) -> None:
        locators = [
            (By.XPATH, f"//*[self::a or self::button or self::li or self::span][normalize-space(.)='{text}']"),
            (By.XPATH, f"//*[self::a or self::button or self::li or self::span][contains(normalize-space(.), '{text}')]"),
        ]
        self.click_any(locators)

    def element_exists(self, locators: Iterable[Locator]) -> bool:
        for by, value in locators:
            try:
                if self.driver.find_elements(by, value):
                    return True
            except NoSuchElementException:
                continue
        return False

    def wait_url_contains(self, fragment: str) -> None:
        self.until(f"URL nao contem '{fragment}'", EC.url_contains(fragment))

    def try_click_text(self, text: str) -> bool:
        try:
            self.click_button_by_text(text)
            return True
        except TimeoutException:
            return False
