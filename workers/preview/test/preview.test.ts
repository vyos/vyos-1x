import { describe, it, expect } from "vitest";
import worker, { mimeFor, keyFor } from "../src/index";
import type { Env } from "../src/index";

describe("preview worker helpers (§10)", () => {
  it("derives R2 key from path, defaulting directory to index.html", () => {
    expect(keyFor("/pr-42/en/rolling/")).toBe("pr-42/en/rolling/index.html");
    expect(keyFor("/pr-42/en/rolling/cli/index.html")).toBe("pr-42/en/rolling/cli/index.html");
  });
  it("extension→MIME fallback map (nosniff-safe)", () => {
    expect(mimeFor("a.html")).toBe("text/html; charset=utf-8");
    expect(mimeFor("a.css")).toBe("text/css");
    expect(mimeFor("a.js")).toBe("text/javascript");
    expect(mimeFor("a.json")).toBe("application/json");
    expect(mimeFor("a.svg")).toBe("image/svg+xml");
    expect(mimeFor("a.woff2")).toBe("font/woff2");
    expect(mimeFor("a.unknown")).toBe("application/octet-stream");
  });
});

// Fake R2Bucket mock following the makeEnv() precedent in apex/test/router.test.ts —
// only the `get` surface the handler consumes; miniflare's real R2 not needed here.
function makeEnv(objects: Record<string, { body: string; contentType?: string }>): Env {
  return {
    PREVIEWS: {
      get: async (key: string) => {
        const hit = objects[key];
        if (!hit) return null;
        return {
          body: hit.body,
          httpMetadata: hit.contentType ? { contentType: hit.contentType } : undefined,
        };
      },
    } as unknown as R2Bucket,
  };
}

const get = (path: string, env: Env) =>
  worker.fetch(new Request(`https://docs-preview.vyos.io${path}`), env);

describe("preview worker fetch entrypoint (§10)", () => {
  it("serves a found object with uploader contentType + noindex/no-store/nosniff headers", async () => {
    const env = makeEnv({
      "pr-42/en/rolling/index.html": { body: "<h1>preview</h1>", contentType: "text/html; charset=utf-8" },
    });
    const r = await get("/pr-42/en/rolling/", env);
    expect(r.status).toBe(200);
    expect(await r.text()).toBe("<h1>preview</h1>");
    expect(r.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(r.headers.get("X-Robots-Tag")).toBe("noindex");
    expect(r.headers.get("Cache-Control")).toBe("no-store");
    expect(r.headers.get("X-Content-Type-Options")).toBe("nosniff");
  });
  it("missing object → 404 with noindex AND no-store (404s must never be cached)", async () => {
    const r = await get("/pr-42/en/rolling/missing.html", makeEnv({}));
    expect(r.status).toBe(404);
    expect(r.headers.get("X-Robots-Tag")).toBe("noindex");
    expect(r.headers.get("Cache-Control")).toBe("no-store");
  });
  it("object without httpMetadata.contentType falls back to mimeFor(key)", async () => {
    const env = makeEnv({ "pr-42/en/rolling/style.css": { body: "body{}" } });
    const r = await get("/pr-42/en/rolling/style.css", env);
    expect(r.status).toBe(200);
    expect(r.headers.get("content-type")).toBe("text/css");
  });
  it("extensionless directory URL with no trailing slash serves the directory's index.html", async () => {
    const env = makeEnv({
      "pr-42/en/rolling/cli/index.html": { body: "<h1>cli</h1>", contentType: "text/html; charset=utf-8" },
    });
    const r = await get("/pr-42/en/rolling/cli", env);
    expect(r.status).toBe(200);
    expect(await r.text()).toBe("<h1>cli</h1>");
    expect(r.headers.get("content-type")).toBe("text/html; charset=utf-8");
  });
  it("extensionless directory URL with a dotted version segment earlier in the path still probes index.html (dot-check is last-segment-only)", async () => {
    const env = makeEnv({
      "pr-42/en/1.4/cli/index.html": { body: "<h1>cli 1.4</h1>", contentType: "text/html; charset=utf-8" },
    });
    const r = await get("/pr-42/en/1.4/cli", env);
    expect(r.status).toBe(200);
    expect(await r.text()).toBe("<h1>cli 1.4</h1>");
    expect(r.headers.get("content-type")).toBe("text/html; charset=utf-8");
  });
  it("a transient R2/binding error on either probe degrades to a controlled 503 (never an unhandled exception)", async () => {
    const throwingEnv: Env = {
      PREVIEWS: { get: async () => { throw new Error("R2 unavailable"); } } as unknown as R2Bucket,
    };
    const r = await get("/pr-42/en/rolling/cli", throwingEnv);
    expect(r.status).toBe(503);
    expect(r.headers.get("X-Robots-Tag")).toBe("noindex");
    expect(r.headers.get("Cache-Control")).toBe("no-store");
  });
});
