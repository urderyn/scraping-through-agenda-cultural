"""Punt d'entrada del projecte: configuració i descoberta de la primera pàgina."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import dotenv_values
from playwright.sync_api import Error as PlaywrightError

from browser import Browser
from discover import discover_first_page, read_event_csv, save_event_urls

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
        description="Descobrir la primera pàgina de l’Agenda i afegir les URL noves al CSV."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Mostrar la finestra del navegador."
    )
    arguments = parser.parse_args()

    try:
        configuration = load_configuration()
    except ConfigurationError as error:
        print(f"Error de configuració: {error}", file=sys.stderr)
        return 2

    try:
        _, existing_rows = read_event_csv(configuration.dataset_path, configuration.url)
        print(f"URL ja desades: {len(existing_rows)}")
        with Browser(headless=not arguments.headed) as browser:
            print(f"User-Agent efectiu: {browser.page.evaluate('navigator.userAgent')}")
            urls = discover_first_page(browser.page, configuration.url)
            print(f"Pàgina oberta: {browser.page.title()}")
            print(f"URL d'esdeveniments de la primera pàgina: {len(urls)}")
            for index, url in enumerate(urls, start=1):
                print(f"{index}. {url}")
            added = save_event_urls(configuration.dataset_path, urls, configuration.url)
            print(f"URL noves afegides: {added}")
            print(f"URL totals al CSV: {len(existing_rows) + added}")
            print(f"CSV: {configuration.dataset_path}")
    except (PlaywrightError, RuntimeError) as error:
        print(f"Error d’execució: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Execució interrompuda; recursos del navegador alliberats.", file=sys.stderr)
        return 130

    print("Execució finalitzada i navegador tancat correctament.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
