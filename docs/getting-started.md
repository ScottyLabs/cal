# Getting Started

Run the CMUCal frontend and backend on your laptop. You do not need nix or
devenv; only kennel and CI use them.

## 1. Join the org

1. [Sign up on git.cmu.dev](https://git.cmu.dev/user/sign_up) and
   [add an SSH key](https://docs.scottylabs.org/scottylabs/onboarding/forgejo-setup.html).
1. Ask the tech lead to add you to the CMUCal team in
   [governance](https://git.cmu.dev/ScottyLabs/governance).
1. Link all five accounts (CMU, git.cmu.dev, GitHub, Discord, Slack) at
   [idp.scottylabs.org](https://idp.scottylabs.org/realms/scottylabs/account/account-security/linked-accounts).
   Governance validation fails if one is missing.

## 2. Prerequisites

Node 22 with npm, Python 3.10 or newer, [uv](https://docs.astral.sh/uv/),
and the OpenBao and secretspec CLIs:

```bash
brew install uv openbao secretspec
```

On Windows, install uv from its site and take `bao` and `secretspec` from the
[OpenBao](https://github.com/openbao/openbao/releases) and
[secretspec](https://github.com/cachix/secretspec/releases) releases.

## 3. Secrets

Dev secrets live in OpenBao. Once governance has added you to the CMUCal team,
log in with your CMU account (it opens a browser):

```bash
bao login -address=https://secrets.scottylabs.org -method=oidc
```

The token lasts a few weeks; run it again when secretspec reports permission
denied. Then clone the repository and check that every secret resolves:

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
secretspec check -P dev
```

`secretspec run -P dev -- <command>` starts a command with the secrets in its
environment, so nothing secret is written to disk. If OpenBao does not work
for you, use the [manual setup](#manual-setup) instead.

## 4. Backend

```bash
cd api
uv sync
secretspec run -P dev -- uv run python run.py
```

The API listens on http://localhost:8080; `curl localhost:8080/api/health`
checks it.

## 5. Frontend

In another terminal, from the repository root:

```bash
cd web
npm install
secretspec run -P dev -- npm run dev
```

Open http://localhost:8090 and sign in with your CMU account.

The dev server runs on port 8090 because that is the only address the dev
Keycloak client returns to. In deployed environments the
[Ricochet](https://codeberg.org/anish/ricochet) relay serves it; locally the
web app serves it itself (`web/src/app/oauth2/callback`), so there is no relay
to install or run.

## 6. Migrations

When a pull request adds an Alembic migration:

```bash
cd api
secretspec run -P dev -- uv run alembic upgrade head
```

Everyone shares one dev database. Never run `alembic downgrade` without asking
the tech lead, and never point a local checkout at production.

## Manual setup

Without OpenBao, keep the secrets in local env files and run every command
above without the `secretspec run -P dev --` prefix.

```bash
cp api/.env.example api/.env.development
cp web/.env.example web/.env.local
```

In `api/.env.development`, fill in `SUPABASE_DB_URL` (the shared dev
database). In `web/.env.local`, fill in `OIDC_CLIENT_SECRET` and
`SESSION_SECRET` (any random 32+ characters). Ask the tech lead for the
values, or copy them from `secretspec/cal/dev` in the
[OpenBao web UI](https://secrets.scottylabs.org/ui/) (sign in with OIDC). Never
commit these files.

## Troubleshooting

- **secretspec reports permission denied**: your OpenBao token expired, so
  run `bao login` again. If it still fails, governance has not added you to
  the CMUCal team yet.
- **Sign-in says Keycloak login is not configured**: `npm run dev` was started
  without `secretspec run -P dev --`, or (manual setup) a value in
  `web/.env.local` is empty. Next.js reads env files only at startup, so
  restart `npm run dev` after editing it.
- **Sign-in ends on a connection error at `localhost:8090`**: the web app is
  not running, or something else holds port 8090 (an old Ricochet, for
  example). `lsof -i :8090` on macOS or Linux shows what.
- **API crashes with `Expected string or URL object, got None`**:
  `SUPABASE_DB_URL` is missing: the API was started without
  `secretspec run -P dev --`, or (manual setup) `api/.env.development` does not
  exist or you did not start the API from `api/`.
- **Pages load but data never does**: some CMU networks block outbound
  Postgres. Try CMU-SECURE, eduroam, or a hotspot.
