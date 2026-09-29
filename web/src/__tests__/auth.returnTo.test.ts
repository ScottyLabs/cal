// @vitest-environment node
import { describe, expect, it } from "vitest";

import { returnUrl, safeReturnTo } from "~/server/auth/session";

const APP = new URL("https://cmucal.com");

describe("safeReturnTo", () => {
  it.each([
    ["/", "/"],
    ["/manager", "/manager"],
    ["/manager?tab=admins#top", "/manager?tab=admins#top"],
    ["/a/../b", "/b"],
  ])("keeps the local path %j", (raw, expected) => {
    expect(safeReturnTo(raw)).toBe(expected);
  });

  it.each([
    null,
    undefined,
    "",
    "manager",
    "https://evil.example/",
    "//evil.example",
    "/\\evil.example",
    "\\\\evil.example",
    // The URL parser strips tabs and newlines, which would turn these into
    // "//evil.example". searchParams.get decodes %09 and %0A to exactly this.
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r\n/evil.example",
    "/\u0000/evil.example",
  ])("rejects %j", (raw) => {
    expect(safeReturnTo(raw)).toBe("/");
  });

  it("rejects the decoded form of a %09 attack", () => {
    const raw = new URLSearchParams("returnTo=/%09/evil.example").get("returnTo");
    expect(safeReturnTo(raw)).toBe("/");
  });
});

describe("returnUrl", () => {
  it("resolves a local path on the app origin", () => {
    expect(returnUrl("/manager?x=1", APP).href).toBe("https://cmucal.com/manager?x=1");
  });

  it.each(["/\t/evil.example", "//evil.example", "https://evil.example/"])(
    "never leaves the app origin for %j",
    (raw) => {
      expect(returnUrl(raw, APP).origin).toBe(APP.origin);
    },
  );
});
