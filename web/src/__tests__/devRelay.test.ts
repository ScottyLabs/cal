// @vitest-environment node
import { describe, expect, it } from "vitest";

import { relayTarget } from "../../scripts/dev-relay.js";

const state = (envelope: object) =>
  Buffer.from(JSON.stringify(envelope)).toString("base64url");

const callback = (params: Record<string, string>) =>
  relayTarget(new URLSearchParams(params));

describe("relayTarget", () => {
  it("forwards the code and the unchanged state to a local return_to", () => {
    const s = state({
      return_to: "http://localhost:3000/api/auth/callback",
      csrf: "x",
    });
    const target = callback({ state: s, code: "abc", iss: "https://idp" });

    expect(target?.origin + (target?.pathname ?? "")).toBe(
      "http://localhost:3000/api/auth/callback",
    );
    expect(target?.searchParams.get("state")).toBe(s);
    expect(target?.searchParams.get("code")).toBe("abc");
    expect(target?.searchParams.get("iss")).toBe("https://idp");
    expect(target?.searchParams.has("session_state")).toBe(false);
  });

  it("forwards an IdP error", () => {
    const target = callback({
      state: state({ return_to: "http://127.0.0.1:3000/cb" }),
      error: "access_denied",
      error_description: "no",
    });
    expect(target?.searchParams.get("error")).toBe("access_denied");
    expect(target?.searchParams.get("error_description")).toBe("no");
  });

  it.each([
    ["a non-local host", { return_to: "https://evil.example.com/cb" }],
    ["a lookalike host", { return_to: "http://localhost.evil.com/cb" }],
    ["a non-http scheme", { return_to: "javascript:alert(1)" }],
    ["a missing return_to", { csrf: "x" }],
  ])("refuses %s", (_, envelope) => {
    expect(callback({ state: state(envelope), code: "abc" })).toBeNull();
  });

  it("refuses a missing or malformed state", () => {
    expect(callback({ code: "abc" })).toBeNull();
    expect(callback({ state: "not-json", code: "abc" })).toBeNull();
  });

  it("refuses state that Ricochet would not decode", () => {
    const s = state({ return_to: "http://localhost:3000/cb" });
    expect(callback({ state: s, code: "abc" })).not.toBeNull();
    expect(callback({ state: `${s}==`, code: "abc" })).toBeNull();
    expect(callback({ state: `${s}!!`, code: "abc" })).toBeNull();
  });
});
