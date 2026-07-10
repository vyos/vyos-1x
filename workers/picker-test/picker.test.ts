import { describe, it, expect } from "vitest";
// The workers pool has no real filesystem (node:fs readFileSync is an unimplemented
// stub — see @cloudflare/vitest-pool-workers/dist/worker/lib/node/fs.mjs, and confirmed
// empirically here: "readFileSync() is not yet implemented in Workers"). Same constraint
// documented in apex/test/manifest.test.ts; import as Vite `?raw` / native JSON assets
// instead so content is inlined at bundle time — no runtime filesystem access needed.
// eslint-disable-next-line import/no-unresolved
import src from "../../docs/_static/js/version-picker.js?raw";
// eslint-disable-next-line import/no-unresolved
import manifest from "../versions.json";

// Evaluate the plain script and grab its namespace (no DOM access at module scope allowed).
const ns: Record<string, CallableFunction> = {};
new Function("window", src)(ns as never);
const P = (ns as never as { VyOSVersionPicker: Record<string, CallableFunction> }).VyOSVersionPicker;

describe("parseLocation", () => {
  it("extracts lang/slug/rest from a docs path", () => {
    expect(P.parseLocation("/en/1.5/cli/index.html"))
      .toEqual({ lang: "en", slug: "1.5", rest: "cli/index.html" });
  });
  it("returns null off the version tree (e.g. previews without prefix knowledge)", () => {
    expect(P.parseLocation("/kb/x")).toBeNull();
  });
});

describe("bannerFor (§4)", () => {
  it("dev → info banner", () => {
    expect(P.bannerFor("rolling", manifest)).toMatchObject({ kind: "dev" });
  });
  it("newest lts → no banner; older lts → newer-lts notice naming 1.5", () => {
    expect(P.bannerFor("1.5", manifest)).toBeNull();
    expect(P.bannerFor("1.4", manifest)).toMatchObject({ kind: "newer-lts", newest: "1.5" });
  });
  it("eol → warning linking newest LTS", () => {
    expect(P.bannerFor("1.3", manifest)).toMatchObject({ kind: "eol", newest: "1.5" });
  });
});

describe("targetUrlFor", () => {
  it("same path on target version", () => {
    expect(P.targetUrlFor({ lang: "en", slug: "1.5", rest: "cli/index.html" }, "1.4"))
      .toBe("/en/1.4/cli/index.html");
  });
});

describe("navUrlFor (query + fragment preserved across version switch)", () => {
  const loc = { lang: "en", slug: "1.4", rest: "quick-start.html" };
  it("neither → bare target path", () => {
    expect(P.navUrlFor(loc, "1.5", "", "")).toBe("/en/1.5/quick-start.html");
  });
  it("query-only", () => {
    expect(P.navUrlFor(loc, "1.5", "?ref=x", ""))
      .toBe("/en/1.5/quick-start.html?ref=x");
  });
  it("hash-only", () => {
    expect(P.navUrlFor(loc, "1.5", "", "#section-3"))
      .toBe("/en/1.5/quick-start.html#section-3");
  });
  it("both, in query-then-hash order", () => {
    expect(P.navUrlFor(loc, "1.5", "?ref=x", "#section-3"))
      .toBe("/en/1.5/quick-start.html?ref=x#section-3");
  });
});
