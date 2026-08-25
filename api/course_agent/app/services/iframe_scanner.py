# course_agent/app/services/iframe_scanner.py
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup


def derive_ical_link(iframe_url: str) -> str | None:
    parsed = urlparse(iframe_url)
    params = parse_qs(parsed.query)

    src = params.get("src")
    if not src:
        return None

    calendar_id = src[0]

    return f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"


def find_google_calendar_iframe(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if "calendar.google.com" in src:
            return src

    return None
