import { type NextRequest, NextResponse } from "next/server";

import { getAuthConfig } from "~/server/auth/config";
import { finishLogin } from "~/server/auth/oidc";
import {
  clearLogin,
  LOGIN_COOKIE,
  readLogin,
  returnUrl,
  writeSession,
} from "~/server/auth/session";

export const dynamic = "force-dynamic";

// GET /api/auth/callback?code=...&state=...&iss=...
// Reached from Ricochet, never from Keycloak directly.
export async function GET(req: NextRequest) {
  const config = getAuthConfig();
  const fail = (reason: string) => {
    const res = NextResponse.redirect(
      new URL(`/?login_error=${encodeURIComponent(reason)}`, config.appUrl),
    );
    clearLogin(res);
    return res;
  };

  const tx = await readLogin(config, req.cookies.get(LOGIN_COOKIE)?.value);
  if (!tx) return fail("expired");

  const params = req.nextUrl.searchParams;
  const idpError = params.get("error");
  if (idpError) return fail(idpError);
  // openid-client checks this too; failing early keeps a stale or foreign
  // state from ever reaching the token endpoint.
  if (params.get("state") !== tx.state) return fail("state");

  try {
    const { tokens, profile } = await finishLogin(config, req.nextUrl.search, tx);
    const res = NextResponse.redirect(returnUrl(tx.returnTo, config.appUrl));
    res.headers.set("Cache-Control", "no-store");
    clearLogin(res);
    await writeSession(res, config, profile, tokens);
    return res;
  } catch (err) {
    console.error("[auth] callback failed:", err);
    return fail("callback");
  }
}
