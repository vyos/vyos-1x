import { describe, it, expect } from "vitest";
import worker, { classifyPath, cacheHeaderFor, withDocsHeaders, type Env } from "../src/index";
// The workers pool has no real filesystem; import the branch wrangler configs as Vite `?raw`
// assets (pattern from apex/test/manifest.test.ts) so their content is inlined at bundle time
// for the html_handling congruence pin at the bottom of this file.
// eslint-disable-next-line import/no-unresolved
import wranglerRolling from "../wrangler.rolling.jsonc?raw";
// eslint-disable-next-line import/no-unresolved
import wranglerV15 from "../wrangler.v15.jsonc?raw";
// eslint-disable-next-line import/no-unresolved
import wranglerV14 from "../wrangler.v14.jsonc?raw";
// eslint-disable-next-line import/no-unresolved
import wranglerLegacy from "../wrangler.legacy.jsonc?raw";

describe("cache classes (§3.3)", () => {
  it("HTML + config class → max-age=0, s-maxage=300", () => {
    for (const p of ["/en/rolling/index.html", "/en/rolling/versions.json",
                     "/en/rolling/sitemap.xml", "/en/rolling/pagefind/pagefind.js"]) {
      expect(cacheHeaderFor(classifyPath(p)))
        .toBe("public, max-age=0, s-maxage=300, must-revalidate");
    }
  });
  it("PDF + _static class → max-age=300, s-maxage=600", () => {
    for (const p of ["/en/rolling/vyos-documentation.pdf", "/en/rolling/_static/css/theme.css"]) {
      expect(cacheHeaderFor(classifyPath(p)))
        .toBe("public, max-age=300, s-maxage=600, must-revalidate");
    }
  });
});

describe("response headers", () => {
  it("adds X-Docs-Build and cache-control; canary forces no-store", () => {
    const base = new Response("ok", { headers: { "content-type": "text/html" } });
    const prod = withDocsHeaders(base, "/en/rolling/index.html",
      { DOCS_BUILD_SHA: "abc123", DOCS_ENV: "production" });
    expect(prod.headers.get("X-Docs-Build")).toBe("abc123");
    expect(prod.headers.get("Cache-Control")).toBe("public, max-age=0, s-maxage=300, must-revalidate");
    const canary = withDocsHeaders(base, "/en/rolling/index.html",
      { DOCS_BUILD_SHA: "abc123", DOCS_ENV: "canary" });
    expect(canary.headers.get("Cache-Control")).toBe("no-store");
  });
});

describe("default fetch entrypoint", () => {
  const makeEnv = (docsEnv: Env["DOCS_ENV"], seen: string[]): Env => ({
    ASSETS: {
      fetch: async (req: Request) => {
        seen.push(req.url);
        return new Response("<html>", { headers: { "content-type": "text/html" } });
      },
    } as unknown as Fetcher,
    DOCS_BUILD_SHA: "testsha",
    DOCS_ENV: docsEnv,
  });

  it("serves assets verbatim with docs headers; path is byte-stable", async () => {
    const seen: string[] = [];
    const url = "https://docs.vyos.io/en/rolling/index.html";
    const resp = await worker.fetch(new Request(url), makeEnv("production", seen));
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
    expect(resp.headers.get("Cache-Control"))
      .toBe("public, max-age=0, s-maxage=300, must-revalidate");
    expect(seen).toEqual([url]); // original request URL reached ASSETS unmodified
  });

  it("canary env forces no-store on the fetch path too", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/index.html"),
      makeEnv("canary", seen),
    );
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
  });

  it("4xx/5xx responses are never cached, even in production", async () => {
    const env: Env = {
      ASSETS: {
        fetch: async () => new Response("nope", { status: 404, headers: { "content-type": "text/html" } }),
      } as unknown as Fetcher,
      DOCS_BUILD_SHA: "testsha",
      DOCS_ENV: "production",
    };
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/missing.html"),
      env,
    );
    expect(resp.status).toBe(404);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });
});

