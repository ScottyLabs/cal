from app.utils.date import infer_semester_from_datetime
from scraper.helpers.event import event_identity
from scraper.helpers.timezone import DEFAULT_TZ


def build_orgs(resources):
    """One CLUB org per host club, keyed by club name."""
    return {r.event_host: {"name": r.event_host, "type": "CLUB"} for r in resources}


def build_events(resources, org_id_by_key, category_id_by_org, agent_run_id):
    """One-time CLUB events, one per distinct event identity.

    Clubs sometimes post the same event twice (same title, time and place
    under two event IDs). Those share an identity, which the upsert cannot
    take twice, so keep the lowest event ID.
    """
    events = {}
    for r in sorted(resources, key=lambda r: int(r.metadata["event_id"])):
        e = r.events[0]
        org_id = org_id_by_key[r.event_host]
        # The API's convention for non-SOC events, e.g. Fall_26.
        semester = infer_semester_from_datetime(e.start_datetime)
        identity = event_identity(
            org_id, r.event_name, semester, e.start_datetime, e.end_datetime, e.location
        )
        if identity in events:
            continue

        events[identity] = {
            "org_id": org_id,
            "title": r.event_name,
            "semester": semester,
            "start_datetime": e.start_datetime,
            "end_datetime": e.end_datetime,
            "location": e.location,
            "is_all_day": False,
            "event_timezone": str(DEFAULT_TZ),
            "category_id": category_id_by_org[org_id],
            "agent_run_id": agent_run_id,
            "description": ", ".join(r.categories) or None,
            "event_type": "CLUB",
            "source_url": r.metadata["source_url"],
            "_identity": identity,  # runtime-only
        }

    return list(events.values())
