import { NextResponse } from "next/server";

// Kennel polls this every 2s for up to 60s after starting the service and will
// not route the public domain here until it returns 200. It must stay outside
// Clerk's protection - see the matcher in src/middleware.ts.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok" }, { status: 200 });
}
