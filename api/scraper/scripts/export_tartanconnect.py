# scraper/scripts/export_tartanconnect.py
"""Import TartanConnect club events into Supabase.

    python -m scraper.scripts.export_tartanconnect [--dry-run]

TARTANCONNECT_DRY_RUN=true is the same as --dry-run, which fetches and builds
rows but writes nothing.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from app.env import get_api_base_url, load_env

ENV = load_env()

from scraper.monitors.career_club.tartanconnect import (  # noqa: E402
    BASE_URL,
    TartanConnectScraper,
)
from scraper.transforms.tartanconnect_events import (  # noqa: E402
    build_events,
    build_orgs,
)

CATEGORY_NAME = "TartanConnect"


def scrape():
    resources = TartanConnectScraper(None).scrape_data_only()
    if not resources:
        raise RuntimeError("Scraped 0 TartanConnect events; refusing to continue")
    print(f"[ok] {len(resources)} TartanConnect events")
    return resources


def export_tartanconnect(dry_run=False):
    """Scrape TartanConnect and export to Supabase
    - Nothing rolls back automatically; a rerun heals a failed run.
    - Upserts one CLUB org per host club, a TartanConnect category in each, and
      one event per listing.
    - Then deletes this source's future events that the feed no longer lists.
      Past events and other sources' events are never touched.
    """
    resources = scrape()

    if dry_run:
        dry_run_report(resources)
        return

    # Imported here so a dry run needs no Supabase credentials or client.
    from scraper.persistence.api_occurrences import regenerate_occurrences
    from scraper.persistence.supabase_agent_run import insert_agent_run
    from scraper.persistence.supabase_categories import ensure_category
    from scraper.persistence.supabase_events import (
        delete_unlisted_future_events,
        insert_events,
    )
    from scraper.persistence.supabase_org_course import upsert_orgs
    from scraper.persistence.supabase_writer import get_supabase

    api_base_url = get_api_base_url()
    db = get_supabase()

    agent_run_id = insert_agent_run(db, agent_version="tartanconnect_v1")
    print(f"[ok] agent run {agent_run_id}")

    orgs = build_orgs(resources)
    org_id_by_key = upsert_orgs(db, orgs)
    category_id_by_org = ensure_category(db, org_id_by_key.values(), CATEGORY_NAME)
    print(f"[ok] {len(orgs)} orgs and {len(category_id_by_org)} categories")

    events = build_events(resources, org_id_by_key, category_id_by_org, agent_run_id)
    event_id_by_identity = insert_events(db, events)
    print(f"[ok] {len(events)} events")

    deleted = delete_unlisted_future_events(db, f"{BASE_URL}/", agent_run_id)
    print(f"[ok] deleted {len(deleted)} future events no longer listed")

    event_ids = sorted(set(event_id_by_identity.values()))
    failed = regenerate_occurrences(api_base_url, event_ids)
    if failed:
        raise RuntimeError(
            f"Occurrence regeneration failed for {len(failed)} of "
            f"{len(event_ids)} events. Events are saved; rerun to retry."
        )


def dry_run_report(resources):
    orgs = build_orgs(resources)
    fake_org_ids = {key: n for n, key in enumerate(orgs)}
    events = build_events(
        resources, fake_org_ids, {n: n for n in fake_org_ids.values()}, None
    )
    now = datetime.now(timezone.utc)
    upcoming = sum(e["start_datetime"] > now for e in events)

    print("[dry-run] nothing was written")
    print(f"[dry-run] {len(orgs)} orgs")
    print(
        f"[dry-run] {len(events)} events ({upcoming} upcoming), "
        f"{len(resources) - len(events)} duplicate listings dropped"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and parse only; write nothing"
    )
    args = parser.parse_args(argv)
    dry_run = args.dry_run or os.getenv("TARTANCONNECT_DRY_RUN", "").lower() == "true"
    export_tartanconnect(dry_run=dry_run)


if __name__ == "__main__":
    sys.exit(main())
