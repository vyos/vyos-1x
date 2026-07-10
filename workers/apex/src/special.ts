import type { Manifest } from "./manifest";
import { bindingGuard } from "./dispatch";

// Static assets (404.html, 503.html, robots.txt, favicons, root) live in the apex
// ASSETS binding; versions.json is served from the imported manifest so the body
// always matches the dispatch map.
export async function specialPathFor(
  request: Request,
  m: Manifest,
  env: Record<string, unknown> & { ASSETS: Fetcher },
): Promise<Response | null> {
  const url = new URL(request.url);
  const p = url.pathname;

  if (p === "/") // default-version redirect (§3.2.2) — query preserved, like alias redirects
    return new Response(null, { status: 301, headers: { Location: `/en/${m.default_version}/${url.search}` } });

  if (p === "/versions.json")
    return new Response(JSON.stringify(m), {
      headers: { "content-type": "application/json; charset=utf-8" },
    });

  if (p === "/healthz")
    return new Response(JSON.stringify({ status: "ok", versions: m.versions.length }), {
      headers: { "content-type": "application/json" },
    });

  if (p === "/sitemap.xml") {
    const entries = m.versions
      .map((v) => `<sitemap><loc>https://docs.vyos.io/en/${v.slug}/sitemap.xml</loc></sitemap>`)
      .join("");
    return new Response(
      `<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${entries}</sitemapindex>`,
      { headers: { "content-type": "application/xml" } },
    );
  }

  if (p === "/llms.txt") { // direct body, not a redirect (§3.2.2)
    const def = m.versions.find((v) => v.slug === m.default_version)!;
    const b = bindingGuard(env, def.binding);
    if (!b) // do NOT fall through — /llms.txt with a missing binding is a 503, not a 404
      return new Response("service unavailable", { status: 503, headers: { "content-type": "text/plain" } });
    // Forward the ORIGINAL request (method + conditional-GET headers), just retargeted
    // to the versioned path — mirrors the robots.txt/favicon pass-through below.
    const target = new URL(`/en/${def.slug}/llms.txt`, url);
    return b.fetch(new Request(target, request));
  }

  if (p === "/robots.txt" || p === "/favicon.ico" || /^\/apple-touch-icon.*\.png$/.test(p))
    // Pass the ORIGINAL request through (not a re-synthesized `new Request(url)`) so
    // conditional-GET headers (If-None-Match / If-Modified-Since) reach ASSETS intact.
    return env.ASSETS.fetch(request);

  return null;
}
