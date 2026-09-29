// Browser-side access token handling. The token comes from our own
// GET /api/auth/token (which refreshes it from the httpOnly session cookie)
// and lives only in memory here, never in localStorage.

interface CachedToken {
  accessToken: string;
  expiresAt: number;
}

// Refresh this long before expiry so a token never lapses in flight.
const EARLY_REFRESH_MS = 30_000;

let cached: CachedToken | null = null;
let inflight: Promise<string | null> | null = null;
let signedOutHandler: (() => void) | null = null;
// Set by AuthProvider from the server-rendered session, so anonymous pages
// never call /api/auth/token.
let hasSession = false;

export function setHasSession(value: boolean): void {
  hasSession = value;
  if (!value) cached = null;
}

/** Called once by AuthProvider; runs when the server says the session is over. */
export function onSignedOut(handler: () => void): void {
  signedOutHandler = handler;
}

export function clearAccessToken(): void {
  cached = null;
}

async function fetchToken(force: boolean): Promise<string | null> {
  const res = await fetch(`/api/auth/token${force ? "?force=1" : ""}`, {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (res.status === 401) {
    cached = null;
    if (hasSession) {
      hasSession = false;
      signedOutHandler?.();
    }
    return null;
  }
  if (!res.ok) {
    throw new Error(`Could not get an access token (${res.status})`);
  }
  const body = (await res.json()) as CachedToken;
  cached = body;
  return body.accessToken;
}

/**
 * A valid access token for the API, or null when signed out. Concurrent
 * callers share one request to /api/auth/token.
 */
export async function getAccessToken(opts: { force?: boolean } = {}): Promise<string | null> {
  if (typeof window === "undefined" || !hasSession) return null;
  if (!opts.force && cached && cached.expiresAt - Date.now() > EARLY_REFRESH_MS) {
    return cached.accessToken;
  }
  inflight ??= fetchToken(Boolean(opts.force)).finally(() => {
    inflight = null;
  });
  return inflight;
}
