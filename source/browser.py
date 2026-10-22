"""Gestió reutilitzable del navegador de Playwright."""

from contextlib import ExitStack
from types import TracebackType

from playwright.sync_api import Page, sync_playwright


class Browser:
    """Obrir Chromium i alliberar-ne els recursos en sortir del bloc with."""

    def __init__(
        self,
        *,
        headless: bool = True,
        user_agent: str = "AgendaCulturalScraper/0.1 (academic project; UOC)",
        timeout_ms: int = 30_000,
        navigation_timeout_ms: int = 45_000,
    ) -> None:

        self.headless = headless
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self.navigation_timeout_ms = navigation_timeout_ms
        self._resources: ExitStack | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        return self._page

    def __enter__(self) -> "Browser":
        with ExitStack() as resources:
            playwright = sync_playwright().start()
            resources.callback(playwright.stop)

            browser = playwright.chromium.launch(headless=self.headless)
            resources.callback(browser.close)

            context = browser.new_context(user_agent=self.user_agent)
            resources.callback(context.close)
            context.set_default_timeout(self.timeout_ms)
            context.set_default_navigation_timeout(self.navigation_timeout_ms)

            self._page = context.new_page()
            self._resources = resources.pop_all()

        return self

    def close(self) -> None:
        resources = self._resources
        self._resources = None
        self._page = None
        if resources is not None:
            resources.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
