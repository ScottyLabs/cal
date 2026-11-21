import { type NextRequest, NextResponse } from "next/server";

import { callbackUrl, getAuthConfig } from "~/server/auth/config";

export const dynamic = "force-dynamic";

// GET /oauth2/callback: the cal-dev Keycloak client only returns to
// localhost:8090/oauth2/callback, which Ricochet normally serves. The dev
// server listens on 8090 itself, so Keycloak lands here and this does
// Ricochet's job: pass the query (code, state, iss, ...) on unchanged to
// /api/auth/callback, where the login cookie is scoped. Deployed environments
// go through the real Ricochet, so this route is off in production.
export function GET(req: NextRequest) {
  if (process.env.NODE_ENV === "production") {
    return new NextResponse(null, { status: 404 });
  }
  const target = new URL(callbackUrl(getAuthConfig()));
  target.search = req.nextUrl.search;
  return NextResponse.redirect(target);
}
