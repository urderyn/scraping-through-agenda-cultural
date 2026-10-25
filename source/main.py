"""Entry point: parse arguments, load configuration, and start discovery."""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import dotenv_values

import discovery

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(ValueError):
    """Local configuration is missing or invalid."""


@dataclass(frozen=True)
class Configuration:
    url: str
    dataset_path: Path


def __load_configuration(project_root: Path = PROJECT_ROOT) -> Configuration:
    project_root = project_root.resolve()
    env_path = project_root / ".env"
    if not env_path.is_file():
        raise ConfigurationError(
            "The .env file is missing from the project root. "
            "Copy .env.example to .env and configure URL."
        )

    values = dotenv_values(env_path)
    url = (values.get("URL"))

    if not url:
        raise ConfigurationError('The URL setting is missing or empty.')

    return Configuration(
        url=url,
        dataset_path=project_root / "dataset" / "events.csv",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browse the Agenda and append new URLs to the CSV after each page."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser window."
    )
    arguments = parser.parse_args()

    try:
        configuration = __load_configuration()
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    return discovery.execute(
        configuration.url, configuration.dataset_path, headed=arguments.headed
    )


if __name__ == "__main__":
    raise SystemExit(main())
