import type { Manifest } from "./manifest";

function aliasMap(m: Manifest): Map<string, string> {
  const map = new Map<string, string>();
  for (const v of m.versions) for (const a of v.aliases) map.set(a, v.slug);
  return map;
}

function r301(pathAndQuery: string): Response {
  return new Response(null, { status: 301, headers: { Location: pathAndQuery } });
}

export function redirectFor(url: URL, m: Manifest): Response | null {
  const { pathname, search } = url; // never touch url.hash — fragments don't reach the server

  // RTD PDF URLs: /_/downloads/en/<ver>/pdf/*  →  /en/<slug>/vyos-documentation.pdf
  const pdf = pathname.match(/^\/_\/downloads\/en\/([^/]+)\/pdf(?:\/|$)/);
  if (pdf) {
    const slug = aliasMap(m).get(pdf[1]) ?? pdf[1];
    const entry = m.versions.find((v) => v.slug === slug);
    // pdf: null means no PDF artifact exists for this version — don't 301 into a dead-end 404.
    // The manifest's pdf value is the source of truth (not a hardcoded filename) so a future
    // R2-fallback path for 1.3 (or any other version) can move the target without a code change.
    if (entry && entry.pdf !== null) return r301(`${entry.pdf}${search}`);
  }

  // Alias / codename prefixes: /en/<alias>/*  →  /en/<slug>/*
  const seg = pathname.match(/^\/en\/([^/]+)(\/.*)?$/);
  if (seg) {
    const [, first, rest = ""] = seg;
    const target = aliasMap(m).get(first);
    if (target) return r301(`/en/${target}${rest || "/"}${search}`);
    // Trailing-slash normalization on bare version roots: /en/<slug> → /en/<slug>/
    if (rest === "" && m.versions.some((v) => v.slug === first))
      return r301(`/en/${first}/${search}`);
  }
  return null;
}
