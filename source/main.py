"""Punt d'entrada del projecte i validació de la configuració local."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import dotenv_values
from playwright.sync_api import Error as PlaywrightError

from browser import Browser

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
        description="Obrir l'Agenda amb Playwright i comprovar el navegador."
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
        with Browser(headless=not arguments.headed) as browser:
            response = browser.page.goto(
                configuration.url, wait_until="domcontentloaded"
            )
            if response is not None and response.status >= 400:
                raise RuntimeError(f"El servidor ha retornat HTTP {response.status}.")
            print(f"Pàgina oberta: {browser.page.title()}")
            print(f"User-Agent efectiu: {browser.page.evaluate('navigator.userAgent')}")
    except (PlaywrightError, RuntimeError) as error:
        print(f"Error del navegador: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Execució interrompuda; recursos del navegador alliberats.", file=sys.stderr)
        return 130

    print("Navegador tancat correctament. La descoberta encara està pendent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
