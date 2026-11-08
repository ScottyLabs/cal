{
  description = "CMU Cal - a unified web calendar for all CMU academic events";

  nixConfig = {
    extra-substituters = [ "https://scottylabs.cachix.org" ];
    extra-trusted-public-keys = [
      "scottylabs.cachix.org-1:hajjEX5SLi/Y7yYloiXTt2IOr3towcTGRhMh1vu6Tjg="
    ];
  };

  inputs = {
    scottylabs.url = "git+https://git.cmu.dev/ScottyLabs/kennel";
    nixpkgs.follows = "scottylabs/nixpkgs";
    flake-parts.follows = "scottylabs/flake-parts";
  };

  outputs =
    inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [ inputs.scottylabs.flakeModules.default ];
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      perSystem =
        {
          pkgs,
          lib,
          helpers,
          ...
        }:
        let
          node = pkgs.nodejs_22;
          curl = lib.getExe pkgs.curl;
        in
        {
          scottylabs = {
            project.name = "cal";

            python = {
              enable = true;
              dir = "api";
            };

            # the hooks check runs the tests against a migrated copy
            postgres.enable = true;
            hooksCheck.setup = lib.mkAfter ''
              export SUPABASE_DB_URL="$DATABASE_URL"
              (cd api && APP_ENV=development alembic upgrade head)
            '';

            ricochet = {
              enable = true;
              appUrl = "http://localhost:3000";
            };

            deno = {
              enable = true;
              react.enable = true;
              dirs = [ "web" ];
            };

            # every deployment would share the one Supabase database
            previewDeployments = false;

            processes = {
              api = {
                run = "cd api && exec secretspec run -P dev -- python run.py";
                ready = "${curl} -sf http://localhost:8080/api/health";
              };
              web = {
                run = "cd web && exec secretspec run -P dev -- deno task dev";
                ready = "${curl} -s -o /dev/null http://localhost:3000";
              };
            };

            shell.scripts = {
              migrate = "cd api && APP_ENV=development alembic upgrade head";
              migrate-down = "cd api && APP_ENV=development alembic downgrade -1";
            };
          };

          pre-commit.settings.hooks = {
            deno-test.enable = lib.mkForce false;
            vitest = {
              enable = true;
              name = "vitest";
              entry = "deno task --cwd web test --run";
              files = "^web/.*\\.(ts|tsx|js|jsx|mts|cjs|mjs)$";
              pass_filenames = false;
              language = "system";
            };
          };

          # the venv has a console script for every dependency
          services.api = {
            package = lib.addMetaAttrs { mainProgram = "api"; } (helpers.buildPythonService { src = ./api; });
            customDomain = "api.cmucal.com";
          };

          services.web = {
            package =
              (helpers.buildDenoTask {
                src = ./web;
                pname = "cal-web";
                output = ".";
              }).overrideAttrs
                (old: {
                  nativeBuildInputs = old.nativeBuildInputs ++ [ pkgs.makeWrapper ];

                  env = {
                    NEXT_TELEMETRY_DISABLED = "1";
                    # next.config.js validates src/env.js at build time, and the deployed values come from web/.env.production
                    SKIP_ENV_VALIDATION = "1";
                  };

                  # the deploy host exports its own HOSTNAME, which the standalone server would bind to
                  installPhase = ''
                    runHook preInstall

                    mkdir -p $out/share/cal-web/.next
                    cp -r .next/standalone/. $out/share/cal-web/
                    cp -r .next/static $out/share/cal-web/.next/static
                    cp -r public $out/share/cal-web/public

                    chmod -R u+w $out/share/cal-web
                    find $out/share/cal-web/node_modules -name '*musl*' -prune -exec rm -rf {} +
                    autoPatchelf $out/share/cal-web/node_modules

                    makeWrapper ${node}/bin/node $out/bin/web \
                      --add-flags "$out/share/cal-web/server.js" \
                      --set HOSTNAME "0.0.0.0" \
                      --chdir "$out/share/cal-web"

                    runHook postInstall
                  '';

                  meta.mainProgram = "web";
                });
            customDomain = "cmucal.com";
          };

          # forwards the retired domain to cmucal.com, keeping the path
          sites.redirect = {
            package = pkgs.runCommand "cal-redirect" { } ''
              mkdir -p $out
              cp ${./redirect/index.html} $out/index.html
            '';
            spa = true;
            customDomain = "cal.scottylabs.org";
          };
        };
    };
}
