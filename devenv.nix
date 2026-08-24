{
  pkgs,
  lib,
  inputs,
  ...
}:
{
  imports = [ inputs.scottylabs.devenvModules.default ];

  scottylabs = {
    enable = true;
    project.name = "cal";

    python.enable = true;

    # The first cutover keeps the existing Supabase database, so every
    # deployment would share one database. Previews stay off until the data
    # moves into a kennel-provisioned Postgres.
    kennel.previewDeployments = false;

    kennel.services = {
      api = {
        customDomain = "api.cal.scottylabs.org";
      };
      web = {
        customDomain = "cal.scottylabs.org";
      };
    };
  };

  # Node is not part of the shared module set; the web service needs it for
  # local development.
  packages = [
    pkgs.nodejs_22
    pkgs.uv
  ];

  # The shared module wires `ty` to the uv venv it creates from a pyproject.toml
  # at the devenv root. This repo keeps the Python project under api/, so no
  # root venv exists and every third-party import resolves to nothing - roughly
  # 200 spurious unresolved-import errors that drown the genuine type errors
  # underneath. Disabled until the Python project is hoisted to the root or ty
  # is pointed at api/.venv. Tracked in README.md.
  git-hooks.hooks.ty.enable = lib.mkForce false;

  scripts = {
    api-dev.exec = "cd api && python run.py";
    web-dev.exec = "cd web && npm run dev";
    migrate.exec = "cd api && APP_ENV=development alembic upgrade head";
    migrate-down.exec = "cd api && APP_ENV=development alembic downgrade -1";
  };
}
