import datetime
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scraper.helpers.timezone import DEFAULT_TZ
from scraper.models import OtherResource, ResourceEvent
from scraper.monitors.base_scraper import BaseScraper

BASE_URL = "https://tartanconnect.cmu.edu"
EVENTS_URL = f"{BASE_URL}/mobile_ws/v17/mobile_events_list"
PAGE_SIZE = 100
# "Private Location (sign in to display)" / "(register to display)": the
# address is only on TartanConnect.
PRIVATE_LOCATION = "See TartanConnect"

# "Sun, Oct 11, 2026 5 PM" or "7:30 PM"; the end time may omit the date.
_DATE_TIME = re.compile(
    r"(\w{3}, \w{3} \d{1,2}, \d{4})?\s*(\d{1,2})(?::(\d{2}))? ([AP]M)"
)
_TAG = re.compile(r'aria-description="List all events filtered by ([^"]*)"')
_GMT_OFFSET = re.compile(r"GMT([+-]\d{1,2})")


class TartanConnectScraper(BaseScraper):
    def __init__(self, db):
        super().__init__(db, "TartanConnect", "TartanConnect Website")

    def scrape(self):
        unique_keys = ["resource_type", "resource_source", "event_name", "event_host"]
        self.update_database(self.scrape_data_only(), "career_club_events", unique_keys)

    def scrape_data_only(self):
        return parse_events(self._fetch_rows())

    def _fetch_rows(self):
        """Page through the public event list (no login) until it runs out."""
        session = requests.Session()
        # The endpoint returns the odd 502/503 under load.
        retry = Retry(total=3, backoff_factor=2, status_forcelist=(502, 503, 504))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        headers = {
            **self.headers,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"{BASE_URL}/events",
        }

        rows = []
        start = 0
        while True:
            res = session.get(
                EVENTS_URL,
                params={"range": start, "limit": PAGE_SIZE},
                headers=headers,
                timeout=60,
            )
            res.raise_for_status()
            page = res.json()
            if not page:
                return rows
            rows.extend(page)
            start += PAGE_SIZE


def parse_events(rows):
    """Turn mobile_events_list rows into one OtherResource per event."""
    resources = []
    seen = set()
    for row in rows:
        if row.get("listingSeparator") == "true":  # date headings
            continue
        # The values are p0, p1, ... in the order "fields" names them.
        event = {
            name: row.get(f"p{i}")
            for i, name in enumerate(row["fields"].split(","))
            if name
        }
        # An event added while paging shifts the pages, repeating a row.
        if event["eventId"] in seen:
            continue
        seen.add(event["eventId"])

        start, end = parse_dates(event["eventDates"], event["eventTimezone"])
        resources.append(
            OtherResource(
                resource_type="Club",
                resource_source="TartanConnect Website",
                event_name=event["eventName"].strip(),
                event_host=event["clubName"].strip(),
                events=[
                    ResourceEvent(
                        start_datetime=start,
                        end_datetime=end,
                        location=parse_location(event["eventLocation"]),
                    )
                ],
                # The event type comes first and may repeat as a topic tag.
                categories=list(
                    dict.fromkeys(
                        tag.replace(" slash ", " / ")
                        for tag in _TAG.findall(event["eventTags"] or "")
                    )
                ),
                metadata={
                    "event_id": event["eventId"],
                    "source_url": BASE_URL + event["eventUrl"],
                },
            )
        )
    return resources


def parse_dates(dates_html: str, timezone_label: str):
    """Parse eventDates into aware datetimes in America/New_York.

    Same day: "<p>Sun, Oct 11, 2026</p><p>5 PM &ndash; 7:30 PM</p>"
    Multi-day: "<p>Fri, Sep 4, 2026 9:00 AM &ndash; </p><p>Wed, Mar 31, 2027 12:00 AM</p>"
    Times are local to timezone_label, e.g. "EDT (GMT-4)" or "PDT (GMT-7)".
    """
    text = " ".join(re.sub(r"<[^>]+>", " ", dates_html).split())
    matches = _DATE_TIME.findall(text)
    if len(matches) != 2:
        raise ValueError(f"Unexpected TartanConnect eventDates: {dates_html!r}")
    (start_date, *start_time), (end_date, *end_time) = matches

    tz = DEFAULT_TZ
    offset = _GMT_OFFSET.search(timezone_label or "")
    if offset and not timezone_label.startswith(("EST", "EDT")):
        tz = datetime.timezone(datetime.timedelta(hours=int(offset.group(1))))

    def to_datetime(date, hour, minute, meridiem):
        local = datetime.datetime.strptime(
            f"{date} {hour}:{minute or '00'} {meridiem}", "%a, %b %d, %Y %I:%M %p"
        )
        return local.replace(tzinfo=tz).astimezone(DEFAULT_TZ)

    return (
        to_datetime(start_date, *start_time),
        to_datetime(end_date or start_date, *end_time),
    )


def parse_location(location: str) -> str:
    location = location.split("<div")[0].strip()
    if location.startswith("Private Location"):
        return PRIVATE_LOCATION
    if location == "-":
        return "N/A"
    if location == "Online Event":
        return "Virtual"
    return location
