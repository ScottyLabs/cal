// A stand-in for Ricochet's dev mode (https://codeberg.org/anish/ricochet), so
// local sign-in works without installing it. The cal-dev Keycloak client only
// returns to http://localhost:8090/oauth2/callback; this forwards the
// authorization response on to the return_to URL in the OAuth state, which
// must be on this machine. Deployed environments use the real Ricochet.
import { createServer } from "node:http";
import { isIP } from "node:net";

export const RELAY_HOST = "127.0.0.1";
export const RELAY_PORT = 8090;
const CALLBACK_PATH = "/oauth2/callback";
const FORWARDED = [
  "code",
  "session_state",
  "iss",
  "error",
  "error_description",
];

/**
 * @param {string} text
 * @returns {unknown}
 */
const parseJson = (text) => JSON.parse(text);

/** @param {string} hostname */
function isLoopback(hostname) {
  if (hostname.toLowerCase() === "localhost") return true;
  const ip = hostname.replace(/^\[(.*)\]$/, "$1");
  if (isIP(ip) === 4) return ip.startsWith("127.");
  return ip === "::1";
}

/**
 * Where to send the browser for a callback query, or null to refuse it.
 * Matches Ricochet with RICOCHET_DEV set and no allowlist.
 * @param {URLSearchParams} query
 * @returns {URL | null}
 */
export function relayTarget(query) {
  const state = query.get("state");
  if (!state) return null;

  // Unpadded base64url only, as Ricochet decodes it; Buffer is more lenient.
  const encoded = state.trim();
  if (!/^[A-Za-z0-9_-]+$/.test(encoded) || encoded.length % 4 === 1) {
    return null;
  }

  let target;
  try {
    const envelope = parseJson(
      Buffer.from(encoded, "base64url").toString("utf8"),
    );
    if (
      typeof envelope !== "object" ||
      envelope === null ||
      !("return_to" in envelope) ||
      typeof envelope.return_to !== "string"
    ) {
      return null;
    }
    target = new URL(envelope.return_to);
  } catch {
    return null;
  }
  if (!["http:", "https:"].includes(target.protocol)) return null;
  if (!isLoopback(target.hostname)) return null;

  target.searchParams.append("state", state);
  for (const key of FORWARDED) {
    const value = query.get(key);
    if (value !== null) target.searchParams.append(key, value);
  }
  return target;
}

/** @returns {Promise<import("node:http").Server>} */
export function startDevRelay() {
  const server = createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (req.method !== "GET" || url.pathname !== CALLBACK_PATH) {
      res.writeHead(404).end();
      return;
    }
    const target = relayTarget(url.searchParams);
    if (target) {
      res.writeHead(302, { Location: target.href }).end();
    } else {
      res.writeHead(400, { "Content-Type": "text/plain" }).end("invalid state");
    }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(RELAY_PORT, RELAY_HOST, () => resolve(server));
  });
}
