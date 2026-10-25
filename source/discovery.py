from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sys

from playwright.sync_api import Error as PlaywrightError, Page

from browser import Browser
from event_csv_repository import EventCsvRepository
from event_urls import normalize_event_url


EVENT_LINKS = ".results__articleItem_denominacio a"
SELECTED_PAGE = ".results__pagination_page.selected"
PAGINATION = ".results__pagination"
NEXT_PAGE = ".results__pagination_nextPage"
LAST_PAGE = ".results__pagination_lastPage"


@dataclass(frozen=True)
class DiscoveredPage:
    number: int
    urls: list[str]
    is_last: bool


def execute(url: str, dataset_path: Path, *, headed: bool = False) -> int:
    """Run discovery to completion, save each page, and return the exit status."""
    processed_pages = 0
    added_total = 0
    complete = False
    try:
        repository = EventCsvRepository(dataset_path, url)
        _, existing_rows = repository.read()
        print(f"Previously saved URLs: {len(existing_rows)}")
        with Browser(headless=not headed) as browser:
            print(f"Effective User-Agent: {browser.page.evaluate('navigator.userAgent')}")
            with closing(__discover_pages(browser.page, url)) as pages:
                for result in pages:
                    added = repository.save_urls(result.urls)
                    processed_pages += 1
                    added_total += added
                    print(
                        f"Page {result.number}: {len(result.urls)} URLs, "
                        f"{added} new; total in CSV: {len(existing_rows) + added_total}",
                        flush=True,
                    )
                    complete = result.is_last
            if not complete:
                raise RuntimeError("Discovery ended before reaching the last page.")
            print(f"Pages processed: {processed_pages}")
            print(f"New URLs added: {added_total}")
            print(f"Total URLs in CSV: {len(existing_rows) + added_total}")
            print(f"CSV: {dataset_path}")
    except (PlaywrightError, RuntimeError) as error:
        print(
            f"Incomplete run: {processed_pages} pages saved, "
            f"{added_total} new URLs. Execution error: {error}", file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            f"Run interrupted: {processed_pages} pages saved. "
            "Saved progress is preserved and the browser is closed.", file=sys.stderr,
        )
        return 130

    print("Run complete: the next-page control is disabled.")
    print("Browser closed successfully.")
    return 0


def __wait_for_results(page: Page, number: int) -> None:
    """Wait for the expected page number and a consistently loaded result list."""
    page.wait_for_function(
        """({pagination, selected, links, next, last, number}) => {
            const pager = document.querySelector(pagination);
            const current = document.querySelector(selected);
            const nextControl = document.querySelector(next);
            const lastControl = document.querySelector(last);
            if (!pager || !current || !nextControl || !lastControl) return false;
            const size = Number(pager.dataset.pagesize);
            if (!Number.isInteger(size) || size < 1 ||
                Number(current.textContent.trim()) !== number ||
                Number(current.dataset.pagestart) !== (number - 1) * size) return false;
            const atEnd = nextControl.classList.contains('nextPage-disabled');
            if (atEnd !== lastControl.classList.contains('nextPage-disabled')) return false;
            const cards = Array.from(document.querySelectorAll(links));
            if (!cards.length || cards.length > size || (!atEnd && cards.length !== size))
                return false;
            return cards.every(el => el.getAttribute('href'));
        }""",
        arg={
            "pagination": PAGINATION,
            "selected": SELECTED_PAGE,
            "links": EVENT_LINKS,
            "next": NEXT_PAGE,
            "last": LAST_PAGE,
            "number": number,
        },
        timeout=30_000,
    )


def __extract_event_urls(page: Page) -> list[str]:
    """Read event cards once the results and pagination are visible."""
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
        raise RuntimeError("No valid URLs were found in the result cards.")
    return urls


def __discover_pages(page: Page, initial_url: str) -> Iterator[DiscoveredPage]:
    """Yield each page before advancing, until the next-page control is disabled."""
    reject_cookies = page.locator("#ppms_cm_reject-all")
    # Reject optional cookies.
    page.add_locator_handler(reject_cookies, lambda locator: locator.click())
    try:
        response = page.goto(initial_url, wait_until="domcontentloaded")
        if response is not None and response.status >= 400:
            raise RuntimeError(f"The server returned HTTP {response.status}.")

        page.locator("#keywords").fill("")
        without_dates = page.locator('input[name="quan"][value=""]')
        if not without_dates.is_checked():
            if not without_dates.is_visible():
                page.locator("#headingTwo").click()
            without_dates.check()

        page.locator("#cerca-button").click()
        page.wait_for_url("**/ca/resultats.html/**")
        number = 1
        while True:
            __wait_for_results(page, number)
            urls = __extract_event_urls(page)
            is_last = page.locator(NEXT_PAGE).evaluate(
                "el => el.classList.contains('nextPage-disabled')"
            )
            yield DiscoveredPage(number=number, urls=urls, is_last=is_last)
            if is_last:
                return

            page.wait_for_timeout(1_000)
            previous_card = page.locator(EVENT_LINKS).first.element_handle()
            if previous_card is None:
                raise RuntimeError("The result list disappeared before changing pages.")
            try:
                page.locator(f"{NEXT_PAGE} a").click()
                # Wait for the result DOM to be replaced.
                page.wait_for_function(
                    "element => !element.isConnected", arg=previous_card, timeout=30_000
                )
            finally:
                previous_card.dispose()
            number += 1
    finally:
        if not page.is_closed():
            page.remove_locator_handler(reject_cookies)
