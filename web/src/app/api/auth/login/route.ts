import { type NextRequest, NextResponse } from "next/server";

import { getAuthConfig } from "~/server/auth/config";
import { startLogin } from "~/server/auth/oidc";
import { safeReturnTo, writeLogin } from "~/server/auth/session";

export const dynamic = "force-dynamic";

// GET /api/auth/login?returnTo=/some/path
// Sends the browser to Keycloak (which hands off to CMU's login). Keycloak
// redirects to Ricochet, and Ricochet to /api/auth/callback on APP_URL.
export async function GET(req: NextRequest) {
  let config;
  try {
    config = getAuthConfig();
  } catch (err) {
    console.error("[auth]", err instanceof Error ? err.message : err);
    return new NextResponse("Sign-in is not configured on this deployment.", {
      status: 503,
      headers: { "Content-Type": "text/plain" },
    });
  }
  const returnTo = safeReturnTo(req.nextUrl.searchParams.get("returnTo"));

  // The login cookie must be set on the origin the callback will land on, so
  // start from APP_URL if we were reached some other way (www., 127.0.0.1).
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (host && host !== config.appUrl.host) {
    const canonical = new URL("/api/auth/login", config.appUrl);
    canonical.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(canonical);
  }

  try {
    const { url, tx } = await startLogin(config, returnTo);
    const res = NextResponse.redirect(url);
    res.headers.set("Cache-Control", "no-store");
    await writeLogin(res, config, tx);
    return res;
  } catch (err) {
    console.error("[auth] could not start login:", err);
    return NextResponse.redirect(new URL("/?login_error=unavailable", config.appUrl));
  }
}
