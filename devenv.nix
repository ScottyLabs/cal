{ pkgs, inputs, ... }:
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

  scripts = {
    api-dev.exec = "cd api && python run.py";
    web-dev.exec = "cd web && npm run dev";
    migrate.exec = "cd api && APP_ENV=development alembic upgrade head";
    migrate-down.exec = "cd api && APP_ENV=development alembic downgrade -1";
  };
}
