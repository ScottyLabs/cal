"use client";

// Signed-in state for client components. The server layout reads the encrypted
// session cookie and passes the profile in, so signed-in state is known on the
// first render. `dbUser` is the API's own users row (GET /users/me), which the
// API creates or links on the first authenticated call.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiGet } from "~/app/utils/api/api";
import { clearAccessToken, onSignedOut, setHasSession } from "~/app/utils/api/token";

export interface AuthProfile {
  sub: string;
  email?: string;
  name?: string;
  givenName?: string;
  familyName?: string;
}

export interface DbUser {
  id: number;
  email: string;
  fname: string | null;
  lname: string | null;
  calendar_id: string | null;
  is_site_admin: boolean;
}

interface AuthContextValue {
  user: AuthProfile | null;
  isSignedIn: boolean;
  dbUser: DbUser | null;
  signIn: (returnTo?: string) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function currentPath(): string {
  return window.location.pathname + window.location.search;
}

export function signInUrl(returnTo = "/"): string {
  return `/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
}

export function AuthProvider({
  initialUser,
  children,
}: {
  initialUser: AuthProfile | null;
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<AuthProfile | null>(initialUser);
  const [dbUser, setDbUser] = useState<DbUser | null>(null);

  // Before any child effect can call the API.
  setHasSession(user !== null);

  useEffect(() => {
    onSignedOut(() => {
      // The Keycloak session ended; re-render the server layout signed out.
      setUser(null);
      setDbUser(null);
      window.location.reload();
    });
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    apiGet<DbUser>("/users/me")
      .then((me) => {
        if (!cancelled) setDbUser(me);
      })
      .catch((err) => console.error("Failed to load the signed-in user:", err));
    return () => {
      cancelled = true;
    };
  }, [user?.sub]);

  const signIn = useCallback((returnTo?: string) => {
    window.location.assign(signInUrl(returnTo ?? currentPath()));
  }, []);

  const signOut = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      clearAccessToken();
      window.location.assign("/");
    }
  }, []);

  const value = useMemo(
    () => ({ user, isSignedIn: user !== null, dbUser, signIn, signOut }),
    [user, dbUser, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

/** Renders children only when signed in. */
export function SignedIn({ children }: { children: React.ReactNode }) {
  return useAuth().isSignedIn ? <>{children}</> : null;
}

/** Renders children only when signed out. */
export function SignedOut({ children }: { children: React.ReactNode }) {
  return useAuth().isSignedIn ? null : <>{children}</>;
}
