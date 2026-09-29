import { cookies } from "next/headers";

import { getAuthConfig } from "./config";
import type { Profile } from "./oidc";
import { readSession, SESSION_COOKIE } from "./session";

/**
 * The signed-in user's profile for server rendering, or null.
 *
 * This only proves the browser holds a session cookie we sealed. The API
 * never relies on it: every API call carries a Keycloak access token that the
 * API verifies itself.
 */
export async function getSessionProfile(): Promise<Profile | null> {
  // Read cookies first, unconditionally: it is what marks every page as
  // per-request. Without it a build that lacks the auth env (the Nix build
  // always does) would prerender a signed-out page and serve it to everyone.
  const store = await cookies();
  let config;
  try {
    config = getAuthConfig();
  } catch (err) {
    // Render signed out rather than fail every page; /api/auth/login reports it.
    console.error("[auth]", err instanceof Error ? err.message : err);
    return null;
  }
  const session = await readSession(config, store.get(SESSION_COOKIE)?.value);
  return session?.profile ?? null;
}
