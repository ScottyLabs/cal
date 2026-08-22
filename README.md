# cal

A unified web calendar for all CMU academic events. Deployed with
[kennel](https://docs.kennel.scottylabs.org).

This repository replaces the two GitHub repositories the project used to live
in — `ScottyLabs/cmucal` (frontend) and `ScottyLabs/cmucal-backend` — which were
deployed on Vercel and Railway respectively.

## Layout

| Path  | What it is                                                  |
| ----- | ----------------------------------------------------------- |
| `api/` | Flask API, scraper, and course agent. Deployed as the `api` service. |
| `web/` | Next.js 16 frontend. Deployed as the `web` service.          |

Both are declared in `devenv.nix` under `scottylabs.kennel.services` and built
by the corresponding packages in `flake.nix`. The names must match.

## Getting started

One-time, per machine:

```bash
nix run git+https://git.cmu.dev/ScottyLabs/kennel#login
```

Then, in the repository:

```bash
cp .env.example .env
devenv allow
```

The shell resolves secrets from OpenBao as it loads, so the login above has to
happen first. Once inside:

```bash
api-dev      # Flask on :8080
web-dev      # Next.js on :3000
migrate      # alembic upgrade head
```

## Deployment

Kennel deploys three long-lived branches and ignores every other branch push.
Open a pull request to get a build.

| Branch    | Profile | URL                                |
| --------- | ------- | ---------------------------------- |
| `main`    | prod    | `cal.scottylabs.org`, `api.cal.scottylabs.org` |
| `staging` | staging | `cal-web-staging.scottylabs.net`   |
| `dev`     | dev     | `cal-web-dev.scottylabs.net`       |

Each service exposes `GET /api/health`. Kennel polls it every 2s for up to 60s
after starting a service and marks the deployment failed if it never returns
200, so the public domain is never routed to a service that didn't come up.

Preview deployments are **disabled** (`scottylabs.kennel.previewDeployments =
false`) because the first cutover keeps the existing Supabase database, which
every deployment would otherwise share. Re-enable them once the data moves into
a kennel-provisioned Postgres.

## Secrets

Declared in `secretspec.toml`, resolved from OpenBao, injected as environment
variables at deploy time. Never committed.

```bash
secretspec set -P prod SUPABASE_DB_URL   # set one
secretspec check -P prod                 # verify the profile resolves
```

`web/.env.production` is the one exception: `NEXT_PUBLIC_*` values are inlined
by Next.js at build time, which happens before kennel resolves secrets. Both
values in it are public by design.

## Known gaps

These are tracked as part of the migration and are not yet done:

- [x] ~~`api/uv.lock`~~ — generated, 132 packages locked.
- [x] ~~`npmDepsHash`~~ — resolved.
- [ ] **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is empty** in
      `web/.env.production`. Copy it from the Clerk dashboard or the Vercel
      project settings. Until it is set, every page except `/api/health`
      returns 500.
- [ ] **`nix build .#api` is unverified.** It fails on macOS with
      `mkdir: command not found` inside pyproject hook derivations — a
      Determinate Nix 3.22.2 structured-attrs bug on darwin, not a packaging
      fault. `uv sync` resolves the lockfile and the generated `bin/api`
      entrypoint serves `/api/health`, so the first real check of the uv2nix
      build happens in CI on x86_64-linux.
- [ ] **`cmucal.com` is not a registered Cloudflare zone** in
      `ScottyLabs/infrastructure`. Until it is, the apex domain cannot point at
      kennel — hence `cal.scottylabs.org` above. Needs a devops PR adding the
      zone ID to `modules/hosts/deploy-01/kennel.nix`.
- [ ] **`api/Dockerfile` is dead.** Railway used it; kennel does not. Delete
      once the deployment is green.
- [ ] **Supabase is still the database.** Migrating into kennel's provisioned
      Postgres (`scottylabs.postgres.enable`, read `DATABASE_URL`) is the
      follow-up that unblocks preview deployments.
- [ ] **Clerk is still the auth provider**, not the Keycloak `oidc_client` that
      governance provisions for this repo. Deliberate for the lift-and-shift.
