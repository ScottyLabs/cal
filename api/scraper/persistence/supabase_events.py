from datetime import datetime, timezone

from scraper.helpers.event import clean_row_for_insert
from scraper.persistence.supabase_writer import chunked


def insert_events(db, events):
    """
    Returns:
        {event_identity: event_id}
    """

    identity_by_row = []
    rows = []

    for e in events:
        identity_by_row.append(e["_identity"])
        rows.append(
            clean_row_for_insert({k: v for k, v in e.items() if k != "_identity"})
        )

    event_id_by_identity = {}

    for batch, id_batch in zip(chunked(rows, 200), chunked(identity_by_row, 200)):
        res = (
            db.table("events")
            .upsert(
                batch,
                on_conflict="org_id,title,semester,start_datetime,end_datetime,location",
                returning="representation",
            )
            .execute()
        )

        for row, identity in zip(res.data, id_batch):
            event_id_by_identity[identity] = row["id"]

    # print(f"Inserted/updated {len(event_id_by_identity)} events")
    return event_id_by_identity


def delete_unlisted_future_events(db, source_url_prefix: str, agent_run_id: int):
    """Delete future events from a source that this run did not upsert.

    Each run upserts its events with its own agent_run_id, so an event of the
    source still carrying an older run ID was not in this run's feed:
    cancelled, removed, or changed (a new title, time or place upserts a new
    row). Past events are kept. Rows not written by a scraper have a NULL
    agent_run_id, which the neq filter never matches. Occurrences, tags and
    saves cascade, so a short but successful feed must not wipe the source:
    if more than a fifth of its future events would go, nothing is deleted.
    Returns the deleted rows.
    """
    now = datetime.now(timezone.utc).isoformat()
    future = (
        db.table("events")
        .select("id, agent_run_id")
        .like("source_url", f"{source_url_prefix}%")
        .gt("start_datetime", now)
        .execute()
        .data
    )
    stale = [
        row["id"]
        for row in future
        if row["agent_run_id"] is not None and row["agent_run_id"] != agent_run_id
    ]
    if len(stale) > max(25, len(future) // 5):
        print(
            f"   warning: {len(stale)} of {len(future)} future events are missing "
            "from this feed; skipping deletion in case the feed was incomplete"
        )
        return []
    deleted = []
    for batch in chunked(stale, 200):
        deleted += db.table("events").delete().in_("id", batch).execute().data
    return deleted
