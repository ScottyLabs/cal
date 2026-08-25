# cal

A unified web calendar for all CMU academic events. Deployed with
[kennel](https://docs.kennel.scottylabs.org).

This repository replaces the two GitHub repositories the project used to live
in - `ScottyLabs/cmucal` (frontend) and `ScottyLabs/cmucal-backend` - which were
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

- [x] ~~`api/uv.lock`~~ - generated, 132 packages locked.
- [x] ~~`npmDepsHash`~~ - resolved.
- [ ] **Clerk is on its `pk_test_` instance**, not production. The test key
      is committed in `web/.env.production` (publishable keys are public by
      design) so the staged cutover to `cal.scottylabs.org` works. Before
      `cmucal.com` goes live this needs the `pk_live_` key **and** the new
      domain added to the production Clerk instance's allowed origins -
      neither of which carries over automatically.
- [ ] **`nix build .#api` is unverified.** It fails on macOS with
      `mkdir: command not found` inside pyproject hook derivations - a
      Determinate Nix 3.22.2 structured-attrs bug on darwin, not a packaging
      fault. `uv sync` resolves the lockfile and the generated `bin/api`
      entrypoint serves `/api/health`, so the first real check of the uv2nix
      build happens in CI on x86_64-linux.
- [ ] **`cmucal.com` is not a registered Cloudflare zone** in
      `ScottyLabs/infrastructure`. Until it is, the apex domain cannot point at
      kennel - hence `cal.scottylabs.org` above. Needs a devops PR adding the
      zone ID to `modules/hosts/deploy-01/kennel.nix`.
- [ ] **Supabase is still the database.** Both projects (`cmucal`,
      `cmucal-dev`) idled into a paused state and were restored on
      2026-08-22; the data survived intact. Migrating into kennel's
      provisioned Postgres (`scottylabs.postgres.enable`, read
      `DATABASE_URL`) is the follow-up that unblocks preview deployments and
      removes the free-tier pause risk that took production down for four
      months.
- [ ] **Lint and type-check are scoped down, not satisfied.** The shared hook
      set reported 673 ruff findings and ~200 ty errors against code that had
      never been linted. What landed: the two genuine `F821` undefined-name
      bugs are fixed, 240 findings were auto-fixed (import ordering, unused
      imports), and `api/pyproject.toml` now selects `E4/E7/E9/F/I` with
      documented ignores. Still deferred, in rough order of value:
      `RUF013` implicit Optional (21), `DTZ*` naive datetimes (44),
      `BLE001` blind except (68), `UP*` typing modernisation (101).
- [ ] **The `ty` hook is disabled.** The shared module points it at a uv venv
      built from a root `pyproject.toml`; this repo keeps the Python project
      under `api/`, so nothing resolves and the real type errors are buried
      under ~200 spurious unresolved-import ones. Fix is to hoist the Python
      project to the repo root or point `ty` at `api/.venv`, then re-enable.
- [ ] **Clerk is still the auth provider**, not the Keycloak `oidc_client` that
      governance provisions for this repo. Deliberate for the lift-and-shift.
