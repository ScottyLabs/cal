# Scraper

<!-- 1. `cd scraper`
2. Run:
`python exporters/handshake_export_to_excel.py`
`python exporters/tartanconnect_export_to_excel.py`
`python exporters/si_export_to_excel.py`
`python exporters/peer_tutoring_export_to_excel.py`
`python exporters/schedule_of_classes_export_to_excel.py` -->

## Development Environment

From `api/`, with the secrets loaded (see
[`docs/getting-started.md`](../../docs/getting-started.md)):

1. `uv sync`
1. Dry run first: `uv run python -m scraper.scripts.export_soc --semester Fall_26 --dry-run`
   - `--semester` accepts `Spring_xx`, `Fall_xx`, `Summer1_xx`, `Summer2_xx`; it defaults to the semester in session. Semester dates live in `scraper/helpers/semester.py`.
1. Run without `--dry-run` to write. Needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `API_BASE_URL` (the API that rebuilds the calendar occurrences, e.g. `http://localhost:8080`). Reruns are safe.

TartanConnect club events work the same way: `uv run python -m scraper.scripts.export_tartanconnect --dry-run`, then without `--dry-run`.

- If need to delete, run this:

```
curl -X DELETE http://localhost:8080/api/events/batch_delete_events_by_params \
-H "Content-Type: application/json" \
--data-raw '{"semester":"Spring_26","source_url":"https://enr-apps.as.cmu.edu/open/SOC/SOCServlet/completeSchedule"}'
```

## Production Environment

- `.forgejo/workflows/scrape.yml` (manual dispatch: `soc`, `peer_tutoring`, `supplemental_instruction`, `tartanconnect` or `all`) runs the exports against production with secrets from OpenBao. It replaced the Railway cron job.

# Notes

Updates for the future:

- fix peertutoring cause they switched from the login method to SSO one, breaking the whole scraper...
- improve the Handshake/TC mechanisms to automatically update login cookie information cause it is static at the moment
- might need to abstract "resource_source" out of each scraper file so it's not one to one (i.e. one scraper file like OfficeHoursScraper can query 5 different google calendars, and write to 5 different resource sources. this would
  involve updating the update_database function slightly )
- more office hours
- write a backend in flask that connects with mongo and returns a list of events given filters (will also expand out reoccurring events for whole semester)
