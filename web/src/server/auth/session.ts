// The browser session lives in encrypted, httpOnly cookies on the web origin;
// there is no server-side session store (the web service has no database).
//
//   cal_session  path=/          profile + Keycloak refresh token
//   cal_at       path=/api/auth  cached access token, only a cache: if it is
//                                missing or too big for a cookie the token
//                                route just refreshes
//   cal_login    path=/api/auth  PKCE verifier, nonce and state for a login
//                                in flight, 10 minutes
//
// Each is a JWE (dir + A256GCM) under a key derived from SESSION_SECRET, with
// its own audience so one cannot be replayed as another. JavaScript never sees
// the refresh token; the browser only ever gets short-lived access tokens
// from GET /api/auth/token.
import { createHash } from "node:crypto";

import { EncryptJWT, jwtDecrypt } from "jose";
import type { NextResponse } from "next/server";

import type { AuthConfig } from "./config";
import type { LoginTransaction, Profile, TokenSet } from "./oidc";

export const SESSION_COOKIE = "cal_session";
export const ACCESS_COOKIE = "cal_at";
export const LOGIN_COOKIE = "cal_login";

const AUTH_PATH = "/api/auth";
const LOGIN_TTL_S = 10 * 60;
// Browsers drop cookies over 4096 bytes including the name and attributes.
const MAX_COOKIE_VALUE = 3800;

type Audience = "session" | "access" | "login";

export interface Session {
  profile: Profile;
  refreshToken: string;
  /** epoch ms */
  refreshTokenExpiresAt: number;
}

interface AccessCache {
  accessToken: string;
  accessTokenExpiresAt: number;
  sub: string;
}

function keyFor(config: AuthConfig): Uint8Array {
  return createHash("sha256").update(`cal-web-session:${config.sessionSecret}`).digest();
}

async function seal(
  config: AuthConfig,
  aud: Audience,
  payload: Record<string, unknown>,
  expiresAtMs: number,
): Promise<string> {
  return new EncryptJWT(payload)
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setAudience(aud)
    .setIssuedAt()
    .setExpirationTime(Math.floor(expiresAtMs / 1000))
    .encrypt(keyFor(config));
}

async function unseal<T>(
  config: AuthConfig,
  aud: Audience,
  value: string | undefined,
): Promise<T | null> {
  if (!value) return null;
  try {
    const { payload } = await jwtDecrypt(value, keyFor(config), { audience: aud });
    return payload as T;
  } catch {
    return null; // tampered, expired, or sealed under a rotated secret
  }
}

function cookieOptions(config: AuthConfig, path: string, expiresAtMs: number) {
  return {
    httpOnly: true,
    secure: config.secureCookies,
    // Lax still sends the cookie on the top-level GET that Ricochet redirects
    // to, which the login cookie needs, while keeping it off cross-site POSTs.
    sameSite: "lax" as const,
    path,
    expires: new Date(expiresAtMs),
  };
}

// --- session -------------------------------------------------------------------

export async function readSession(
  config: AuthConfig,
  value: string | undefined,
): Promise<Session | null> {
  const session = await unseal<Session>(config, "session", value);
  if (!session?.profile?.sub || !session.refreshToken) return null;
  if (session.refreshTokenExpiresAt <= Date.now()) return null;
  return session;
}

export async function writeSession(
  res: NextResponse,
  config: AuthConfig,
  profile: Profile,
  tokens: TokenSet,
): Promise<void> {
  const session: Session = {
    profile,
    refreshToken: tokens.refreshToken,
    refreshTokenExpiresAt: tokens.refreshTokenExpiresAt,
  };
  const expires = tokens.refreshTokenExpiresAt;
  res.cookies.set(
    SESSION_COOKIE,
    await seal(config, "session", { ...session }, expires),
    cookieOptions(config, "/", expires),
  );

  const access = await seal(
    config,
    "access",
    { accessToken: tokens.accessToken, accessTokenExpiresAt: tokens.accessTokenExpiresAt, sub: profile.sub },
    tokens.accessTokenExpiresAt,
  );
  if (access.length <= MAX_COOKIE_VALUE) {
    res.cookies.set(ACCESS_COOKIE, access, cookieOptions(config, AUTH_PATH, tokens.accessTokenExpiresAt));
  } else {
    res.cookies.delete({ name: ACCESS_COOKIE, path: AUTH_PATH });
  }
}

export async function readAccessCache(
  config: AuthConfig,
  value: string | undefined,
  sub: string,
): Promise<AccessCache | null> {
  const cache = await unseal<AccessCache>(config, "access", value);
  return cache?.sub === sub ? cache : null;
}

export function clearSession(res: NextResponse): void {
  res.cookies.delete({ name: SESSION_COOKIE, path: "/" });
  res.cookies.delete({ name: ACCESS_COOKIE, path: AUTH_PATH });
}

// --- login in flight -------------------------------------------------------------

export async function writeLogin(
  res: NextResponse,
  config: AuthConfig,
  tx: LoginTransaction,
): Promise<void> {
  const expires = Date.now() + LOGIN_TTL_S * 1000;
  res.cookies.set(
    LOGIN_COOKIE,
    await seal(config, "login", { ...tx }, expires),
    cookieOptions(config, AUTH_PATH, expires),
  );
}

export async function readLogin(
  config: AuthConfig,
  value: string | undefined,
): Promise<LoginTransaction | null> {
  return unseal<LoginTransaction>(config, "login", value);
}

export function clearLogin(res: NextResponse): void {
  res.cookies.delete({ name: LOGIN_COOKIE, path: AUTH_PATH });
}

// --- helpers for route handlers ------------------------------------------------------

const RETURN_TO_BASE = "http://return-to.invalid";

function hasControlChars(value: string): boolean {
  for (let i = 0; i < value.length; i++) {
    const code = value.charCodeAt(i);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

/**
 * Only ever return to a path on this site. The URL parser drops tabs and
 * newlines and treats a backslash as a slash, so "/\t/evil.com" would
 * otherwise resolve to https://evil.com. Anything that does not resolve to
 * the same origin as a bare path falls back to "/".
 */
export function safeReturnTo(raw: string | null | undefined): string {
  if (
    !raw ||
    !raw.startsWith("/") ||
    raw.startsWith("//") ||
    raw.includes("\\") ||
    hasControlChars(raw)
  ) {
    return "/";
  }
  let url: URL;
  try {
    url = new URL(raw, RETURN_TO_BASE);
  } catch {
    return "/";
  }
  if (url.origin !== RETURN_TO_BASE) return "/";
  return `${url.pathname}${url.search}${url.hash}`;
}

/** The absolute URL to land on after login; always on the app's own origin. */
export function returnUrl(returnTo: string, appUrl: URL): URL {
  const url = new URL(safeReturnTo(returnTo), appUrl);
  return url.origin === appUrl.origin ? url : new URL("/", appUrl);
}
