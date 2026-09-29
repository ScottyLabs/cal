from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.enums import FrequencyType
from app.models.event_occurrence import (
    populate_event_occurrences,
    regenerate_event_occurrences_by_event_ids,
)
from app.models.models import (
    EventOccurrence,
    EventOverride,
    RecurrenceExdate,
    RecurrenceRdate,
)

NY = ZoneInfo("America/New_York")


def _snapshot(db, event_ids):
    # event_saved_at is left out: it records the event's last_updated_at, which
    # every regeneration bumps, so it differs between any two runs.
    return sorted(
        (
            o.event_id,
            o.start_datetime,
            o.end_datetime,
            o.title,
            o.description,
            o.location,
            o.org_id,
            o.category_id,
            o.is_all_day,
            o.source_url,
            str(o.recurrence),
        )
        for o in db.query(EventOccurrence)
        .filter(EventOccurrence.event_id.in_(event_ids))
        .all()
    )


def _make_events(db, event_factory, recurrence_rule_factory):
    """Three weekly events across the Nov 1 DST change: plain, EXDATE, RDATE+override."""
    start = datetime(2026, 9, 28, 9, 30, tzinfo=NY)
    events = []
    for i in range(3):
        s = start + timedelta(days=i)
        event = event_factory(
            start_datetime=s.astimezone(timezone.utc),
            end_datetime=(s + timedelta(minutes=80)).astimezone(timezone.utc),
            event_timezone="America/New_York",
            location=f"Room {i}",
            semester="Fall_26",
            title=f"Batch Test {i}",
        )
        rule = recurrence_rule_factory(
            event_id=event.id,
            frequency=FrequencyType.WEEKLY,
            interval=1,
            start_datetime=event.start_datetime,
            count=10,
        )
        events.append((event, rule, s))

    _, rule, s = events[1]
    db.add(RecurrenceExdate(rrule_id=rule.id, exdate=s + timedelta(weeks=2)))

    _, rule, s = events[2]
    db.add(RecurrenceRdate(rrule_id=rule.id, rdate=s + timedelta(days=3)))
    db.add(
        EventOverride(
            rrule_id=rule.id,
            recurrence_date=s + timedelta(weeks=4),
            new_start=s + timedelta(weeks=4, hours=2),
            new_end=s + timedelta(weeks=4, hours=3),
            new_title="Moved",
            new_location="Elsewhere",
        )
    )
    db.flush()
    return events


def test_batch_regeneration_matches_per_event(
    db, event_factory, recurrence_rule_factory
):
    events = _make_events(db, event_factory, recurrence_rule_factory)
    ids = [event.id for event, _, _ in events]

    for event, rule, _ in events:
        populate_event_occurrences(db, event, rule)
    db.flush()
    per_event = _snapshot(db, ids)

    # Sanity: the EXDATE, RDATE and override paths actually ran.
    counts = {i: sum(1 for row in per_event if row[0] == i) for i in ids}
    assert counts[ids[0]] == 10
    assert counts[ids[1]] == 9
    assert counts[ids[2]] == 11
    assert any(row[3] == "Moved" and row[5] == "Elsewhere" for row in per_event)

    # The batch path skips rules generated after the event's last update, so
    # clear that marker to make it rebuild everything.
    for _, rule, _ in events:
        rule.last_generated_at = None
    db.flush()

    missing_id = max(ids) + 1000
    regenerated, skipped = regenerate_event_occurrences_by_event_ids(
        db, ids + [missing_id]
    )
    db.flush()

    assert (regenerated, skipped) == (3, 1)
    assert _snapshot(db, ids) == per_event


def test_batch_regeneration_skips_fresh_rules(
    db, event_factory, recurrence_rule_factory
):
    events = _make_events(db, event_factory, recurrence_rule_factory)
    ids = [event.id for event, _, _ in events]

    for _, rule, _ in events:
        rule.last_generated_at = None
    db.flush()
    assert regenerate_event_occurrences_by_event_ids(db, ids) == (3, 0)
    db.flush()
    first = _snapshot(db, ids)

    # Nothing changed since the last build, so a second call does no work.
    # Same timestamp rule as populate_event_occurrences' callers relied on.
    for event, rule, _ in events:
        rule.last_generated_at = event.last_updated_at + timedelta(seconds=1)
    db.flush()
    assert regenerate_event_occurrences_by_event_ids(db, ids) == (0, 0)
    assert _snapshot(db, ids) == first
