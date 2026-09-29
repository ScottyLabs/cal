import { NextResponse } from "next/server";

// Kennel polls this every 2s for up to 60s after starting the service and will
// not route the public domain here until it returns 200. It deliberately does
// not touch the auth config, so an auth misconfiguration shows up as a login
// error rather than a failed deploy.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
