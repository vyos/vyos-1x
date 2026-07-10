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
