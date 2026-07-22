import { describe, it, expect } from "vitest";
import worker, { classifyPath, cacheHeaderFor, withDocsHeaders, type Env } from "../src/index";

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
  // Assets binding stub emulating html_handling:"none": exact-path lookups only —
  // no extension inference and no directory auto-index. A bare "/foo/" therefore only
  // resolves because the worker rewrites it to "/foo/index.html" before this runs, which
  // is exactly the RTD-parity behavior under test.
  const ASSET_MAP: Record<string, string> = {
    "/en/rolling/index.html": "<html>root index</html>",
    "/en/rolling/cli.html": "<html>cli page</html>",
    "/en/rolling/guide/index.html": "<html>guide index</html>",
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

  it("extensionless page path (no trailing slash) is not mapped → 404", async () => {
    const seen: string[] = [];
    const resp = await worker.fetch(
      new Request("https://docs.vyos.io/en/rolling/cli"),
      makeAssetsEnv("production", seen),
    );
    expect(resp.status).toBe(404);
    // passed through unmodified; html_handling:"none" does not infer ".html"
    expect(seen).toEqual(["https://docs.vyos.io/en/rolling/cli"]);
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
});
