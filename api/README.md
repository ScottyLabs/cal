# Backend

The dev shell installs this directory's Python dependencies, and `pitchfork start --local` from the repository root starts the API on :8080. The root [README](../README.md) covers setup.

Add runtime dependencies to `[project.dependencies]` in `pyproject.toml`, and test-only ones to `[project.optional-dependencies].dev`.

## Tests

Run `pytest` in this directory. The tests use the cmucal-test project on Supabase.

## Supabase

(ignore this unless told otherwise) IF need to get the table schema from Supabase: in the terminal, run `sqlacodegen [SUPABASE_DB_URL from env file] --outfile models.py`

- comment out the `class Base` section in `models.py`
- add `from app.services.db import Base` to the top of `models.py`
- change all capitalized class names from plural to singular. i.e. class Events --> class Event. Don't change the lowercase names in quotes.

## Database Migrations

Create a migration with:

```
APP_ENV=development alembic revision --autogenerate -m "<insert your message>"
```

Apply it with `migrate` and undo the latest one with `migrate-down`, both from the dev shell.

## Course data

- See the scraper README's instructions on `export_soc`. `.forgejo/workflows/scrape.yml` runs it in production.

## Scraped Info

(ignore this unless told otherwise) IF need to scrape data from handshake, tartanconnect, si, peer tutoring

1. `cd scraper`
1. Run these commands:
   - `python exporters/handshake_export_to_excel.py`
   - `python exporters/tartanconnect_export_to_excel.py`
   - `python exporters/si_export_to_excel.py`
   - `python exporters/peer_tutoring_export_to_excel.py`
1. Then you can see an excel sheet exported to the base folder
