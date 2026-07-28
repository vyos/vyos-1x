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

  // The slug segment is restricted to the sphinx slug charset so hostile text can never
  // reach URL construction as a version identifier (CodeQL js/xss-through-dom).
  it("accepts real version slugs", () => {
    expect(P.parseLocation("/en/rolling/index.html")).toMatchObject({ slug: "rolling" });
    expect(P.parseLocation("/en/1.5/cli/index.html")).toMatchObject({ slug: "1.5" });
  });
  it("rejects a slug carrying markup metacharacters", () => {
    expect(P.parseLocation("/en/foo<img>/page.html")).toBeNull();
  });
  it("rejects a slug carrying a quote or a space", () => {
    expect(P.parseLocation('/en/foo"bar/page.html')).toBeNull();
    expect(P.parseLocation("/en/foo bar/page.html")).toBeNull();
  });
  // "." and ".." are the only normalizing dot-segments: as a slug they would walk out of
  // the /<lang>/<slug>/ tree once the browser resolves the URL. Interior dots are fine.
  it("rejects the dot-segments '.' and '..' as slugs, keeping dotted version slugs", () => {
    expect(P.parseLocation("/en/../index.html")).toBeNull();
    expect(P.parseLocation("/en/./index.html")).toBeNull();
    expect(P.parseLocation("/en/1.5/index.html")).toMatchObject({ slug: "1.5" });
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

/* DOM-text sources (select.value, location.pathname) reach a location.href sink, so every
 * path component is percent-encoded at construction time (CodeQL js/xss-through-dom). */
describe("URL construction percent-encodes hostile path components", () => {
  const loc = { lang: "en", slug: "1.5", rest: "cli/index.html" };
  // Characters that could break out of a path segment or introduce a URL scheme.
  const HOSTILE = ['"', "'", "<", ">", " ", ":"];

  it("is a no-op on legitimate sphinx slugs — URLs byte-identical to pre-hardening", () => {
    expect(P.targetUrlFor(loc, "1.4")).toBe("/en/1.4/cli/index.html");
    expect(P.targetUrlFor(loc, "rolling")).toBe("/en/rolling/cli/index.html");
    expect(P.targetUrlFor({ lang: "en", slug: "1.4", rest: "" }, "1.5")).toBe("/en/1.5/");
    expect(P.langUrlFor(loc, "de")).toBe("/de/1.5/cli/index.html");
  });

  it("encodePath keeps '/' separators while encoding each segment", () => {
    expect(P.encodePath("cli/index.html")).toBe("cli/index.html");
    expect(P.encodePath('a b/c"d/e.html')).toBe("a%20b/c%22d/e.html");
  });

  // location.pathname returns well-formed escapes verbatim, so encoding blindly would
  // double-encode them (%2E -> %252E) and break the deep link on the HEAD probe.
  it("encodePath normalizes pre-existing escapes instead of double-encoding", () => {
    expect(P.encodePath("index%2Ehtml")).toBe("index.html");
    expect(P.encodePath("a%20b/c.html")).toBe("a%20b/c.html");
    expect(P.encodePath("a%2Fb/c")).toBe("a%2Fb/c"); // encoded slash stays in its segment
  });

  it("encodePath degrades safely on a malformed escape (no throw)", () => {
    const url = P.encodePath("100%zz/x");
    expect(url).toBe("100%25zz/x");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });

  // Normalization runs per %HH run, not per segment: a whole-segment decode throws on the
  // malformed escape and then double-encodes the valid one beside it (a%2520b%25zz).
  it("encodePath normalizes each escape run independently in a mixed-validity segment", () => {
    const url = P.encodePath("a%20b%zz/x");
    expect(url).toBe("a%20b%25zz/x");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });

  it("encodePath keeps an invalid-UTF-8 escape run verbatim (already pure %HH text)", () => {
    const url = P.encodePath("x%E0%A4y.html");
    expect(url).toBe("x%E0%A4y.html");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });

  it("targetUrlFor encodes a markup-injecting target slug", () => {
    const url = P.targetUrlFor(loc, '"><img src=x>');
    expect(url).toBe("/en/%22%3E%3Cimg%20src%3Dx%3E/cli/index.html");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });

  it("targetUrlFor kills the colon in a javascript:-shaped slug", () => {
    expect(P.targetUrlFor(loc, "javascript:alert(1)"))
      .toBe("/en/javascript%3Aalert(1)/cli/index.html");
  });

  it("targetUrlFor encodes a hostile lang segment", () => {
    const url = P.targetUrlFor({ lang: 'en"><script>', slug: "1.5", rest: "a.html" }, "1.4");
    expect(url).toBe("/en%22%3E%3Cscript%3E/1.4/a.html");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });

  it("langUrlFor encodes the new lang plus the retained slug and rest", () => {
    const url = P.langUrlFor({ lang: "en", slug: 'x"y', rest: 'a b/c.html' }, "de<i>");
    expect(url).toBe("/de%3Ci%3E/x%22y/a%20b/c.html");
    for (const c of HOSTILE) expect(url).not.toContain(c);
  });
});
