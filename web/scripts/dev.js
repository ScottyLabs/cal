// `npm run dev`: the local sign-in relay on :8090, then the Next.js dev server.
// `devenv up` runs the real Ricochet instead and starts Next with `dev:next`.
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

import { RELAY_HOST, RELAY_PORT, startDevRelay } from "./dev-relay.js";

try {
  await startDevRelay();
  console.log(`sign-in relay listening on http://${RELAY_HOST}:${RELAY_PORT}`);
} catch (err) {
  if (/** @type {NodeJS.ErrnoException} */ (err).code !== "EADDRINUSE") {
    throw err;
  }
  console.log(`port ${RELAY_PORT} is in use; assuming Ricochet runs there`);
}

const nextBin = createRequire(import.meta.url).resolve("next/dist/bin/next");
const next = spawn(
  process.execPath,
  [nextBin, "dev", "--turbo", ...process.argv.slice(2)],
  { stdio: "inherit" },
);

// Pass stop signals on so Next never outlives this script, then exit the way
// Next did.
/** @type {NodeJS.Signals[]} */
const signals = ["SIGINT", "SIGTERM", "SIGHUP"];
const forward = (/** @type {NodeJS.Signals} */ signal) => next.kill(signal);
for (const signal of signals) process.on(signal, forward);

next.on("error", (err) => {
  console.error(err);
  process.exit(1);
});
next.on("exit", (code, signal) => {
  for (const s of signals) process.off(s, forward);
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 1);
});
