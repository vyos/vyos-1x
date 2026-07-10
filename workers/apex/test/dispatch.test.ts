import { describe, it, expect } from "vitest";
import { loadManifest, buildDispatch } from "../src/manifest";
import { resolveVersion, bindingGuard } from "../src/dispatch";

const dispatch = buildDispatch(loadManifest());

describe("version dispatch (§3.2.6)", () => {
  it("resolves /en/<slug>/... to its binding, path untouched", () => {
    expect(resolveVersion("/en/rolling/cli/index.html", dispatch))
      .toEqual({ slug: "rolling", binding: "DOCS_ROLLING" });
    expect(resolveVersion("/en/1.5/", dispatch))
      .toEqual({ slug: "1.5", binding: "DOCS_V15" });
  });
  it("returns null for unknown version or non-version paths", () => {
    expect(resolveVersion("/en/9.9/x", dispatch)).toBeNull();
    expect(resolveVersion("/kb/article", dispatch)).toBeNull();
  });
});

describe("runtime binding guard (§3.2.7)", () => {
  it("returns the fetcher when binding exists", () => {
    const fake = { fetch: async () => new Response("ok") };
    expect(bindingGuard({ DOCS_ROLLING: fake } as never, "DOCS_ROLLING")).toBe(fake);
  });
  it("returns null (→ themed 503) when binding missing or not a Fetcher", () => {
    expect(bindingGuard({} as never, "DOCS_ROLLING")).toBeNull();
    expect(bindingGuard({ DOCS_ROLLING: 42 } as never, "DOCS_ROLLING")).toBeNull();
  });
});
