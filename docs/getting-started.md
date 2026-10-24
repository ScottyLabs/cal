# Getting Started

Run the CMUCal API and web app on your laptop and sign in with your CMU
account. Pick the setup that fits you:

| Setup | Who | Secrets come from | You run |
| --- | --- | --- | --- |
| [A. Manual](#a-manual) | Anyone, including before governance adds you | Env files you fill in | 2 terminals |
| [B. OpenBao](#b-openbao) | CMUCal team members, any OS | OpenBao, via `secretspec` | 2 terminals |
| [C. devenv](#c-devenv) | CMUCal team members with Nix (macOS, Linux, WSL) | OpenBao, via devenv | `devenv up` |

All three run the same thing: the API on http://localhost:8080 and the web app
on http://localhost:3000, against the shared dev database.

## 1. Join the org

1. [Sign up on git.cmu.dev](https://git.cmu.dev/user/sign_up) and
   [add an SSH key](https://docs.scottylabs.org/scottylabs/onboarding/forgejo-setup.html).
1. Link all five accounts (CMU, git.cmu.dev, GitHub, Discord, Slack) at
   [idp.scottylabs.org](https://idp.scottylabs.org/realms/scottylabs/account/account-security/linked-accounts).
1. Ask the tech lead to add you to the CMUCal team in
   [governance](https://git.cmu.dev/ScottyLabs/governance). Governance refuses
   anyone with an unlinked account, and the team is what gives you read access
   to the dev secrets in OpenBao (setups B and C).

Then clone the repository:

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
```

## 2. Run it

### A. Manual

Install Node 22 (with npm), Python 3.10 or newer, and
[uv](https://docs.astral.sh/uv/). Then create the env files:

```bash
cp api/.env.example api/.env.development
cp web/.env.example web/.env.local
```

Fill in `SUPABASE_DB_URL` in `api/.env.development`, and `OIDC_CLIENT_SECRET`
and `SESSION_SECRET` (any random 32+ characters) in `web/.env.local`. Ask the
tech lead for the values. Never commit these files.

Start the API in one terminal:

```bash
cd api
uv sync
uv run python run.py
```

And the web app in another:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 and sign in.

### B. OpenBao

Same tools as setup A, plus the OpenBao and secretspec CLIs. On macOS,
`brew install openbao secretspec`; on Windows or Linux, download them from the
[OpenBao](https://github.com/openbao/openbao/releases) and
[secretspec](https://github.com/cachix/secretspec/releases) releases.

Log in once per machine (it opens a browser):

```bash
bao login -address=https://secrets.scottylabs.org -method=oidc
```

`secretspec check -P dev` confirms you can read every secret. Then run the
same commands as setup A without creating any env files, putting
`secretspec run -P dev --` in front of the two start commands:

```bash
cd api
uv sync
secretspec run -P dev -- uv run python run.py
```

```bash
cd web
npm install
secretspec run -P dev -- npm run dev
```

### C. devenv

Install Nix and devenv ([devenv.sh/getting-started](https://devenv.sh/getting-started/)),
then log in to OpenBao once per machine:

```bash
nix run git+https://git.cmu.dev/ScottyLabs/kennel#login
```

Then, in the repository:

```bash
devenv up
```

That starts the API, the web app and the sign-in relay together, with the dev
secrets loaded. Ctrl-C stops all of them. `devenv shell` gives you a shell with
the same secrets for other commands (tests, migrations, scripts).

## How sign-in works locally

Sign-in goes through ScottyLabs Keycloak, which only sends people back to a
relay on `localhost:8090`. The relay forwards the sign-in to the web app. In
setups A and B, `npm run dev` starts a small relay for you
(`web/scripts/dev-relay.js`); in setup C, `devenv up` runs
[Ricochet](https://codeberg.org/anish/ricochet), the relay ScottyLabs uses in
production. Either way there is nothing extra to start.

## Tests

```bash
cd api
uv sync --extra dev
uv run pytest
```

Tests that need a database read `SUPABASE_DB_URL`. Point it at a local
Postgres you can throw away, migrated with `uv run alembic upgrade head`, not
the shared dev database.

```bash
cd web
npm test
```

## Migrations

When a pull request adds an Alembic migration, apply it to the dev database
from `api/` with the dev secrets loaded (env file, `secretspec run -P dev --`,
or `devenv shell`):

```bash
uv run alembic upgrade head
```

Everyone shares one dev database. Never run `alembic downgrade` without asking
the tech lead, and never point a local checkout at production.

## Troubleshooting

- **secretspec or `devenv up` fails with a secret or permission error**: log
  in to OpenBao again. If that does not help, governance has not added you to
  the CMUCal team yet; use setup A until it does.
- **Sign-in ends on a connection error at `localhost:8090`**: the relay is not
  running. It runs inside `npm run dev` (setups A and B) or `devenv up`
  (setup C), so check that one is still up. Opening `localhost:8090` itself
  shows a 404, which is normal.
- **Sign-in says Keycloak login is not configured**: the web app is missing a
  secret. In setup A, a value in `web/.env.local` is empty; in setup B, the
  `secretspec run -P dev --` prefix is missing. Next.js reads env files only at
  startup, so restart `npm run dev` after editing them.
- **API crashes with `Expected string or URL object, got None`**:
  `SUPABASE_DB_URL` is missing. In setup A, `api/.env.development` does not
  exist or the API was not started from `api/`; in setup B, the prefix is
  missing.
- **Pages load but data never does**: some CMU networks block outbound
  Postgres. Try CMU-SECURE, eduroam, or a hotspot.
