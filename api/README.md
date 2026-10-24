# CMUCal API

The Flask API (`app/`), the scrapers (`scraper/`) and the course agent
(`course_agent/`). To run it, follow
[`docs/getting-started.md`](../docs/getting-started.md); the commands below
assume the dev secrets are loaded (an `.env.development` file,
`secretspec run -P dev --`, or `devenv shell`).

## Run

```bash
uv sync
uv run python run.py
```

The API listens on http://localhost:8080.

## Dependencies

Dependencies live in `pyproject.toml`: runtime ones under
`[project.dependencies]`, test-only ones under
`[project.optional-dependencies].dev`. Add one with `uv add <package>` (or
`uv add --optional dev <package>`) so `uv.lock` stays in sync.

## Tests

```bash
uv sync --extra dev
uv run pytest
```

Tests that need a database read `SUPABASE_DB_URL`. Point it at a local
Postgres you can throw away, migrated with `uv run alembic upgrade head`, not
the shared dev database.

## Migrations

Alembic migrates whatever database `SUPABASE_DB_URL` points at. `APP_ENV`
(default `development`) only picks which `.env.<APP_ENV>` file it loads.

```bash
uv run alembic revision --autogenerate -m "<message>"
uv run alembic upgrade head
```

- `upgrade head` runs the pending migrations and bumps the version.
- `stamp head` bumps the version without running anything.
- `downgrade -1` undoes the latest migration.

Everyone shares one dev database, so ask the tech lead before a downgrade.
Production migrations are run by the tech lead, never from a local checkout.

## Regenerating models from Supabase

Only when told to: `uv run sqlacodegen "$SUPABASE_DB_URL" --outfile models.py`,
then in `models.py`:

- comment out the `class Base` section;
- add `from app.services.db import Base` at the top;
- make the capitalized class names singular (`class Events` becomes
  `class Event`), leaving the lowercase names in quotes alone.

## Course and club data

See [`scraper/README.md`](scraper/README.md): the Schedule of Classes and
TartanConnect exports, and the Scrape workflow that runs them against
production.
