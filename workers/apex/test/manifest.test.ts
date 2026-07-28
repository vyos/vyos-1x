import { describe, it, expect } from "vitest";
import { loadManifest, buildDispatch, validateManifest, type Manifest } from "../src/manifest";
// The workers pool has no real filesystem (node:fs readFileSync is an unimplemented
// stub — see @cloudflare/vitest-pool-workers/dist/worker/lib/node/fs.mjs); import the
// config as a Vite `?raw` asset instead so the file content is inlined at bundle time.
// eslint-disable-next-line import/no-unresolved
import wranglerJsonc from "../wrangler.jsonc?raw";
// eslint-disable-next-line import/no-unresolved
import rootHtml from "../assets/root.html?raw";

describe("versions.json v2 manifest (§3.4)", () => {
  it("loads and validates schema_version 2 with 5 versions", () => {
    const m = loadManifest();
    expect(m.schema_version).toBe(2);
    expect(m.versions).toHaveLength(5);
    expect(m.default_version).toBe("rolling");
  });
  it("every version carries a binding; statuses in dev|lts|eol", () => {
    const m = loadManifest();
    for (const v of m.versions) {
      expect(v.binding).toMatch(/^DOCS_[A-Z0-9_]+$/);
      expect(["dev", "lts", "eol"]).toContain(v.status);
    }
  });
  it("dispatch map: every version slug maps to its binding (shared legacy included)", () => {
    const m = loadManifest();
    const d = buildDispatch(m);
    expect(d.size).toBe(m.versions.length);
    for (const v of m.versions) {
      expect(d.get(v.slug)).toBe(v.binding);
    }
    // aliases are redirect-layer concerns, never dispatch keys
    for (const v of m.versions) {
      for (const a of v.aliases) {
        expect(d.has(a)).toBe(false);
      }
    }
  });
  it("only 1.3 carries pdf_r2_key (§5 apex PDF R2 fallback)", () => {
    const m = loadManifest();
    const withKey = m.versions.filter((v) => v.pdf_r2_key);
    expect(withKey).toHaveLength(1);
    expect(withKey[0]).toMatchObject({
      slug: "1.3",
      pdf: "/en/1.3/vyos-documentation.pdf",
      pdf_r2_key: "legacy/1.3/vyos-documentation.pdf",
    });
  });
});

function baseManifest(): Manifest {
  return {
    schema_version: 2,
    default_lang: "en",
    default_version: "rolling",
    languages: [{ code: "en", label: "English" }],
    versions: [
      { slug: "rolling", label: "Rolling", status: "dev", binding: "DOCS_ROLLING",
        aliases: ["latest"], pdf: null },
      { slug: "1.5", label: "1.5", status: "lts", binding: "DOCS_V15",
        aliases: ["stable", "lts"], pdf: null },
    ],
  };
}

describe("validateManifest — duplicate/ambiguous slug + alias rejection", () => {
  it("rejects a duplicate slug", () => {
    const m = baseManifest();
    m.versions.push({ ...m.versions[0], binding: "DOCS_ROLLING2" });
    expect(() => validateManifest(m)).toThrow(/duplicate slug: rolling/);
  });

  it("rejects a duplicate alias across two versions", () => {
    const m = baseManifest();
    m.versions[1].aliases.push("latest"); // "latest" already aliases rolling
    expect(() => validateManifest(m)).toThrow(/duplicate alias: latest/);
  });

  it("rejects an alias that collides with a canonical slug", () => {
    const m = baseManifest();
    m.versions[0].aliases.push("1.5"); // "1.5" is a real slug
    expect(() => validateManifest(m)).toThrow(/alias 1\.5 .* collides with a canonical slug/);
  });

  it("accepts a well-formed manifest unchanged", () => {
    const m = baseManifest();
    const snapshot = structuredClone(m);
    expect(validateManifest(m)).toBe(m);
    expect(m).toEqual(snapshot); // validation must not mutate the manifest
  });

  it("accepts pdf_r2_key when pdf is set", () => {
    const m = baseManifest();
    m.versions[1].pdf = "/en/1.5/vyos-documentation.pdf";
    m.versions[1].pdf_r2_key = "legacy/1.5/vyos-documentation.pdf";
    expect(validateManifest(m)).toBe(m);
  });

  it("rejects pdf_r2_key set on a version whose pdf is null (no URL for the fallback to be reached at)", () => {
    const m = baseManifest();
    m.versions[0].pdf_r2_key = "legacy/rolling/vyos-documentation.pdf"; // pdf stays null
    expect(() => validateManifest(m)).toThrow(/pdf_r2_key set but pdf is null for rolling/);
  });
});

it("every versions.json binding exists in BOTH apex wrangler envs (§3.4 gate a)", () => {
  const raw = wranglerJsonc.replace(/\/\/.*$/gm, ""); // strip line comments
  const cfg = JSON.parse(raw);
  const bindings = new Set(buildDispatch(loadManifest()).values());
  for (const envName of ["canary", "production"]) {
    const services = new Set((cfg.env[envName].services as { binding: string }[]).map((s) => s.binding));
    for (const b of bindings) expect(services, `${envName} missing ${b}`).toContain(b);
  }
});

it("root.html's hardcoded default-version references stay congruent with the manifest", () => {
  // root.html is a static fallback shell (never templated at build time — see the
  // comment in the file) so its `/en/<slug>/` references must be hand-kept in sync
  // with the manifest's default_version. This is the drift guard: it fails loudly if
  // someone bumps default_version without also updating the static asset.
  const expected = `/en/${loadManifest().default_version}/`;
  // Strip HTML comments first — the explanatory comment in root.html mentions the
  // literal placeholder text "/en/<default_version>/", which is documentation, not
  // a real markup reference, and must not be asserted against the manifest.
  // Applied repeatedly to a fixpoint: a single pass can splice two partial comments
  // into a new one (CodeQL js/incomplete-multi-character-sanitization).
  let withoutComments = rootHtml;
  for (let prev = ""; prev !== withoutComments; ) {
    prev = withoutComments;
    withoutComments = withoutComments.replace(/<!--[\s\S]*?-->/g, "");
  }
  const refs = withoutComments.match(/\/en\/[^/"'\s]+\//g) ?? [];
  expect(refs.length).toBeGreaterThan(0);
  for (const ref of refs) expect(ref).toBe(expected);
});
