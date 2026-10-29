from bs4 import BeautifulSoup, Tag
import requests
import re
import time

from pathlib import Path
from event_csv_repository import EventCsvRepository

REQUEST_TIMEOUT = 20
MIN_DELAY = 1

def execute(url: str, dataset_path: Path) -> int:
    """ Read CSV to get the URLs and visits each URL to get the data from each activity """

    print("Retrieving the content for each activity")

    repository = EventCsvRepository(dataset_path, url)
    _, existing_rows = repository.read()

    with requests.Session() as session:
        # Loop over each url to get its content
        for row in existing_rows:
            url = row["url"]
            if repository.event_exists(url):
                continue

            start_time = time.monotonic()

            try:
                response = session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

            except requests.RequestException as error:
                print(f"Error obtaining {url}: {error}")
                continue

            finally:
                # Adapt the delay to the time the request took.
                elapsed = time.monotonic() - start_time
                time.sleep(max(MIN_DELAY, elapsed))

            try:
                soup = BeautifulSoup(response.content, features="html.parser")

                # Obtain all the content of the activity
                article = soup.find(id="articleRoot")

                if not isinstance(article, Tag):
                    print(f"Article not found: {url}")
                    continue

                # Extraction of all the data from the article
                data = __extract_event_data(url, article)

            except Exception as error:
                print(f"Error while retrieving the information for {url}: {error}")

            # Update CSV with the data
            try:
                if not repository.update_event(url, data):
                    print(f"URL not found in CSV: {url}")

            except Exception as error:
                print(f"Error while updating CSV for {url}: {error}")
    return 1


def __extract_event_data(url: str, article: Tag) -> dict[str, str]:
    """ Extraction of all the data of an activity"""

    # Title of the activity
    title = article.h2.p.get_text()

    ambits, categories = __find_tags(article)

    description = __extract_description(article)

    inici, final = __extract_dates(article)

    location_data = __extract_location(article)

    return {
        "titol": title,
        "descripcio": description,
        "ambit": ", ".join(ambits),
        "categories": ", ".join(categories),
        "inici": inici,
        "final": final,
        **location_data
    }

def __extract_description(soup: BeautifulSoup) -> str | None:
    """ Extract the description in plane text"""

    element = soup.find("div", id="read-more-descripcio")

    if element is None:
        return None

    description = element.get_text(" ", strip=True)

    description = re.sub(r"\s+", " ", description)

    description = re.sub(
        r"Darrera actualització:.*",
        "",
        description,
    ).strip()

    return description or None

def __extract_dates(article: Tag) -> tuple[str,str]:
    """ Extract dates from the page. Most of the pages contain the dates of the beginning and the end on a menu. But if not found
    there, the script tries to find a second location where may contain this information.
    """
    try:
        dates = article.find(id="menu1-content").find_all('b')
        date_values = [
            " ".join(element.get_text().split())
            for element in dates
            if element.get_text().strip()
        ]

        inici = date_values[0] if len(date_values) >= 1 else ""
        final = date_values[1] if len(date_values) >= 2 else ""
    except Exception as error:
        try:
            dates = article.find(class_="article-panel-section-line").find_all('b')
            date_values = [
                " ".join(element.get_text().split())
                for element in dates
                if element.get_text().strip()
            ]

            inici = date_values[0] if len(date_values) >= 1 else ""
            final = date_values[1] if len(date_values) >= 2 else ""

        except Exception as error:
            inici, final = "", ""

    return inici, final

def __extract_location(article: Tag) -> dict[str, str]:
    """ Extract place, address, city and postal code"""

    espai = article.select_one("#menu2 .espai-item")

    if espai is None:
        return {
            "lloc": "",
            "adreca": "",
            "codi_postal": "",
            "ciutat": "",
        }

    place = espai.select_one(".espai-nom")
    adress_element = espai.select_one(".espai-adress p")

    complete_adress = (
        adress_element.get_text(" ", strip=True)
        if adress_element
        else ""
    )
    parts = [part.strip() for part in complete_adress.split(",")]

    adress = ""
    postal_code = ""
    city = ""

    if len(parts) == 1:
        city = parts[0]

    elif len(parts) == 3:
        middle = parts[1]
        if middle.isdigit() and len(middle) == 5:
            adress = parts[0]
            postal_code = middle
        else:
            adress = ", ".join(parts[:-1])

        city = parts[-1]

    elif len(parts) == 4:
        adress = ", ".join(parts[:-2])
        postal_code = parts[-2]
        city = parts[-1]


    return {
        "lloc": place.get_text(" ", strip=True) if place else "",
        "adreca": adress,
        "codi_postal": postal_code,
        "ciutat": city,
    }

def __find_tags(article: BeautifulSoup) -> tuple[list[str], list[str]]:
    """ Extract ambits and categories of an article """

    tags_section = article.find(
        "div",
        class_="article-panel-section-tags",
    )

    if tags_section is None:
        return [], []

    def extract_text(class_name: str) -> list[str]:
        return [
            text
            for element in tags_section.find_all("span", class_=class_name)
            if (text := element.get_text(" ", strip=True))
        ]

    ambits = extract_text("ambit")
    categories = extract_text("categoria")

    return ambits, categories

