// OIDC against ScottyLabs Keycloak through the Ricochet relay, following the
// org pattern in housing (apps/backend/src/auth/oidc.ts) and cmugpt-surface
// (apps/server/src/routes/authRoutes.ts). openid-client does the protocol and
// all token validation; this module only decides the redirect_uri and state.
//
// Ricochet contract (codeberg.org/anish/ricochet): the IdP redirect_uri is the
// relay, and our real callback rides in `state` as base64url(JSON) with a
// `return_to` field. The relay checks return_to against its host allowlist
// and forwards code, state (byte for byte), session_state and iss to it.
import { randomBytes } from "node:crypto";

import * as client from "openid-client";

import { type AuthConfig, callbackUrl } from "./config";

export const SCOPE = "openid email profile";

let configPromise: Promise<client.Configuration> | null = null;

export function getOidcClient(config: AuthConfig): Promise<client.Configuration> {
  configPromise ??= client
    .discovery(new URL(config.issuer), config.clientId, config.clientSecret)
    .catch((err: unknown) => {
      configPromise = null; // don't cache a failed discovery
      throw err;
    });
  return configPromise;
}

export interface LoginTransaction {
  state: string;
  codeVerifier: string;
  nonce: string;
  returnTo: string;
}

/** The Ricochet envelope: where to land, plus a random value for CSRF. */
export function relayState(config: AuthConfig): string {
  const envelope = {
    return_to: callbackUrl(config),
    csrf: randomBytes(24).toString("base64url"),
  };
  return Buffer.from(JSON.stringify(envelope)).toString("base64url");
}

export async function startLogin(
  config: AuthConfig,
  returnTo: string,
): Promise<{ url: URL; tx: LoginTransaction }> {
  const oidc = await getOidcClient(config);
  const codeVerifier = client.randomPKCECodeVerifier();
  const tx: LoginTransaction = {
    state: relayState(config),
    codeVerifier,
    nonce: client.randomNonce(),
    returnTo,
  };
  const url = client.buildAuthorizationUrl(oidc, {
    redirect_uri: config.relayUrl,
    scope: SCOPE,
    response_type: "code",
    state: tx.state,
    nonce: tx.nonce,
    code_challenge: await client.calculatePKCECodeChallenge(codeVerifier),
    code_challenge_method: "S256",
  });
  return { url, tx };
}

export interface TokenSet {
  accessToken: string;
  /** epoch ms */
  accessTokenExpiresAt: number;
  refreshToken: string;
  /** epoch ms; when Keycloak will stop accepting the refresh token */
  refreshTokenExpiresAt: number;
}

export interface Profile {
  sub: string;
  email?: string;
  name?: string;
  givenName?: string;
  familyName?: string;
}

// Keycloak's default SSO Session Max; only used if it omits refresh_expires_in.
const FALLBACK_REFRESH_LIFETIME_S = 10 * 60 * 60;

function toTokenSet(
  res: client.TokenEndpointResponse & client.TokenEndpointResponseHelpers,
  previousRefreshToken?: string,
): TokenSet {
  const refreshToken = res.refresh_token ?? previousRefreshToken;
  if (!refreshToken) {
    throw new Error("Keycloak did not return a refresh token");
  }
  const now = Date.now();
  const refreshExpiresIn =
    typeof res.refresh_expires_in === "number" && res.refresh_expires_in > 0
      ? res.refresh_expires_in
      : FALLBACK_REFRESH_LIFETIME_S;
  return {
    accessToken: res.access_token,
    accessTokenExpiresAt: now + (res.expiresIn() ?? 60) * 1000,
    refreshToken,
    refreshTokenExpiresAt: now + refreshExpiresIn * 1000,
  };
}

function str(value: unknown): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}

/**
 * Exchange the code Ricochet forwarded. The token request's redirect_uri must
 * be the one the code was issued for, i.e. the relay, so the relay URL is
 * passed as the "current URL" carrying the incoming query (code, state, iss).
 * openid-client checks state, iss, PKCE and the ID token (signature, aud,
 * nonce, expiry).
 */
export async function finishLogin(
  config: AuthConfig,
  incomingSearch: string,
  tx: LoginTransaction,
): Promise<{ tokens: TokenSet; profile: Profile }> {
  const oidc = await getOidcClient(config);
  const currentUrl = new URL(config.relayUrl);
  currentUrl.search = incomingSearch;

  const res = await client.authorizationCodeGrant(oidc, currentUrl, {
    expectedState: tx.state,
    expectedNonce: tx.nonce,
    pkceCodeVerifier: tx.codeVerifier,
    idTokenExpected: true,
  });
  const claims = res.claims();
  if (!claims?.sub) {
    throw new Error("ID token has no sub");
  }
  return {
    tokens: toTokenSet(res),
    profile: {
      sub: claims.sub,
      email: str(claims.email),
      name: str(claims.name) ?? str(claims.preferred_username),
      givenName: str(claims.given_name),
      familyName: str(claims.family_name),
    },
  };
}

export async function refresh(config: AuthConfig, refreshToken: string): Promise<TokenSet> {
  const oidc = await getOidcClient(config);
  return toTokenSet(await client.refreshTokenGrant(oidc, refreshToken), refreshToken);
}

/** True when Keycloak rejected the grant itself (session over), not a network blip. */
export function isInvalidGrant(err: unknown): boolean {
  return (
    err instanceof client.ResponseBodyError &&
    (err.error === "invalid_grant" || err.error === "unauthorized_client")
  );
}

/** Best effort: ends this client's Keycloak session for the refresh token. */
export async function revoke(config: AuthConfig, refreshToken: string): Promise<void> {
  try {
    const oidc = await getOidcClient(config);
    await client.tokenRevocation(oidc, refreshToken, { token_type_hint: "refresh_token" });
  } catch (err) {
    console.warn("[auth] refresh token revocation failed:", err);
  }
}
