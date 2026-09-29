// Server-only settings for the Keycloak login. Read at request time rather
// than build time: kennel injects secrets when the service starts, after the
// Nix build has run, so none of these may be NEXT_PUBLIC_ or read in
// next.config.js.

export interface AuthConfig {
  /** https://idp.scottylabs.org/realms/scottylabs */
  issuer: string;
  clientId: string;
  clientSecret: string;
  /**
   * The Ricochet relay registered as the client's only redirect URI:
   * https://oauth.scottylabs.org/oauth2/callback deployed, or
   * http://localhost:8090/oauth2/callback in local development.
   */
  relayUrl: string;
  /** This deployment's public origin, e.g. https://cmucal.com. */
  appUrl: URL;
  /** Keys the encrypted session cookies. */
  sessionSecret: string;
  secureCookies: boolean;
}

const MIN_SECRET_LENGTH = 32;

let cached: AuthConfig | null = null;

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Keycloak login is not configured: ${name} is not set`);
  }
  return value;
}

export function getAuthConfig(): AuthConfig {
  if (cached) return cached;

  const keycloakUrl = required("KEYCLOAK_URL").replace(/\/+$/u, "");
  const realm = required("KEYCLOAK_REALM");
  const sessionSecret = required("SESSION_SECRET");
  if (sessionSecret.length < MIN_SECRET_LENGTH) {
    throw new Error(`SESSION_SECRET must be at least ${MIN_SECRET_LENGTH} characters`);
  }
  // Kennel sets APP_URL for every deployment (the custom domain in prod).
  const appUrl = new URL(required("APP_URL"));

  cached = {
    issuer: `${keycloakUrl}/realms/${realm}`,
    clientId: required("OIDC_CLIENT_ID"),
    clientSecret: required("OIDC_CLIENT_SECRET"),
    relayUrl: required("OAUTH_RELAY_URL"),
    appUrl: new URL(appUrl.origin),
    sessionSecret,
    secureCookies: appUrl.protocol === "https:",
  };
  return cached;
}

/** Where Ricochet bounces the authorization code back to. */
export function callbackUrl(config: AuthConfig): string {
  return new URL("/api/auth/callback", config.appUrl).toString();
}
