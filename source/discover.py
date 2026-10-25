"""Navegació del cercador i descoberta d'URL de l'Agenda Cultural."""

import csv
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
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
        (parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
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


class DatasetError(RuntimeError):
    """El CSV no es pot processar sense posar en risc les dades existents."""


def read_event_csv(
    csv_path: Path, base_url: str
) -> tuple[list[str], list[dict[str, str]]]:
    """Llegir i validar el CSV conservant l'ordre, les columnes i els valors."""
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            fields = reader.fieldnames
            if (
                not fields
                or "url" not in fields
                or len(fields) != len(set(fields))
                or any(not field.strip() for field in fields)
            ):
                raise DatasetError(
                    "El CSV ha de tenir una capçalera amb la columna url, "
                    "sense noms de columna buits ni repetits. No s'ha modificat."
                )

            rows = []
            known_urls = set()
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise DatasetError(
                        f"La fila {reader.line_num} del CSV no té el nombre "
                        "de camps de la capçalera. No s'ha modificat."
                    )
                normalized = normalize_event_url(row["url"], base_url)
                if normalized is None:
                    raise DatasetError(
                        f"La fila {reader.line_num} del CSV té una URL buida "
                        "o no vàlida per a l'Agenda configurada. No s'ha modificat."
                    )
                if normalized in known_urls:
                    raise DatasetError(
                        "El CSV existent conté URL duplicades després de normalitzar-les. "
                        "Cal revisar-les abans de continuar; no s'ha modificat."
                    )
                known_urls.add(normalized)
                rows.append(row)
            return fields, rows
    except FileNotFoundError:
        return ["url"], []
    except (OSError, UnicodeError, csv.Error) as error:
        raise DatasetError(f"No s'ha pogut llegir el CSV: {error}") from error


def save_event_urls(csv_path: Path, urls: list[str], base_url: str) -> int:
    """Afegir només URL noves i retornar el nombre de files incorporades."""
    fields, rows = read_event_csv(csv_path, base_url)
    known_urls = {normalize_event_url(row["url"], base_url) for row in rows}
    new_rows = []
    for url in urls:
        normalized = normalize_event_url(url, base_url)
        if normalized is None:
            raise DatasetError("S'ha rebut una URL no vàlida. No s'ha modificat el CSV.")
        if normalized not in known_urls:
            # Les columnes d'enriquiment es conserven; les files noves les deixen buides.
            row = dict.fromkeys(fields, "")
            row["url"] = normalized
            new_rows.append(row)
            known_urls.add(normalized)

    # Una execució sense novetats no reescriu ni canvia el fitxer existent.
    if not new_rows and csv_path.exists():
        return 0

    try:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        # El temporal és al mateix sistema de fitxers per substituir el CSV atòmicament.
        with TemporaryDirectory(prefix=f".{csv_path.name}-", dir=csv_path.parent) as directory:
            temporary_path = Path(directory) / csv_path.name
            with temporary_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                writer.writerows(new_rows)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, csv_path)
    except (OSError, UnicodeError, csv.Error) as error:
        raise DatasetError(f"No s'ha pogut desar el CSV: {error}") from error

    return len(new_rows)
