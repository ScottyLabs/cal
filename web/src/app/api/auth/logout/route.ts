import { type NextRequest, NextResponse } from "next/server";

import { getAuthConfig } from "~/server/auth/config";
import { revoke } from "~/server/auth/oidc";
import { clearSession, readSession, SESSION_COOKIE } from "~/server/auth/session";

export const dynamic = "force-dynamic";

// POST /api/auth/logout
// Drops the session cookies and revokes the refresh token at Keycloak. This is
// not an RP-initiated (end_session) logout: the governance clients register no
// post-logout redirect URI, so Keycloak and CMU's own SSO sessions survive
// and the next sign-in may complete without a password prompt.
export async function POST(req: NextRequest) {
  const config = getAuthConfig();
  const session = await readSession(config, req.cookies.get(SESSION_COOKIE)?.value);
  if (session) {
    await revoke(config, session.refreshToken);
  }
  const res = NextResponse.json({ ok: true });
  res.headers.set("Cache-Control", "no-store");
  clearSession(res);
  return res;
}
