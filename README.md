# cal

A unified web calendar for all CMU academic events, live at
[cmucal.com](https://cmucal.com). Deployed with
[kennel](https://docs.kennel.scottylabs.org).

- `api/`: Flask API, scrapers, and course agent (the `api` service).
- `web/`: Next.js 16 frontend (the `web` service).
- `docs/`: contributor docs, published on docs.scottylabs.org.

Both services are declared in `devenv.nix` under `scottylabs.kennel.services`
and built by the matching packages in `flake.nix`.

## Getting started

On the CMUCal team, with Nix and devenv: log in to OpenBao once
(`nix run git+https://git.cmu.dev/ScottyLabs/kennel#login`), then `devenv up`
starts the API (http://localhost:8080), the web app (http://localhost:3000)
and the sign-in relay with the dev secrets loaded.

Without Nix, or on Windows, see the manual setup in
[`docs/getting-started.md`](docs/getting-started.md): Node 22, Python 3.10+,
[uv](https://docs.astral.sh/uv/), local env files, and Ricochet for sign-in.

## Deployment

Kennel deploys `main` to production (`cmucal.com`, `api.cmucal.com`), so a
merge ships to users. Other branch pushes are ignored; open a pull request to
get CI. Preview deployments are off because every deployment would share the
one Supabase database.

Each service exposes `GET /api/health`, which kennel polls after starting it.

## Secrets

Declared in `secretspec.toml`, stored in OpenBao, injected at deploy time.
Never committed.

```bash
secretspec set -P prod SUPABASE_DB_URL
secretspec check -P prod
```

`web/.env.production` is the exception: `NEXT_PUBLIC_*` values are inlined at
build time, before kennel resolves secrets, and are public by design.

## Known gaps

- Supabase (free tier) is still the database. `.forgejo/workflows/keepalive.yml`
  keeps it from pausing. Moving to kennel Postgres means rewriting the
  scraper and course agent writers, which use the Supabase REST client.
- Scraped course events do not skip holidays, and lecture vs recitation is
  guessed from the section label.
- Ruff runs a reduced rule set and the `ty` hook is off.
- `nix build .#api` fails on macOS (a darwin nix bug); CI builds on Linux.
