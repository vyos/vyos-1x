import raw from "../../versions.json";

export interface VersionEntry {
  slug: string; label: string;
  status: "dev" | "lts" | "eol";
  binding: string; aliases: string[];
  pdf: string | null;
  // R2 object key for the apex PDF fallback (spec §5) — set only on versions whose PDF
  // exceeds the 25 MiB static-asset cap and is therefore absent from the content
  // Worker's own asset tree (currently just 1.3). Optional; most versions omit it.
  pdf_r2_key?: string;
}
export interface Manifest {
  schema_version: number;
  default_lang: string; default_version: string;
  languages: { code: string; label: string }[];
  versions: VersionEntry[];
}

// Split out from loadManifest() so tests can validate synthetic manifests without
// touching the real ../../versions.json import (which loadManifest() is hardwired to).
export function validateManifest(m: Manifest): Manifest {
  if (m.schema_version !== 2) throw new Error(`versions.json schema_version ${m.schema_version} != 2`);
  const slugs = new Set<string>();
  for (const v of m.versions) {
    if (!/^DOCS_[A-Z0-9_]+$/.test(v.binding)) throw new Error(`bad binding for ${v.slug}`);
    if (!["dev", "lts", "eol"].includes(v.status)) throw new Error(`bad status for ${v.slug}`);
    if (slugs.has(v.slug)) throw new Error(`duplicate slug: ${v.slug}`);
    // pdf_r2_key names an R2 fallback for the exact `pdf` URL — a null pdf has no URL
    // for the fallback to ever be reached at, so the pairing is nonsensical.
    if (v.pdf_r2_key && v.pdf === null) throw new Error(`pdf_r2_key set but pdf is null for ${v.slug}`);
    slugs.add(v.slug);
  }
  // Separate pass: an alias must not collide with ANY canonical slug (not just an
  // earlier one), so `slugs` must be fully populated before this check runs.
  const aliases = new Set<string>();
  for (const v of m.versions) {
    for (const alias of v.aliases) {
      if (slugs.has(alias)) throw new Error(`alias ${alias} (on ${v.slug}) collides with a canonical slug`);
      if (aliases.has(alias)) throw new Error(`duplicate alias: ${alias}`);
      aliases.add(alias);
    }
  }
  if (!m.versions.some((v) => v.slug === m.default_version))
    throw new Error(`default_version ${m.default_version} not in versions[]`);
  return m;
}

export function loadManifest(): Manifest {
  return validateManifest(raw as Manifest);
}

export function buildDispatch(m: Manifest): Map<string, string> {
  return new Map(m.versions.map((v) => [v.slug, v.binding]));
}
