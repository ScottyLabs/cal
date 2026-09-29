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
        customDomain = "api.cmucal.com";
      };
      web = {
        customDomain = "cmucal.com";
      };
    };
  };

  # Node is not part of the shared module set; the web service needs it for
  # local development.
  #
  # rustc is here only to satisfy CI. The shared prepare action runs
  # Swatinem/rust-cache unconditionally with cmd-format "devenv shell {0}",
  # so it probes `devenv shell rustc -vV` in every project and fails the job
  # when there is no Rust toolchain on PATH. This project has no Rust. Worth
  # raising with devops so the step becomes conditional; until then this is
  # the cheapest way to keep the probe happy without pulling in the whole
  # scottylabs.rust module.
  packages = [
    pkgs.nodejs_22
    pkgs.uv
    pkgs.rustc
  ];

  # The shared module runs `ty check` from the devenv root, but this repo keeps
  # the Python project under api/. ty.toml at the root points ty at api/.venv
  # and api/, which clears the ~120 spurious unresolved imports. What is left
  # is about 100 genuine diagnostics (mostly Optional handling and argument
  # types), so the hook stays off until those are fixed. Enabling it also needs
  # api/.venv to exist in the shell, since the shared module only runs
  # `uv sync` for a pyproject.toml at the root. Tracked in README.md.
  git-hooks.hooks.ty.enable = lib.mkForce false;

  scripts = {
    api-dev.exec = "cd api && python run.py";
    web-dev.exec = "cd web && npm run dev";
    migrate.exec = "cd api && APP_ENV=development alembic upgrade head";
    migrate-down.exec = "cd api && APP_ENV=development alembic downgrade -1";
  };
}
