export function resolveVersion(
  pathname: string,
  dispatch: Map<string, string>,
): { slug: string; binding: string } | null {
  const m = pathname.match(/^\/en\/([^/]+)\//);
  if (!m) return null;
  const binding = dispatch.get(m[1]);
  return binding ? { slug: m[1], binding } : null;
}

export function bindingGuard(env: Record<string, unknown>, binding: string): Fetcher | null {
  const b = env[binding];
  if (b && typeof (b as Fetcher).fetch === "function") return b as Fetcher;
  return null;
}
