import { describe, it, expect } from "vitest";
import { loadManifest } from "../src/manifest";
import { redirectFor } from "../src/redirects";

const m = loadManifest();
const loc = (u: string) => {
  const r = redirectFor(new URL(u), m);
  return r ? { status: r.status, location: r.headers.get("Location") } : null;
};

describe("alias + codename 301s (§3.2.4)", () => {
  it("maps every alias, preserving path + query", () => {
    expect(loc("https://docs.vyos.io/en/latest/cli/index.html?x=1"))
      .toEqual({ status: 301, location: "/en/rolling/cli/index.html?x=1" });
    expect(loc("https://docs.vyos.io/en/stable/")).toEqual({ status: 301, location: "/en/1.5/" });
    expect(loc("https://docs.vyos.io/en/lts/a")).toEqual({ status: 301, location: "/en/1.5/a" });
    expect(loc("https://docs.vyos.io/en/circinus/a")).toEqual({ status: 301, location: "/en/1.5/a" });
    expect(loc("https://docs.vyos.io/en/sagitta/a")).toEqual({ status: 301, location: "/en/1.4/a" });
    expect(loc("https://docs.vyos.io/en/equuleus/a")).toEqual({ status: 301, location: "/en/1.3/a" });
    expect(loc("https://docs.vyos.io/en/crux/a")).toEqual({ status: 301, location: "/en/1.2/a" });
  });
  it("RTD PDF URLs → PDF path taken from the manifest (source of truth, §3.4)", () => {
    const v15pdf = m.versions.find((v) => v.slug === "1.5")!.pdf;
    const rollingPdf = m.versions.find((v) => v.slug === "rolling")!.pdf;
    expect(loc("https://docs.vyos.io/_/downloads/en/1.5/pdf/"))
      .toEqual({ status: 301, location: v15pdf });
    expect(loc("https://docs.vyos.io/_/downloads/en/latest/pdf/"))
      .toEqual({ status: 301, location: rollingPdf });
  });
  it("RTD PDF URLs for a pdf:null version → no redirect (no dead-end 301)", () => {
    expect(loc("https://docs.vyos.io/_/downloads/en/crux/pdf/")).toBeNull();
    expect(loc("https://docs.vyos.io/_/downloads/en/1.2/pdf/")).toBeNull();
  });
  it("RTD PDF URLs preserve the query string, appended to the manifest's pdf value", () => {
    const v14pdf = m.versions.find((v) => v.slug === "1.4")!.pdf;
    expect(loc("https://docs.vyos.io/_/downloads/en/sagitta/pdf/?x=1"))
      .toEqual({ status: 301, location: `${v14pdf}?x=1` });
  });
  it("does not match /pdf-notes (only an exact /pdf segment)", () => {
    expect(loc("https://docs.vyos.io/_/downloads/en/rolling/pdf-notes")).toBeNull();
  });
  it("trailing-slash normalization on bare version roots (§3.2.3)", () => {
    expect(loc("https://docs.vyos.io/en/1.5")).toEqual({ status: 301, location: "/en/1.5/" });
    expect(loc("https://docs.vyos.io/en/rolling?q=1")).toEqual({ status: 301, location: "/en/rolling/?q=1" });
  });
  it("never emits a fragment in Location (§3.2.6)", () => {
    const r = loc("https://docs.vyos.io/en/latest/page.html#section");
    expect(r!.location).not.toContain("#");
  });
  it("returns null for canonical paths (no redirect loop)", () => {
    expect(loc("https://docs.vyos.io/en/rolling/")).toBeNull();
    expect(loc("https://docs.vyos.io/en/1.5/cli/")).toBeNull();
  });
});
