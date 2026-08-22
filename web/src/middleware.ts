// middleware.ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/welcome(.*)",
  "/sign-in(.*)",
  "/sign-up(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  const { userId } = await auth();               

  if (!isPublicRoute(req)) {
    await auth.protect();                        
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals, static files, and the health probe
    '/((?!_next|api/health|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes, except the health probe. Clerk throws on a
    // missing publishableKey before it ever matches a route, so leaving
    // /api/health in the matcher would make an auth misconfiguration surface
    // as a kennel health-check failure instead of an auth error.
    '/(api(?!/health)|trpc)(.*)',
  ],
};
