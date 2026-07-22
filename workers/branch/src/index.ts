export interface Env {
  ASSETS: Fetcher;                 // static assets binding
  DOCS_BUILD_SHA: string;          // injected at deploy
  DOCS_ENV: "production" | "canary";
}

export type CacheClass = "page" | "asset";

// Binary/media asset extensions (case-insensitive, so ".PDF" also matches) get the longer
// asset cache class, alongside the Sphinx /_static/ (theme) + /_images/ (figure) trees.
const ASSET_EXT_RE = /\.(pdf|png|jpe?g|webp|svg|gif|ico|woff2?|ttf|otf|eot)$/i;

export function classifyPath(path: string): CacheClass {
  if (
    path.includes("/_static/") ||
    path.includes("/_images/") ||
    ASSET_EXT_RE.test(path)
  )
    return "asset";
  return "page"; // HTML, versions.json, sitemaps, robots/llms, pagefind index
}

export function cacheHeaderFor(cls: CacheClass): string {
  return cls === "asset"
    ? "public, max-age=300, s-maxage=600, must-revalidate"
    : "public, max-age=0, s-maxage=300, must-revalidate";
}

export function withDocsHeaders(
  resp: Response,
  path: string,
  env: Pick<Env, "DOCS_BUILD_SHA" | "DOCS_ENV">,
): Response {
  const out = new Response(resp.body, resp);
  out.headers.set("X-Docs-Build", env.DOCS_BUILD_SHA);
  out.headers.set(
    "Cache-Control",
    // Error responses (4xx/5xx) must never carry the page/asset cache class — a
    // cached 404 would poison the edge for the full s-maxage window.
    env.DOCS_ENV === "canary" || out.status >= 400
      ? "no-store"
      : cacheHeaderFor(classifyPath(path)),
  );
  return out;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    // With assets html_handling "none", the runtime serves explicit .html URLs directly
    // but does NOT map a directory URL ("/foo/") to its index.html — the worker must map
    // trailing-slash URLs to index.html itself to preserve ReadTheDocs URL parity.
    if (url.pathname.endsWith("/")) {
      const mapped = new URL(url);
      mapped.pathname = url.pathname + "index.html";
      const resp = await env.ASSETS.fetch(new Request(mapped, request));
      return withDocsHeaders(resp, url.pathname, env);
    }
    // Bare extensionless path (no trailing slash, no "." in the last segment): it may be a
    // real directory whose slashed form RTD 301-redirects to ("/foo" → "/foo/"), or a
    // file-like path with no matching asset (e.g. "/cli", whose real asset is "cli.html")
    // that RTD 404s. A dot heuristic can't separate them, so probe the assets binding for
    // "<path>/index.html": 200 → 301 to the slashed form; anything else → fall through to
    // the exact-path fetch (404 for "/cli", matching live RTD).
    const lastSegment = url.pathname.slice(url.pathname.lastIndexOf("/") + 1);
    if (lastSegment !== "" && !lastSegment.includes(".")) {
      const probe = new URL(url);
      probe.pathname = url.pathname + "/index.html";
      const probeResp = await env.ASSETS.fetch(new Request(probe, { method: "GET" }));
      probeResp.body?.cancel(); // existence check only — release the probe body stream
      if (probeResp.status === 200) {
        const location = url.pathname + "/" + url.search; // preserve query; no fragment
        return withDocsHeaders(
          new Response(null, { status: 301, headers: { Location: location } }),
          url.pathname,
          env,
        );
      }
    }
    const resp = await env.ASSETS.fetch(request);
    return withDocsHeaders(resp, url.pathname, env);
  },
} satisfies ExportedHandler<Env>;
