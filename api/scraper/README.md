# Updated README
<!-- 1. `cd scraper`
2. Run:
`python exporters/handshake_export_to_excel.py`
`python exporters/tartanconnect_export_to_excel.py`
`python exporters/si_export_to_excel.py`
`python exporters/peer_tutoring_export_to_excel.py`
`python exporters/schedule_of_classes_export_to_excel.py` -->
## Development Environment
1. Activate the virtual environment at the root directory (`cd api && uv sync`).
2. Dry run first: `python -m scraper.scripts.export_soc --semester Fall_26 --dry-run`
    - `--semester` accepts `Spring_xx`, `Fall_xx`, `Summer1_xx`, `Summer2_xx`; it defaults to the semester in session. Semester dates live in `scraper/helpers/semester.py`.
3. Run without `--dry-run` to write. Needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `API_BASE_URL` (e.g. `https://api.cmucal.com`). Reruns are safe.

* If need to delete, run this:
```
curl -X DELETE http://localhost:5001/api/events/batch_delete_events_by_params \
-H "Content-Type: application/json" \
--data-raw '{"semester":"Spring_26","source_url":"https://enr-apps.as.cmu.edu/open/SOC/SOCServlet/completeSchedule"}'
```

## Production Environment
- `.forgejo/workflows/scrape.yml` (manual dispatch) runs `python -m scraper.scripts.export_soc` with secrets from OpenBao. It replaced the Railway cron job.

# Old README

To use, first create a virtual environment: `python3 -m venv <myenvname>`

Then activate it:

On windows: `.\env\Scripts\activate.bat`
On mac: `source venv/bin/activate`

Then install needed packages: `pip3 install -r requirements.txt`

Then create a file `config.ini` that contains the link to the MONGO database in the format seen in `config.ini.example`.

Then launch the scraper: `python3 main.py`

--------

Updates for the future:
- fix peertutoring cause they switched from the login method to SSO one, breaking the whole scraper...
- improve the Handshake/TC mechanisms to automatically update login cookie information cause it is static at the moment
- might need to abstract "resource_source" out of each scraper file so it's not one to one (i.e. one scraper file like OfficeHoursScraper can query 5 different google calendars, and write to 5 different resource sources. this would
involve updating the update_database function slightly )
- more office hours
- write a backend in flask that connects with mongo and returns a list of events given filters (will also expand out reoccurring events for whole semester)