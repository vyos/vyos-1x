export interface Env { PREVIEWS: R2Bucket }

const MIME: Record<string, string> = {
  html: "text/html; charset=utf-8", css: "text/css", js: "text/javascript",
  json: "application/json", svg: "image/svg+xml", png: "image/png", jpg: "image/jpeg",
  gif: "image/gif", ico: "image/x-icon", txt: "text/plain; charset=utf-8",
  xml: "application/xml", pdf: "application/pdf", woff2: "font/woff2", woff: "font/woff",
};

export function mimeFor(key: string): string {
  const ext = key.split(".").pop() ?? "";
  return MIME[ext] ?? "application/octet-stream";
}

export function keyFor(pathname: string): string {
  let key = pathname.replace(/^\//, "");
  if (key.endsWith("/") || key === "" ) key += "index.html";
  return key;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const key = keyFor(new URL(request.url).pathname);
    let obj: R2ObjectBody | null = null;
    let resolvedKey = key;
    try {
      obj = await env.PREVIEWS.get(key);
      if (!obj && !key.split("/").pop()?.includes(".")) {
        // Extensionless directory URL with no trailing slash (e.g. /en/rolling/cli) —
        // keyFor() only appends index.html for trailing-slash/empty paths, so probe the
        // directory's index.html before 404ing. Check the LAST path segment only — a dot
        // anywhere earlier (e.g. version segment "1.4" in /pr-42/en/1.4/cli) must not skip
        // the probe for an otherwise-extensionless final segment.
        resolvedKey = `${key}/index.html`;
        obj = await env.PREVIEWS.get(resolvedKey);
      }
    } catch {
      // Transient R2/binding error on either probe — fail closed with a controlled 503
      // instead of letting an unhandled exception surface as a raw worker error.
      return new Response("preview temporarily unavailable", {
        status: 503,
        headers: { "X-Robots-Tag": "noindex", "Cache-Control": "no-store" },
      });
    }
    if (!obj) {
      return new Response("preview not found", {
        status: 404,
        // no-store on the 404 too — a cached 404 would persist past the preview upload
        headers: { "X-Robots-Tag": "noindex", "Cache-Control": "no-store" },
      });
    }
    return new Response(obj.body, {
      headers: {
        "content-type": obj.httpMetadata?.contentType ?? mimeFor(resolvedKey),
        "X-Robots-Tag": "noindex",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
} satisfies ExportedHandler<Env>;
