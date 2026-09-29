import { type NextRequest, NextResponse } from "next/server";

import { getAuthConfig } from "~/server/auth/config";
import { isInvalidGrant, refresh } from "~/server/auth/oidc";
import {
  ACCESS_COOKIE,
  clearSession,
  readAccessCache,
  readSession,
  SESSION_COOKIE,
  writeSession,
} from "~/server/auth/session";

export const dynamic = "force-dynamic";

// Hand out an access token early rather than let one expire mid-request.
const MIN_REMAINING_MS = 60_000;

function json(body: unknown, status = 200) {
  const res = NextResponse.json(body, { status });
  res.headers.set("Cache-Control", "no-store");
  return res;
}

// GET /api/auth/token -> { accessToken, expiresAt } for the signed-in user.
// The browser sends it to the API as `Authorization: Bearer`. Same-origin
// only: no CORS headers are set, so another site cannot read the response.
export async function GET(req: NextRequest) {
  const config = getAuthConfig();
  const session = await readSession(config, req.cookies.get(SESSION_COOKIE)?.value);
  if (!session) {
    const res = json({ error: "signed_out" }, 401);
    clearSession(res);
    return res;
  }

  const force = req.nextUrl.searchParams.get("force") === "1";
  const cached = await readAccessCache(
    config,
    req.cookies.get(ACCESS_COOKIE)?.value,
    session.profile.sub,
  );
  if (!force && cached && cached.accessTokenExpiresAt - Date.now() > MIN_REMAINING_MS) {
    return json({ accessToken: cached.accessToken, expiresAt: cached.accessTokenExpiresAt });
  }

  try {
    const tokens = await refresh(config, session.refreshToken);
    const res = json({ accessToken: tokens.accessToken, expiresAt: tokens.accessTokenExpiresAt });
    await writeSession(res, config, session.profile, tokens);
    return res;
  } catch (err) {
    if (isInvalidGrant(err)) {
      // The Keycloak session ended (idle timeout, max age, revoked).
      const res = json({ error: "signed_out" }, 401);
      clearSession(res);
      return res;
    }
    console.error("[auth] token refresh failed:", err);
    return json({ error: "unavailable" }, 503);
  }
}
