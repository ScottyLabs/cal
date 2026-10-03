"use client"; // Required for event handlers in the App Router

// import Link from "next/link";

import React from "react";
import axios from "axios";
import { useSearchParams } from "next/navigation";
// import google_login_icon from "@/components/icons/google_login_icons/svg/light/web_light_sq_SI.svg"; // Ensure the correct import path

import { signInUrl } from "~/context/AuthContext";

axios.defaults.withCredentials = true;

const LOGIN_ERRORS: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  expired: "That sign-in took too long. Please try again.",
};

// Sign in goes to Keycloak, which hands off to CMU's own login page.
const Login: React.FC = () => {
  const reason = useSearchParams().get("login_error");
  const error = reason ? (LOGIN_ERRORS[reason] ?? "Sign-in failed. Please try again.") : null;

  return (
    <div className="flex flex-col items-center gap-3">
      <a
        href={signInUrl("/")}
        className="rounded-full bg-[#C41230] px-8 py-3 text-lg font-medium text-white shadow hover:bg-[#a50f28]"
      >
        Sign in with CMU
      </a>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
};

export default function Welcome() {
  return (
    <div className="flex flex-col items-center justify-center">
      <div className="h-3/5 text-center">
        <h1 className="text-black font-serif text-[76px] font-normal leading-normal dark:text-[#E6E8EC]">
          Welcome to CMUCal
        </h1>
        <h2 className="text-black font-serif text-[35px] font-normal leading-normal mb-6 dark:text-[#A1A6B0]">
          the all-in-one CMU resources platform
        </h2>
        <h3 className="pb-6 pt-2 dark:text-[#C7CBD4]">
          Log in with your CMU credentials
        </h3>
        <div className="flex justify-center gap-8 pb-14">
          {/* <SignInButton /> */}
            <Login />
        </div>
      </div>
    </div>
  );
}
