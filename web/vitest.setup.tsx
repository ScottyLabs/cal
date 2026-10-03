// vitest.setup.tsx
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, vi } from "vitest";

// Testing Library only unmounts automatically when vitest globals are enabled.
afterEach(() => {
  cleanup();
});

vi.mock("~/context/AuthContext", () => {
  const value = {
    user: { sub: "test-sub", email: "test@andrew.cmu.edu", name: "Test User" },
    isSignedIn: true,
    dbUser: {
      id: 1,
      email: "test@andrew.cmu.edu",
      fname: "Test",
      lname: "User",
      calendar_id: null,
      is_site_admin: false,
    },
    signIn: vi.fn(),
    signOut: vi.fn(),
  };
  return {
    useAuth: () => value,
    AuthProvider: ({ children }: { children: ReactNode }) => children,
    SignedIn: ({ children }: { children: ReactNode }) => children,
    SignedOut: () => null,
    signInUrl: (returnTo = "/") => `/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`,
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => "/",
}));