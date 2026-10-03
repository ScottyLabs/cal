import os

import requests

# The API regenerates occurrences for these in one request and one commit.
# Gunicorn kills a request after 120s (app/wsgi.py), so keep batches small
# enough to finish well inside that.
REGENERATE_BATCH = 50
REGENERATE_TIMEOUT = 115


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
