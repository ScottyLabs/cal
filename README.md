# cal

A unified web calendar for all CMU academic events, live at
[cmucal.com](https://cmucal.com). Deployed with
[kennel](https://docs.kennel.scottylabs.org).

- `api/`: Flask API, scrapers, and course agent (the `api` service).
- `web/`: Next.js 16 frontend (the `web` service).
- `docs/`: contributor docs.

Both services are declared and built in `flake.nix`.

## Getting started

Install Lix and log in to OpenBao by following kennel's [local development](https://docs.kennel.scottylabs.org/guides/local-development/#installing-nix) and [secrets](https://docs.kennel.scottylabs.org/guides/secrets/#local-development) guides, then enter the dev shell and start the API, the frontend, and the sign-in relay. The full walkthrough is in [`docs/getting-started.md`](docs/getting-started.md).

```bash
nix develop
pitchfork start --local   # API on :8080, frontend on :3000
```

## Deployment

Kennel deploys `main` to production (`cmucal.com`, `api.cmucal.com`), so a
merge ships to users. Preview deployments are off because every deployment
would share the one Supabase database.

## Secrets

Declared in `secretspec.toml` and stored in OpenBao. Kennel's [secrets guide](https://docs.kennel.scottylabs.org/guides/secrets/#managing-secrets) covers setting and checking them.

`web/.env.production` is the exception: `NEXT_PUBLIC_*` values are inlined at
build time, before kennel resolves secrets, and are public by design.

## Known gaps

- Supabase (free tier) is still the database. `.forgejo/workflows/keepalive.yml`
  keeps it from pausing. Moving to kennel Postgres means rewriting the
  scraper and course agent writers, which use the Supabase REST client.
- Scraped course events do not skip holidays, and lecture vs recitation is
  guessed from the section label.
- Ruff runs a reduced rule set.
- `nix build .#api` fails on macOS (a darwin nix bug); CI builds on Linux.
