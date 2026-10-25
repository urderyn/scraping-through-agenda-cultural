import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


EVENT_PATH = re.compile(r"^/ca/activitat\.html/\d+/[^/]+/?$")


def normalize_event_url(href: str, base_url: str) -> str | None:
    """Accept event URLs on the same host and port, without navigation or tracking parameters."""
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

    # On event pages remove uneeded parameters
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != "page" and not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
    )
