import csv
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from event_urls import normalize_event_url


class DatasetError(RuntimeError):
    """The CSV cannot be processed safely while preserving existing data."""


class EventCsvRepository:
    """Manage the CSV while preserving existing rows and columns."""

    def __init__(self, csv_path: Path, base_url: str) -> None:
        self.__csv_path = csv_path
        self.__base_url = base_url

    def read(self) -> tuple[list[str], list[dict[str, str]]]:
        """Read the CSV and validate its structure without checking for duplicates."""
        try:
            with self.__csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, strict=True)
                fields = reader.fieldnames
                if (
                    not fields
                    or "url" not in fields
                    or len(fields) != len(set(fields))
                    or any(not field.strip() for field in fields)
                ):
                    raise DatasetError(
                        "The CSV must have a header containing the url column, "
                        "with no empty or repeated column names. The file was not modified."
                    )

                rows = []
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise DatasetError(
                            f"CSV row {reader.line_num} does not have the number "
                            "of fields specified by the header. The file was not modified."
                        )
                    rows.append(row)
                return fields, rows
        except FileNotFoundError:
            return ["url"], []
        except (OSError, UnicodeError, csv.Error) as error:
            raise DatasetError(f"Could not read the CSV: {error}") from error

    def save_urls(self, urls: list[str]) -> int:
        """Add new URLs and return the added number"""
        fields, rows = self.read()
        known_urls = set()
        for row_number, row in enumerate(rows, start=2):
            normalized = normalize_event_url(row["url"], self.__base_url)
            if normalized is None:
                raise DatasetError(
                    f"CSV record {row_number} has an empty URL "
                    "or one that is invalid for the configured Agenda. The file was not modified."
                )
            known_urls.add(normalized)
        new_rows = []
        for url in urls:
            normalized = normalize_event_url(url, self.__base_url)
            if normalized is None:
                raise DatasetError("Received an invalid URL. The CSV was not modified.")
            if normalized not in known_urls:
                # Preserve enrichment columns and leave them empty in new rows.
                row = dict.fromkeys(fields, "")
                row["url"] = normalized
                new_rows.append(row)
                known_urls.add(normalized)

        # A run with no new URLs does not rewrite or change the existing file.
        if not new_rows and self.__csv_path.exists():
            return 0

        self.__write(fields, rows + new_rows)

        return len(new_rows)

    def event_exists(self, url: str) -> bool:
        normalized_url = normalize_event_url(url, self.__base_url)
        if normalized_url is None:
            return False

        _, rows = self.read()

        for row in rows:
            existing_url = normalize_event_url(
                row.get("url", ""),
                self.__base_url,
            )

            if existing_url == normalized_url:
                return bool(row.get("titol", "").strip())

        return False

    def update_event(self, url: str, data: dict[str, str]) -> bool:
        normalized_url = normalize_event_url(url, self.__base_url)

        if normalized_url is None:
            raise DatasetError("Received an invalid URL.")

        # Validate the data before updating CSV.
        if not isinstance(data, dict):
            raise DatasetError("Event data must be a dictionary.")

        for key, value in data.items():
            if not isinstance(key, str):
                raise DatasetError("Invalid column name.")

            if not isinstance(value, str):
                raise DatasetError(
                    f"Value for column {key!r} must be a string."
                )

        fields, rows = self.read()
        if "url" not in fields:
            raise DatasetError("The CSV does not contain the URL column.")

        # Search row that contains this URL
        matching_row = None

        for row in rows:
            existing_url = normalize_event_url(
                row.get("url", ""),
                self.__base_url,
            )

            if existing_url == normalized_url:
                matching_row = row
                break

        if matching_row is None:
            return False

        # Add columns if they still do not exist.
        for key in data:
            if key not in fields:
                fields.append(key)

        # Update only correct values
        for key, value in data.items():
            if value.strip():
                matching_row[key] = value

        # Update CSV
        self.__write(fields, rows)

        return True

    def __write(self, fields: list[str], rows: list[dict[str, str]]) -> None:
        """Replace the CSV only after the temporary file is complete."""
        try:
            self.__csv_path.parent.mkdir(parents=True, exist_ok=True)
            # Keep the temporary file on the same filesystem for atomic replacement.
            with TemporaryDirectory(
                prefix=f".{self.__csv_path.name}-", dir=self.__csv_path.parent
            ) as directory:
                temporary_path = Path(directory) / self.__csv_path.name
                with temporary_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                    writer.writeheader()
                    writer.writerows(rows)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self.__csv_path)
        except (OSError, UnicodeError, csv.Error) as error:
            raise DatasetError(f"Could not save the CSV: {error}") from error
