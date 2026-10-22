"""Navegació del cercador i descoberta d'URL de l'Agenda Cultural."""

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from playwright.sync_api import Page, expect


EVENT_LINKS = ".results__articleItem_denominacio a"
SELECTED_PAGE = ".results__pagination_page.selected"
EVENT_PATH = re.compile(r"^/ca/activitat\.html/\d+/[^/]+/?$")


def normalize_event_url(href: str, base_url: str) -> str | None:
    """Acceptar fitxes del mateix servidor i port, sense navegació ni seguiment."""
    if not href or not href.strip():
        return None

    try:
        base = urlsplit(base_url)
        parts = urlsplit(urljoin(base_url, href.strip()))
        if (
            parts.scheme not in {"http", "https"}
            or parts.hostname != base.hostname
            or parts.port != base.port
            or parts.username is not None
            or parts.password is not None
            or not EVENT_PATH.fullmatch(parts.path)
        ):
            return None
    except ValueError:
        return None

    # En les fitxes, page és context de navegació, no l'identificador de l'event.
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != "page" and not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(query), "")
    )


def extract_event_urls(page: Page) -> list[str]:
    """Llegir les fitxes un cop els resultats i la paginació són visibles."""
    page.locator(SELECTED_PAGE).wait_for(state="visible")
    links = page.locator(EVENT_LINKS)
    links.first.wait_for(state="visible")
    hrefs = links.evaluate_all("elements => elements.map(el => el.getAttribute('href'))")

    urls = []
    for href in hrefs:
        url = normalize_event_url(href or "", page.url)
        if url is not None:
            urls.append(url)

    if not urls:
        raise RuntimeError("No s'ha trobat cap URL vàlida a les fitxes dels resultats.")
    return urls


def discover_first_page(page: Page, initial_url: str) -> list[str]:
    """Obrir el formulari públic i extreure només la primera pàgina de la cerca."""
    reject_cookies = page.locator("#ppms_cm_reject-all")
    # L'avís pot aparèixer més tard i bloquejar una interacció amb el formulari.
    page.add_locator_handler(reject_cookies, lambda locator: locator.click())
    try:
        response = page.goto(initial_url, wait_until="domcontentloaded")
        if response is not None and response.status >= 400:
            raise RuntimeError(f"El servidor ha retornat HTTP {response.status}.")

        page.locator("#keywords").fill("")
        without_dates = page.locator('input[name="quan"][value=""]')
        if not without_dates.is_checked():
            if not without_dates.is_visible():
                page.locator("#headingTwo").click()
            without_dates.check()

        page.locator("#cerca-button").click()
        page.wait_for_url("**/ca/resultats.html/**")
        # La paginació apareix després de construir el llistat dinàmic.
        expect(page.locator(SELECTED_PAGE)).to_have_text("1", timeout=30_000)
        return extract_event_urls(page)
    finally:
        if not page.is_closed():
            page.remove_locator_handler(reject_cookies)
