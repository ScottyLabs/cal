import "~/styles/globals.css";
import localFont from 'next/font/local';
import { GeistMono } from 'geist/font/mono';

import { ClerkProvider } from '@clerk/nextjs';
import type { Metadata } from "next";
import ThemeProvider from "@components/ThemeProvider";
import Navbar from "@components/Navbar";
import SignedOutNav from "@components/SignedOutNav";
import BottomNav from "@components/BottomNav";
import Welcome from "@components/Welcome";
import { SignedIn, SignedOut } from "@clerk/nextjs";
import { GcalEventsProvider } from "../context/GCalEventsContext";
import { EventStateProvider } from "~/context/EventStateContext";
import { UserProvider } from "~/context/UserContext";
import ModalRender from "@components/ModalRender";
import { auth, clerkClient } from "@clerk/nextjs/server";
import { loginWithClerk } from "./utils/api/users";

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

export const metadata: Metadata = {
  title: "CMUCal",
  description: "A scheduling app that consolidates resources and events on campus.",
  icons: [{ rel: "icon", url: "/Favicon.png" }],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth();
  const client = await clerkClient()

  if (userId) {
    const user = await client.users.getUser(userId)
    try {
      await loginWithClerk(
        user.id,
        user.emailAddresses[0]?.emailAddress,
        user.firstName,
        user.lastName
      );
    } catch (err) {
      console.error("Error during Clerk login:", err);
    }
  }

  return (
    <ClerkProvider>
      <html lang="en" className="h-full">
        <body className={`${inter.variable} ${GeistMono.variable} font-sans antialiased dark:#0F1115 h-full`}>
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
                      <div className="flex justify-center items-center h-[90vh] dark:bg-gray-700">
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
    </ClerkProvider>
  );
}
