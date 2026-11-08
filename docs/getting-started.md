# Getting Started

Run the CMU Cal frontend and backend on your laptop.

## 1. Join the org

1. [Sign up on git.cmu.dev](https://git.cmu.dev/user/sign_up) and add an SSH key to your account.
1. [Join the CMU Cal team through governance](https://git.cmu.dev/ScottyLabs/governance#joining-a-team).

## 2. Prerequisites

Install Lix by following kennel's [local development guide](https://docs.kennel.scottylabs.org/guides/local-development/#installing-nix). The dev shell provides Node 22, Python, uv, and the OpenBao and secretspec CLIs.

## 3. Secrets

Dev secrets live in OpenBao. Once governance has added you to the CMU Cal team, log in as described in kennel's [secrets guide](https://docs.kennel.scottylabs.org/guides/secrets/#local-development). Then clone the repository and enter the dev shell:

```bash
git clone git@git.cmu.dev:ScottyLabs/cal.git
cd cal
nix develop
```

## 4. Run

```bash
pitchfork start --local
```

This starts the API on http://localhost:8080, the frontend on http://localhost:3000, and the [Ricochet](https://docs.kennel.scottylabs.org/guides/local-development/#oauth-relay) relay that sign-in through ScottyLabs Keycloak goes through. Open http://localhost:3000 and sign in with your CMU account. Kennel's [local development guide](https://docs.kennel.scottylabs.org/guides/local-development/#local-services) covers following and stopping the processes.

## 5. Migrations

When a pull request adds an Alembic migration, run `migrate` in the dev shell.

Everyone shares one dev database. Ask the tech lead before running `migrate-down`, and keep local checkouts off the production database.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| secretspec reports permission denied | Your OpenBao token expired, so run the login command again. If it still fails, governance has not added you to the CMU Cal team yet. |
| Sign-in ends on a connection error at `localhost:8090` | Ricochet is not running. `pitchfork status` shows whether it started. |
| Pages load but data never does | Some CMU networks block outbound Postgres. Try CMU-SECURE, eduroam, or a hotspot. |
