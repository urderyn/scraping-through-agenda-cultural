"""Punt d'entrada: configuració, descoberta paginada i desament incremental."""

import argparse
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import dotenv_values
from playwright.sync_api import Error as PlaywrightError

from browser import Browser
from discover import discover_pages, read_event_csv, save_event_urls

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(ValueError):
    """La configuració local és absent o no és vàlida."""


@dataclass(frozen=True)
class Configuration:
    url: str
    dataset_path: Path


def load_configuration(project_root: Path = PROJECT_ROOT) -> Configuration:
    project_root = project_root.resolve()
    env_path = project_root / ".env"
    if not env_path.is_file():
        raise ConfigurationError(
            "Falta el fitxer .env a l'arrel del projecte. "
            "Copia .env.example a .env i configura URL."
        )

    values = dotenv_values(env_path)
    url = (values.get("URL"))

    if not url:
        raise ConfigurationError('No sha trobat el parametre URL')

    return Configuration(
        url=url,
        dataset_path=project_root / "dataset" / "events.csv",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recórrer l’Agenda i afegir les URL noves al CSV després de cada pàgina."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Mostrar la finestra del navegador."
    )
    parser.add_argument(
        "--max-pages", type=int, metavar="N",
        help="Limitar la comprovació manual a N pàgines; per defecte es recorren totes.",
    )
    arguments = parser.parse_args()
    if arguments.max_pages is not None and arguments.max_pages < 1:
        parser.error("--max-pages ha de ser un enter positiu.")

    try:
        configuration = load_configuration()
    except ConfigurationError as error:
        print(f"Error de configuració: {error}", file=sys.stderr)
        return 2

    processed_pages = 0
    added_total = 0
    complete = False
    try:
        _, existing_rows = read_event_csv(configuration.dataset_path, configuration.url)
        print(f"URL ja desades: {len(existing_rows)}")
        with Browser(headless=not arguments.headed) as browser:
            print(f"User-Agent efectiu: {browser.page.evaluate('navigator.userAgent')}")
            with closing(discover_pages(browser.page, configuration.url)) as pages:
                for result in pages:
                    added = save_event_urls(
                        configuration.dataset_path, result.urls, configuration.url
                    )
                    processed_pages += 1
                    added_total += added
                    print(
                        f"Pàgina {result.number}: {len(result.urls)} URL, "
                        f"{added} noves; total al CSV: {len(existing_rows) + added_total}",
                        flush=True,
                    )
                    complete = result.is_last
                    if complete or (
                        arguments.max_pages is not None
                        and processed_pages >= arguments.max_pages
                    ):
                        break
            print(f"Pàgines processades: {processed_pages}")
            print(f"URL noves afegides: {added_total}")
            print(f"URL totals al CSV: {len(existing_rows) + added_total}")
            print(f"CSV: {configuration.dataset_path}")
    except (PlaywrightError, RuntimeError) as error:
        print(
            f"Recorregut incomplet: {processed_pages} pàgines desades, "
            f"{added_total} URL noves. Error d’execució: {error}", file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            f"Recorregut interromput: {processed_pages} pàgines desades. "
            "Es conserva el progrés guardat i es tanca el navegador.", file=sys.stderr,
        )
        return 130

    if complete:
        print("Recorregut complet: control de pàgina següent desactivat.")
    else:
        print("Comprovació limitada amb --max-pages; el recorregut és parcial.")
    print("Navegador tancat correctament.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
