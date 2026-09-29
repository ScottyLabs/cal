# scraper/scripts/export_soc.py
"""Scrape the CMU Schedule of Classes into Supabase.

    python -m scraper.scripts.export_soc [--semester Fall_26] [--dry-run]

The semester defaults to SOC_SEMESTER, else the one in session. SOC_DRY_RUN=true
is the same as --dry-run, which parses and builds rows but writes nothing.
"""

import argparse
import logging
import os
import sys
import traceback

import requests

from app.env import get_api_base_url, load_env

ENV = load_env()

from scraper.helpers.semester import infer_semester_label  # noqa: E402
from scraper.monitors.academic import ScheduleOfClassesScraper  # noqa: E402
from scraper.transforms.soc_events import build_events_and_rrules  # noqa: E402
from scraper.transforms.soc_org_course import build_orgs_and_courses  # noqa: E402

logger = logging.getLogger(__name__)

# The API regenerates occurrences for these in one request and one commit.
# Gunicorn kills a request after 120s (app/wsgi.py), so keep batches small
# enough to finish well inside that.
REGENERATE_BATCH = 50
REGENERATE_TIMEOUT = 115


def export_soc_safe():
    try:
        logger.info("🚀 SOC export started")
        export_soc()
        logger.info("[ok] SOC export finished successfully")
    except Exception:
        logger.error("export_soc failed")
        logger.error(traceback.format_exc())


def scrape(semester_label: str):
    scraper = ScheduleOfClassesScraper(None, semester_label=semester_label)
    resources = scraper.scrape_data_only()
    if not resources:
        raise RuntimeError(
            f"Scraped 0 sessions for {semester_label}; refusing to continue"
        )
    print(
        f"[ok] {len(resources)} sessions for {semester_label} "
        f"({scraper.sem_start.date()} to {scraper.sem_end.date()})"
    )
    return resources


def export_soc(semester_label=None, dry_run=False):
    """Scrape the Schedule of Classes and export to Supabase
    - Note that nothing rolls back automatically.
    - The system is designed to heal itself on rerun, and does not rely on rollback
    - Only upserts. Nothing belonging to other semesters is deleted; recurrence
      rules are replaced only for the events this run upserted.
    """
    semester_label = (
        semester_label or os.getenv("SOC_SEMESTER") or infer_semester_label()
    )
    resources = scrape(semester_label)

    if dry_run:
        dry_run_report(resources)
        return

    # Imported here so a dry run needs no Supabase credentials or client.
    from scraper.persistence.supabase_agent_run import insert_agent_run
    from scraper.persistence.supabase_categories import ensure_lecture_category
    from scraper.persistence.supabase_events import insert_events
    from scraper.persistence.supabase_org_course import upsert_courses, upsert_orgs
    from scraper.persistence.supabase_recurrence import replace_recurrence_rules
    from scraper.persistence.supabase_writer import get_supabase

    api_base_url = get_api_base_url()
    db = get_supabase()

    # agent run
    agent_run_id = insert_agent_run(db, agent_version="soc_v1")
    logger.info(f"Created agent run with ID {agent_run_id}")

    # orgs + courses
    orgs, courses = build_orgs_and_courses(resources)
    org_id_by_key = upsert_orgs(db, orgs)
    upsert_courses(db, courses, org_id_by_key)
    print(f"[ok] {len(orgs)} orgs and {len(courses)} courses")

    # categories
    category_id_by_org = ensure_lecture_category(db, org_id_by_key)
    print(f"[ok] {len(category_id_by_org)} categories")

    # events + recurrence rules
    events, rrules = build_events_and_rrules(
        resources, org_id_by_key, category_id_by_org, agent_run_id
    )
    event_id_by_identity = insert_events(db, events)
    replace_recurrence_rules(db, rrules, event_id_by_identity)
    print(f"[ok] {len(events)} events and {len(rrules)} recurrence rules")

    affected_event_ids = sorted(set(event_id_by_identity.values()))
    failed = regenerate_occurrences(api_base_url, affected_event_ids)
    if failed:
        raise RuntimeError(
            f"Occurrence regeneration failed for {len(failed)} of "
            f"{len(affected_event_ids)} events. Events and rules are saved; "
            "rerun to retry (upserts are idempotent)."
        )


def regenerate_occurrences(api_base_url: str, event_ids: list) -> list:
    """Ask the API to build event_occurrences; returns the event IDs that failed.

    Sends SCRAPER_API_TOKEN as a bearer token when set. A 401/403 stops the run
    instead of failing every batch.
    """
    base = api_base_url.rstrip("/")
    if not base.endswith("/api"):
        base += "/api"
    url = f"{base}/events/regenerate_occurrences_by_events"
    print(f"...Regenerating occurrences for {len(event_ids)} events via {url}")

    headers = {"User-Agent": "cmucal-scraper/1.0"}
    token = os.getenv("SCRAPER_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("   note: SCRAPER_API_TOKEN is not set; sending no service token")

    failed = []
    total = (len(event_ids) + REGENERATE_BATCH - 1) // REGENERATE_BATCH
    for n, i in enumerate(range(0, len(event_ids), REGENERATE_BATCH), start=1):
        batch = event_ids[i : i + REGENERATE_BATCH]
        try:
            res = requests.post(
                url,
                json={"event_ids": batch},
                headers=headers,
                timeout=REGENERATE_TIMEOUT,
            )
            if res.status_code in (401, 403):
                raise PermissionError(
                    f"HTTP {res.status_code} from {url}: the API rejected the"
                    " request. Set SCRAPER_API_TOKEN to the API's service token."
                )
            if res.status_code >= 300:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:200]}")
            body = res.json()
            print(
                f"   batch {n}/{total}: regenerated "
                f"{body.get('regenerated_events')}, skipped {body.get('skipped_events')}"
            )
        except (requests.exceptions.RequestException, RuntimeError, ValueError) as e:
            print(f"   batch {n}/{total} FAILED: {e}")
            failed.extend(batch)

    print(
        f"[ok] Regeneration requested for {len(event_ids)} events, {len(failed)} failed"
    )
    return failed


def dry_run_report(resources):
    orgs, courses = build_orgs_and_courses(resources)
    fake_org_ids = {key: n for n, key in enumerate(orgs)}
    fake_category_ids = {
        n: {"LECTURE": n, "RECITATION": n} for n in fake_org_ids.values()
    }
    events, rrules = build_events_and_rrules(
        resources, fake_org_ids, fake_category_ids, agent_run_id=None
    )
    identities = [e["_identity"] for e in events]
    duplicates = len(identities) - len(set(identities))

    print("[dry-run] nothing was written")
    print(f"[dry-run] {len(orgs)} orgs, {len(courses)} courses")
    print(f"[dry-run] {len(events)} events, {len(rrules)} recurrence rules")
    print(f"[dry-run] duplicate event identities: {duplicates}")
    if duplicates:
        raise RuntimeError("Duplicate event identities would break the upsert")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--semester",
        help="Label like Fall_26 or Spring_27. Default: SOC_SEMESTER, else inferred from today",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and parse only; write nothing"
    )
    args = parser.parse_args(argv)
    dry_run = args.dry_run or os.getenv("SOC_DRY_RUN", "").lower() == "true"
    export_soc(args.semester, dry_run=dry_run)


if __name__ == "__main__":
    sys.exit(main())
