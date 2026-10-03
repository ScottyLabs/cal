import json
import pathlib

from scraper.monitors.career_club import tartanconnect
from scraper.monitors.career_club.tartanconnect import (
    TartanConnectScraper,
    parse_events,
)
from scraper.transforms.tartanconnect_events import build_events, build_orgs

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load_rows():
    # Real mobile_events_list rows from Oct 3 2026, including two date
    # separators and a club posting the same meeting twice.
    return json.loads((FIXTURES / "tartanconnect_events.json").read_text())


def by_id(resources):
    return {r.metadata["event_id"]: r for r in resources}


def test_skips_separators_and_keeps_event_fields():
    resources = by_id(parse_events(load_rows()))

    assert set(resources) == {
        "1935731",
        "1937717",
        "1937748",
        "1936397",
        "1936667",
        "1937573",
        "1937590",
    }
    greek_sing = resources["1937590"]
    assert greek_sing.event_name == "Greek Sing Fall 2026"
    assert greek_sing.event_host == "Greek Sing"
    assert greek_sing.categories == [
        "Entertainment",
        "Will be recorded",
        "Competition",
        "Music",
    ]
    assert greek_sing.metadata["source_url"] == (
        "https://tartanconnect.cmu.edu/rsvp_boot?id=1937590"
    )
    assert greek_sing.events[0].location == "Cohon University Center Wiegand Gymnasium"

    # "Sports slash Recreation" in the markup.
    assert resources["1936667"].categories == ["Sports / Recreation"]
    # Wellness is both the event type and a topic tag; kept once.
    assert resources["1936397"].categories.count("Wellness") == 1


def test_times_are_eastern():
    resources = by_id(parse_events(load_rows()))

    # "5 PM - 8:30 PM" on one day.
    event = resources["1937590"].events[0]
    assert event.start_datetime.isoformat() == "2026-10-24T17:00:00-04:00"
    assert event.end_datetime.isoformat() == "2026-10-24T20:30:00-04:00"

    # Multi-day: the end has its own date.
    event = resources["1935731"].events[0]
    assert event.start_datetime.isoformat() == "2026-09-04T09:00:00-04:00"
    assert event.end_datetime.isoformat() == "2027-03-31T00:00:00-04:00"

    # Listed as 11:55 PM CDT (GMT-5), which is 12:55 AM the next day Eastern.
    event = resources["1937573"].events[0]
    assert event.start_datetime.isoformat() == "2026-10-12T00:55:00-04:00"


def test_locations():
    resources = by_id(parse_events(load_rows()))

    assert resources["1935731"].events[0].location == "See TartanConnect"
    assert resources["1936397"].events[0].location == "Virtual"
    assert resources["1936667"].events[0].location == "Wiegand Gym"


def test_rows_repeated_across_pages_are_parsed_once():
    rows = load_rows()
    assert len(parse_events(rows + rows)) == len(parse_events(rows))


def test_build_events_dedupes_identical_listings():
    resources = parse_events(load_rows())
    orgs = build_orgs(resources)
    org_ids = {name: n for n, name in enumerate(orgs)}
    events = build_events(resources, org_ids, {n: 100 + n for n in org_ids.values()}, 7)

    # 1937717 and 1937748 are the same Origami Club meeting posted twice.
    assert len(events) == len(resources) - 1
    origami = [e for e in events if e["title"] == "Club Meeting"]
    assert [e["source_url"] for e in origami] == [
        "https://tartanconnect.cmu.edu/rsvp_boot?id=1937717"
    ]

    event = next(e for e in events if e["title"] == "Greek Sing Fall 2026")
    assert orgs["Greek Sing"] == {"name": "Greek Sing", "type": "CLUB"}
    assert event["org_id"] == org_ids["Greek Sing"]
    assert event["category_id"] == 100 + org_ids["Greek Sing"]
    assert event["event_type"] == "CLUB"
    assert event["semester"] == "Fall_26"
    assert event["event_timezone"] == "America/New_York"
    assert event["agent_run_id"] == 7
    assert event["description"] == "Entertainment, Will be recorded, Competition, Music"


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_fetch_pages_until_empty(monkeypatch):
    rows = load_rows()
    pages = {
        0: rows[:4],
        tartanconnect.PAGE_SIZE: rows[4:],
        2 * tartanconnect.PAGE_SIZE: [],
    }
    requested = []

    def fake_get(self, url, params=None, **kwargs):
        requested.append(params["range"])
        return _Response(pages[params["range"]])

    monkeypatch.setattr(tartanconnect.requests.Session, "get", fake_get)

    assert TartanConnectScraper(None)._fetch_rows() == rows
    assert requested == [0, tartanconnect.PAGE_SIZE, 2 * tartanconnect.PAGE_SIZE]