describe("directory-index mapping (html_handling \"none\", §3.2.3 amended 2026-07-22)", () => {
  // NOTE: these tests mock the ASSETS binding — they exercise the WORKER's directory
  // mapping + bare-directory probe logic, NOT the wrangler `html_handling` config (which
  // only exists at deploy time). The config-level backstop is the smoke gate,
  // scripts/docs_gates/smoke.py; the raw-string congruence test at the bottom of this file
  // is the unit-level pin against a silent revert.
  //
  // Assets binding stub emulating html_handling:"none": exact-path lookups only — no
  // extension inference and no directory auto-index. A bare "/foo/" resolves only because
  // the worker rewrites it to "/foo/index.html" first; a bare "/foo" 301s only because the
  // worker probes "/foo/index.html" and finds it — exactly the behavior under test.
  const ASSET_MAP: Record<string, string> = {
    "/en/rolling/index.html": "<html>root index</html>",
    "/en/rolling/cli.html": "<html>cli page</html>",
    "/en/rolling/guide/index.html": "<html>guide index</html>",
    "/en/rolling/installation/index.html": "<html>installation index</html>",
  };

  const makeAssetsEnv = (docsEnv: Env["DOCS_ENV"], seen: string[]): Env => ({
    ASSETS: {
      fetch: async (req: Request) => {
        seen.push(req.url);
        const body = ASSET_MAP[new URL(req.url).pathname];
        return body === undefined
          ? new Response("not found", { status: 404, headers: { "content-type": "text/html" } })
          : new Response(body, { headers: { "content-type": "text/html" } });
      },
    } as unknown as Fetcher,
    DOCS_BUILD_SHA: "testsha",
    DOCS_ENV: docsEnv,
  });

  it("trailing-slash directory URL is mapped to index.html → 200 + index content", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(200);
    expect(await resp.text()).toBe("<html>root index</html>");
    // worker rewrote "/en/rolling/" → "/en/rolling/index.html" before hitting ASSETS
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/index.html"]);
    // 200 still carries the build stamp + the page cache class
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
    expect(resp.headers.get("Cache-Control"))
      .toBe("public, max-age=0, s-maxage=300, must-revalidate");
  });

  it("explicit .html URL is served directly — 200, never a 3xx redirect", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/cli.html"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(200);
    expect(resp.status).toBeLessThan(300); // no 307/308 for explicit .html paths
    expect(await resp.text()).toBe("<html>cli page</html>");
    // passed through unmodified — the worker never rewrites explicit-file paths
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/cli.html"]);
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
    expect(resp.headers.get("Cache-Control"))
      .toBe("public, max-age=0, s-maxage=300, must-revalidate");
  });

  it("explicit nested /folder/index.html is served directly → 200", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/guide/index.html"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(200);
    expect(await resp.text()).toBe("<html>guide index</html>");
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/guide/index.html"]);
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
    expect(resp.headers.get("Cache-Control"))
      .toBe("public, max-age=0, s-maxage=300, must-revalidate");
  });

  it("extensionless file-like path (no dir behind it) probes, misses, then 404s", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/cli"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(404);
    // probe "/cli/index.html" misses (no such dir) → fall through to the exact-path fetch of
    // "/cli", which also misses (real asset is cli.html); html_handling:"none" never infers it.
    expect(seen).toEqual([
      "https://docs.vyos.io/en/rolling/cli/index.html",
      "https://docs.vyos.io/en/rolling/cli",
    ]);
    // a 404 must never carry a cacheable page/asset class
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("directory mapping preserves the original query string", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/?q=foo"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(200);
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/index.html?q=foo"]);
  });

  it("bare directory path (real dir behind it) → 301 to the slashed form, query preserved", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/installation?q=x"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(301);
    expect(resp.headers.get("Location")).toBe("/en/rolling/installation/?q=x");
    expect(resp.headers.get("X-Docs-Build")).toBe("testsha");
    // only the index.html probe reached ASSETS — the redirect short-circuits the passthrough
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/installation/index.html?q=x"]);
  });

  it("trailing-slash mapping preserves request method + conditional/range headers", async () => {
    // Codex: pins that `new Request(mapped, request)` carries method + headers to ASSETS,
    // so conditional-GET (304) and Range (206) still work on directory URLs.
    let captured: Request | undefined;
    const env: Env = {
      ASSETS: {
        fetch: async (req: Request) => {
          captured = req;
          return new Response(null, { headers: { "content-type": "text/html" } });
        },
      } as unknown as Fetcher,
      DOCS_BUILD_SHA: "testsha",
      DOCS_ENV: "production",
    };
    await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/", {
        method: "HEAD",
        headers: { "If-None-Match": '"abc"', Range: "bytes=0-0" },
      }),
      env,
    );
    expect(captured?.url).toBe("https://docs.vyos.io/en/rolling/index.html");
    expect(captured?.method).toBe("HEAD");
    expect(captured?.headers.get("If-None-Match")).toBe('"abc"');
    expect(captured?.headers.get("Range")).toBe("bytes=0-0");
  });
});

describe("asset cache-class classification (§3.3, extended)", () => {
  it("images, fonts, and the /_images/ + /_static/ trees get the asset class", () => {
    for (const p of [
      "/en/rolling/_images/diagram.png",
      "/en/rolling/_static/fonts/roboto.woff2",
      "/en/rolling/logo.svg",
      "/en/rolling/photo.jpeg",
      "/en/rolling/hero.webp",               // webp added to ASSET_EXT_RE (standalone path)
      "/en/rolling/font.otf",                // otf added to ASSET_EXT_RE (standalone path)
      "/en/rolling/icon.ico",
      "/en/rolling/vyos-documentation.pdf",
      "/en/rolling/vyos-documentation.PDF",  // .pdf folded into the case-insensitive regex
    ]) {
      expect(classifyPath(p)).toBe("asset");
    }
  });
  it("HTML pages and data files stay the page class", () => {
    for (const p of [
      "/en/rolling/index.html",
      "/en/rolling/cli.html",
      "/en/rolling/versions.json",
      "/en/rolling/sitemap.xml",
    ]) {
      expect(classifyPath(p)).toBe("page");
    }
  });
});

describe("wrangler config congruence — html_handling pinned to \"none\"", () => {
  // Unit tests mock ASSETS and never exercise the real wrangler html_handling config; this
  // raw-string assertion is the unit-level pin against a silent revert to
  // "auto-trailing-slash" (which reintroduces the 307-on-explicit-.html smoke failure). The
  // deploy-time smoke gate (scripts/docs_gates/smoke.py) is the runtime-level backstop.
  it("all four branch wrangler envs set html_handling \"none\"", () => {
    for (const raw of [wranglerRolling, wranglerV15, wranglerV14, wranglerLegacy]) {
      expect(raw).toContain('"html_handling": "none"');
      expect(raw).not.toContain("auto-trailing-slash");
    }
  });
});
