export interface UaPolicy {
  allow: string[];
  log: string[];
  block: string[];
}

export type UaVerdict = "allow" | "block" | "log";

export function uaVerdict(ua: string, policy: UaPolicy): UaVerdict {
  const hit = (list: string[]) => list.some((n) => ua.toLowerCase().includes(n.toLowerCase()));
  // Explicit blocks take precedence — a request-controlled UA string that spoofs an
  // allow-listed substring (e.g. "Googlebot EvilScraper") must not be able to bypass a
  // block entry just by also matching the allow list.
  if (hit(policy.block)) return "block";
  if (hit(policy.allow)) return "allow";
  if (hit(policy.log)) return "log";
  return "allow"; // fail-open default
}
