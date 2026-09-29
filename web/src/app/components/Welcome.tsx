"use client"; // Required for event handlers in the App Router

// import Link from "next/link";

import React from "react";
import axios from "axios";
import Image from "next/image";
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

const About: React.FC = () => {
  return (
    <div className="bg-gray-200 p-6 rounded-lg shadow-md w-1/2 dark:bg-gray-800 dark:text-gray-300">
      <h3 className="text-xl font-medium mb-4 font-serif font-source-serif-pro">About</h3>
      <p>
        CMUCal offers convenient search for academic resources and events on campus, with the option of adding
        events to your personal Google Calendar.
      </p>
    </div>
  );
};

const Video: React.FC = () => {
  return (
    <div className="border-gray p-6 rounded-lg shadow-md w-1/2 dark:bg-gray-600 dark:text-gray-300 dark: border-gray-200">
      <p className="text-xl font-medium mb-4 font-serif font-source-serif-pro">Video Tutorial</p>
    </div>
  );
};

export default function Welcome() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <div className="h-3/5 bg-lightgrey text-center">
        <h1 className="text-black font-serif font-source-serif-pro text-[76px] font-normal leading-normal pt-18 dark:text-[#E6E8EC]">
          Welcome to CMUCal
        </h1>
        <h2 className="text-black font-serif font-source-serif-pro text-[35px] font-normal leading-normal mb-6 dark:text-[#A1A6B0]">
          the all-in-one CMU resources platform
        </h2>
        <h3 className="pb-6 pt-2 dark:text-[#C7CBD4]">
          Log in with your CMU Credentials
        </h3>
        <div className="flex justify-center gap-8 pb-14">
          {/* <SignInButton /> */}
            <Login />
        </div>
      </div>

      {/* <div className="flex justify-around px-10 py-6 gap-8 pb-20">
        <About />
        <Video />
      </div> */}
    </main>
  );
}
