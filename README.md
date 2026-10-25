# Agenda Cultural Scraper

Academic project for the **Data Typology and Lifecycle** course at **UOC**. It collects event URLs from the Agenda Cultural de Catalunya and saves them to `dataset/events.csv` without adding duplicates.

`main.py` loads the configuration and calls `discovery.execute()`, which uses Playwright to browse all result pages and saves new URLs through `EventCsvRepository`.

## Setup

Requires Python 3.10 or later. From the project root, for the first setup:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

The `URL` setting in `.env` specifies the Agenda home page.

## Run

With the virtual environment activated:

```sh
python source/main.py
```

Arguments:

- `--headed`: show the browser window; runs headless by default.
- `-h`, `--help`: show usage information.

Example with a visible browser:

```sh
python source/main.py --headed
```
