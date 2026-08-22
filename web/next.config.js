/**
 * Run `build` or `dev` with `SKIP_ENV_VALIDATION` to skip env validation. This is especially useful
 * for Docker builds.
 */
import "./src/env.js";

/** @type {import("next").NextConfig} */
const config = {
  // Kennel deploys this as a systemd service from a read-only Nix store path.
  // Standalone output traces the exact dependency set into a self-contained
  // server, instead of shipping the whole node_modules tree.
  output: "standalone",
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
  eslint: {
    // !! Warning !!
    // This allows production builds to successfully complete even if
    // your project has ESLint errors.
    // !! Warning !!
    ignoreDuringBuilds: true,
  },
};

export default config;
