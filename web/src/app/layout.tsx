import "~/styles/globals.css";
import localFont from 'next/font/local';
import { GeistMono } from 'geist/font/mono';

import type { Metadata } from "next";
import ThemeProvider from "@components/ThemeProvider";
import Navbar from "@components/Navbar";
import SignedOutNav from "@components/SignedOutNav";
import BottomNav from "@components/BottomNav";
import Welcome from "@components/Welcome";
import { AuthProvider, SignedIn, SignedOut } from "~/context/AuthContext";
import { GcalEventsProvider } from "../context/GCalEventsContext";
import { EventStateProvider } from "~/context/EventStateContext";
import { UserProvider } from "~/context/UserContext";
import ModalRender from "@components/ModalRender";
import PostHogPageViews from "@components/PostHogPageViews";
import { getSessionProfile } from "~/server/auth/current";

// next/font/google downloads at build time, which fails in the Nix sandbox on
// the CI runner (no network). Inter is vendored as a latin-subset variable
// woff2, and Geist Mono comes from the self-hosted `geist` package, which
// already exposes the same --font-geist-mono variable. Rendering is unchanged.
const inter = localFont({
  src: './fonts/Inter-Variable.woff2',
  variable: '--font-inter',
  display: 'swap',
  weight: '100 900',
});

// Signed-in state comes from the session cookie, so nothing here may be
// prerendered at build time.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "CMUCal",
  description: "A scheduling app that consolidates resources and events on campus.",
  icons: { icon: "/favicon.ico", apple: "/apple-touch-icon.png" },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // The API links or creates the users row itself on the first authenticated
  // call (AuthProvider asks for /users/me), so nothing is sent from here.
  const profile = await getSessionProfile();

  return (
    <AuthProvider initialUser={profile}>
      <html lang="en" className="h-full" suppressHydrationWarning>
        <body className={`${inter.variable} ${GeistMono.variable} font-sans antialiased dark:bg-[#0F1115] h-full`}>
          <PostHogPageViews apiKey={process.env.POSTHOG_KEY} apiHost={process.env.POSTHOG_HOST} />
          <GcalEventsProvider>
            <EventStateProvider>
              <UserProvider>
                <ThemeProvider>
                  <SignedIn>
                    <div className="flex flex-col h-full">
                      <Navbar />
                      <main className="flex-1 overflow-auto">
                        <ModalRender/>
                        {children}
                      </main>
                      <BottomNav />
                    </div>
                  </SignedIn>
                  <SignedOut>
                    <SignedOutNav />
                    <main>
                      <div className="flex justify-center items-center h-[calc(100vh-5rem)] dark:bg-gray-700">
                        <Welcome />
                      </div>
                    </main>
                  </SignedOut>
                </ThemeProvider>
              </UserProvider>
            </EventStateProvider>
          </GcalEventsProvider>
        </body>
      </html>
    </AuthProvider>
  );
}
