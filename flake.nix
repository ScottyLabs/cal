{
  description = "CMU Cal — a unified web calendar for all CMU academic events";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    scottylabs = {
      url = "git+https://git.cmu.dev/ScottyLabs/kennel";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { nixpkgs, scottylabs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          helpers = scottylabs.mkLib pkgs;
          node = pkgs.nodejs_22;
        in
        {
          # Flask API. buildPythonService resolves the dependency closure from
          # api/uv.lock and exposes each [project.scripts] entry under bin/, so
          # the console script in api/pyproject.toml must be named `api` to
          # match the scottylabs.kennel.services key.
          api = helpers.buildPythonService {
            src = ./api;
          };

          # Next.js server. Clerk's middleware needs a Node runtime, so this is
          # a kennel service rather than a static site — which also means it
          # cannot use a shared build helper, since kennel ships none for npm.
          web = pkgs.buildNpmPackage {
            pname = "cal-web";
            version = "0.1.0";
            src = ./web;

            # Regenerate after any package-lock.json change:
            #   nix run nixpkgs#prefetch-npm-deps -- web/package-lock.json
            npmDepsHash = "sha256-s+aaPJWwYaFyCq3c5Nolz6aKlFa/OtDb5vl3ndAXG74=";

            env = {
              NEXT_TELEMETRY_DISABLED = "1";
              # next.config.js imports src/env.js, which validates at build
              # time. The deployed values arrive from web/.env.production.
              SKIP_ENV_VALIDATION = "1";
            };

            nativeBuildInputs = [ pkgs.makeWrapper ];

            # next.config.js sets output: "standalone", so .next/standalone is
            # a self-contained server with only the traced dependencies. Static
            # assets and public/ are not traced and must be copied alongside it.
            # The standalone server reads PORT and HOSTNAME from the
            # environment, and kennel injects PORT. HOSTNAME is forced rather
            # than defaulted: the deploy host exports its own HOSTNAME, which
            # would otherwise make the server bind to a name Caddy cannot
            # reach, failing the health check.
            installPhase = ''
              runHook preInstall

              mkdir -p $out/share/cal-web
              cp -r .next/standalone/. $out/share/cal-web/
              mkdir -p $out/share/cal-web/.next
              cp -r .next/static $out/share/cal-web/.next/static
              cp -r public $out/share/cal-web/public

              makeWrapper ${node}/bin/node $out/bin/web \
                --add-flags "$out/share/cal-web/server.js" \
                --set HOSTNAME "0.0.0.0" \
                --chdir "$out/share/cal-web"

              runHook postInstall
            '';
          };
        }
      );
    };
}
