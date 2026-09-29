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

Node 22 with npm, Python 3.10 or newer, and [uv](https://docs.astral.sh/uv/)
(`brew install uv`).

## 3. Backend

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
cp api/.env.example api/.env.development
```

Fill in `SUPABASE_DB_URL` (the shared dev database; ask the tech lead). Then:

```bash
cd api
uv sync
uv run python run.py
```

The API listens on http://localhost:8080; `curl localhost:8080/api/health`
checks it.

## 4. Frontend

Sign-in goes through ScottyLabs Keycloak and the
[Ricochet](https://codeberg.org/anish/ricochet) relay, which you run locally.
Install it once (needs [Rust](https://rustup.rs)):

```bash
cargo install --git https://codeberg.org/anish/ricochet --rev ddc58bcad0bb2b898f900a3c13c94c263e797ad2 --locked
```

Then, in its own terminal:

```bash
RICOCHET_DEV=1 RICOCHET_BIND=127.0.0.1:8090 ricochet
```

In another terminal, from the repository root:

```bash
cp web/.env.example web/.env.local
```

Fill in `OIDC_CLIENT_SECRET` (ask the tech lead) and `SESSION_SECRET` (any
random 32+ characters). Then:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 and sign in with your CMU account.

## 5. Migrations

When a pull request adds an Alembic migration:

```bash
cd api
uv run alembic upgrade head
```

Everyone shares one dev database. Never run `alembic downgrade` without asking
the tech lead, and never point a local checkout at production.

## Troubleshooting

- **Sign-in says Keycloak login is not configured**: a value in
  `web/.env.local` is empty. Next.js reads env files only at startup, so
  restart `npm run dev` after editing it.
- **Sign-in ends on a connection error at `localhost:8090`**: Ricochet is not
  running.
- **API crashes with `Expected string or URL object, got None`**:
  `SUPABASE_DB_URL` is missing, or you did not start the API from `api/`.
- **Pages load but data never does**: some CMU networks block outbound
  Postgres. Try CMU-SECURE, eduroam, or a hotspot.
