# Getting Started

Run the CMUCal frontend and backend on your laptop. There are two ways:

- **devenv** (once you are on the CMUCal team): one command starts the API,
  the web app and the sign-in relay, with the dev secrets loaded from OpenBao.
  Needs Nix, so macOS, Linux or WSL.
- **Manual**: install the tools yourself and keep the secrets in local env
  files. Works anywhere, including Windows, and before governance has added
  you.

## 1. Join the org

1. [Sign up on git.cmu.dev](https://git.cmu.dev/user/sign_up) and
   [add an SSH key](https://docs.scottylabs.org/scottylabs/onboarding/forgejo-setup.html).
1. Ask the tech lead to add you to the CMUCal team in
   [governance](https://git.cmu.dev/ScottyLabs/governance).
1. Link all five accounts (CMU, git.cmu.dev, GitHub, Discord, Slack) at
   [idp.scottylabs.org](https://idp.scottylabs.org/realms/scottylabs/account/account-security/linked-accounts).
   Governance validation fails if one is missing.

## 2. Run with devenv

Install Nix and devenv ([devenv.sh/getting-started](https://devenv.sh/getting-started/)),
then log in to OpenBao once per machine. It opens a browser; sign in with your
CMU account:

```bash
nix run git+https://git.cmu.dev/ScottyLabs/kennel#login
```

Clone the repository and start everything:

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
devenv up
```

`devenv up` runs the API on http://localhost:8080, the web app on
http://localhost:3000, and [Ricochet](https://codeberg.org/anish/ricochet) on
port 8090, the relay that Keycloak sends sign-ins back through. Open
http://localhost:3000 and sign in with your CMU account. Ctrl-C stops all
three.

For other commands, `devenv shell` opens a shell with the dev secrets in its
environment.

## 3. Manual setup

### Prerequisites

Node 22 with npm, Python 3.10 or newer, [uv](https://docs.astral.sh/uv/), and
[Rust](https://rustup.rs) (to install Ricochet).

### Secrets

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
cp api/.env.example api/.env.development
cp web/.env.example web/.env.local
```

In `api/.env.development`, fill in `SUPABASE_DB_URL` (the shared dev
database). In `web/.env.local`, fill in `OIDC_CLIENT_SECRET` and
`SESSION_SECRET` (any random 32+ characters). Ask the tech lead for the
values, or copy them from `secretspec/cal/dev` in the
[OpenBao web UI](https://secrets.scottylabs.org/ui/) (sign in with OIDC). Never
commit these files.

If you have the `bao` and `secretspec` CLIs, you can skip the env files: run
`bao login -address=https://secrets.scottylabs.org -method=oidc` once, then
start the API and web app below with `secretspec run -P dev --` in front.

### Backend

```bash
cd api
uv sync
uv run python run.py
```

The API listens on http://localhost:8080; `curl localhost:8080/api/health`
checks it.

### Sign-in relay

Sign-in goes through ScottyLabs Keycloak, which only returns to the
[Ricochet](https://codeberg.org/anish/ricochet) relay on port 8090. Install it
once:

```bash
cargo install --git https://codeberg.org/anish/ricochet --rev ddc58bcad0bb2b898f900a3c13c94c263e797ad2 --locked
```

Then start it in its own terminal and leave it running. On macOS or Linux:

```bash
RICOCHET_DEV=1 RICOCHET_BIND=127.0.0.1:8090 ricochet
```

On Windows (PowerShell):

```powershell
$env:RICOCHET_DEV="1"; $env:RICOCHET_BIND="127.0.0.1:8090"; ricochet
```

It is running when it prints `ricochet listening bind=127.0.0.1:8090`.

### Frontend

In another terminal, from the repository root:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 and sign in with your CMU account.

## 4. Migrations

When a pull request adds an Alembic migration, run this from `api/`, inside
`devenv shell` or with your env files in place:

```bash
uv run alembic upgrade head
```

Everyone shares one dev database. Never run `alembic downgrade` without asking
the tech lead, and never point a local checkout at production.

## Troubleshooting

- **`devenv up` or secretspec fails with a secret or permission error**: log
  in to OpenBao again. If it still fails, governance has not added you to the
  CMUCal team yet; use the manual setup until it does.
- **Sign-in ends on a connection error at `localhost:8090`**: Ricochet is not
  running. In the manual setup, start it as above; without `RICOCHET_DEV` and
  `RICOCHET_BIND` set it exits right away. Opening `localhost:8090` itself
  shows a 404, which is normal.
- **Sign-in says Keycloak login is not configured**: a value in
  `web/.env.local` is empty. Next.js reads env files only at startup, so
  restart `npm run dev` after editing it.
- **API crashes with `Expected string or URL object, got None`**:
  `SUPABASE_DB_URL` is missing: `api/.env.development` does not exist, or you
  did not start the API from `api/`.
- **Pages load but data never does**: some CMU networks block outbound
  Postgres. Try CMU-SECURE, eduroam, or a hotspot.
