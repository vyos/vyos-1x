"""URL-parity corpus + alias assertions (spec §11).

Modes:
  --sitemap-host X   pull per-version sitemaps from X (RTD pre-cutover)
  --probe-host Y     probe every URL on Y (canary via Access, or production)
Fails (exit 1) on any status mismatch (non-200 for corpus rows; wrong
Location for alias rows).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>")

# Sitemap sweep covers only the versions THIS repo builds on CF (rolling/1.5/1.4).
# 1.3/1.2 have NO RTD sitemaps (spec §15a.5) — their parity is the legacy snapshot
# repo's crawl-inventory job. Their alias/PDF redirect rows below stay in scope.
DEFAULT_SLUGS = "rolling,1.5,1.4"

ALIASES = [("latest", "rolling"), ("stable", "1.5"), ("lts", "1.5"),
           ("circinus", "1.5"), ("sagitta", "1.4"), ("equuleus", "1.3"), ("crux", "1.2")]


def urls_from_sitemap(xml: str) -> list[str]:
    out = []
    for loc in SITEMAP_LOC.findall(xml):
        path = re.sub(r"^https?://[^/]+", "", loc)
        if path.startswith("/en/"):
            out.append(path)
    return out


def alias_corpus() -> list[tuple[str, int, str]]:
    rows = [(f"/en/{a}/", 301, f"/en/{s}/") for a, s in ALIASES]
    # 1.2 excluded: never had an RTD PDF artifact (Phase-0 finding, spec §15a) — pdf: null
    rows += [(f"/_/downloads/en/{s}/pdf/", 301, f"/en/{s}/vyos-documentation.pdf")
             for s in ["rolling", "1.5", "1.4", "1.3"]]
    rows.append(("/_/downloads/en/latest/pdf/", 301, "/en/rolling/vyos-documentation.pdf"))
    return rows


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The parity checker must SEE 301s, not follow them (alias assertions)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

# Overridable in tests (monkeypatched to "http") so fetch() can be exercised end-to-end
# against a real local http.server instead of requiring TLS for a unit test.
_SCHEME = "https"


def fetch(host: str, path: str, access: tuple[str, str] | None, method: str = "HEAD"):
    req = urllib.request.Request(f"{_SCHEME}://{host}{path}", method=method)
    if access:
        req.add_header("CF-Access-Client-Id", access[0])
        req.add_header("CF-Access-Client-Secret", access[1])
    try:
        with _OPENER.open(req, timeout=30) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:  # 3xx land here with the no-redirect handler
        return e.code, e.headers.get("Location")
    except Exception:  # noqa: BLE001 — DNS blip/timeout fails THIS probe, not the run
        return 0, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap-host", required=True)
    ap.add_argument("--probe-host", required=True)
    ap.add_argument("--slugs", default=DEFAULT_SLUGS)
    ap.add_argument("--access-id")
    ap.add_argument("--access-secret")
    ap.add_argument("--report", type=Path, default=Path("parity-report.json"))
    a = ap.parse_args()
    access = (a.access_id, a.access_secret) if a.access_id else None
    failures: list[dict] = []
    checked = 0

    for slug in a.slugs.split(","):
        status, _ = fetch(a.sitemap_host, f"/en/{slug}/sitemap.xml", None, "GET")
        if status != 200:
            failures.append({"path": f"/en/{slug}/sitemap.xml", "reason": f"sitemap {status}"})
            continue
        try:
            with urllib.request.urlopen(f"https://{a.sitemap_host}/en/{slug}/sitemap.xml",
                                        timeout=30) as r:
                urls = urls_from_sitemap(r.read().decode())
        except Exception as e:  # noqa: BLE001 — record per-slug, keep sweeping; report ALWAYS written
            failures.append({"path": f"/en/{slug}/sitemap.xml",
                             "reason": f"sitemap fetch error: {e}"})
            continue
        for path in urls:
            checked += 1
            st, _ = fetch(a.probe_host, path, access)
            if st != 200:
                failures.append({"path": path, "reason": f"status {st}"})

    for path, want_status, want_loc in alias_corpus():
        checked += 1
        st, loc = fetch(a.probe_host, path, access)
        if st != want_status or (loc or "") != want_loc:
            failures.append({"path": path, "reason": f"got {st} → {loc}, want {want_status} → {want_loc}"})

    a.report.write_text(json.dumps({"checked": checked, "failures": failures}, indent=2))
    for f in failures:
        print(f"PARITY-FAIL {f['path']}: {f['reason']}", file=sys.stderr)
    print(f"checked={checked} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
