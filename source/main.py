"""Punt d'entrada del projecte i validació de la configuració local."""

from dataclasses import dataclass
from pathlib import Path
import sys

from dotenv import dotenv_values

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
    try:
        configuration = load_configuration()
    except ConfigurationError as error:
        print(f"Error de configuració: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
