"use client";

import posthog from "posthog-js";
import { useEffect } from "react";

// The root layout passes the key and host in at request time. Kennel injects
// secrets when the service starts, after the Nix build, so they cannot be
// NEXT_PUBLIC_ values inlined by the build.
export default function PostHogPageViews({
  apiKey,
  apiHost,
}: {
  apiKey?: string;
  apiHost?: string;
}) {
  useEffect(() => {
    if (!apiKey) return;
    posthog.init(apiKey, {
      api_host: apiHost,
      defaults: "2026-08-30",
      // Page views only: no click autocapture, session replay or surveys.
      autocapture: false,
      disable_session_recording: true,
      disable_surveys: true,
    });
  }, [apiKey, apiHost]);

  return null;
}
