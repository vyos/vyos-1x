"""Scoped pre-traffic smoke + post-promote probe (spec §7.1 steps 2/5).

Probes ONE version's pages plus apex special paths through a host, presenting a
CF Access service token. Header contract (§3.3): content probes assert
X-Docs-Build == --expect-sha; apex probes assert X-Apex-Build presence only.

Phase-2 obligation (authorized addition, not in the original spec text): the
version's index.html probe also asserts the response body carries the
`#vyos-search` mount div (docs/_templates/searchbox.html), guarding the
Pagefind gate's silent-degrade failure mode — a build that forgot to set
DOCS_VERSION_SLUG would otherwise ship stock RTD search without CI noticing.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import urllib.request

APEX_PATHS = ["/versions.json", "/healthz", "/robots.txt", "/sitemap.xml"]
SEARCH_MOUNT_MARKER = 'id="vyos-search"'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Probes assert an EXACT status per-path (200 or 404) — following a 3xx would
    silently swap the probed status for whatever the redirect target returns,
    masking an accidental redirect where a direct 200/404 was expected. Mirrors
    parity.py's _NoRedirect/_OPENER pattern."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


@dataclasses.dataclass
class Probe:
    path: str
    expect_status: int
    assert_docs_build: bool
    assert_apex_build: bool
    assert_search_mount: bool = False


def probe_plan(slug: str, pdf: str | None, critical: list[str]) -> list[Probe]:
    plan = [Probe(f"/en/{slug}/{rel}", 200, True, False) for rel in ["index.html", *critical]]
    plan.append(Probe(f"/en/{slug}/pagefind/pagefind.js", 200, True, False))
    if pdf:
        plan.append(Probe(pdf, 200, True, False))
    plan.append(Probe(f"/en/{slug}/definitely-missing-page-xyz.html", 404, False, False))
    plan += [Probe(p, 200, False, True) for p in APEX_PATHS]
    plan[0].assert_search_mount = True  # plan[0] is always /en/<slug>/index.html
    return plan


def docs_build_ok(header_value: str | None, expect_sha: str) -> bool:
    """SKIP sentinel (nightly sweep): header presence only; otherwise exact match."""
    if expect_sha == "SKIP":
        return header_value is not None
    return header_value == expect_sha


def search_mount_present(html: str) -> bool:
    return SEARCH_MOUNT_MARKER in html


def run(host: str, slug: str, expect_sha: str, access_id: str, access_secret: str,
        pdf: str | None, critical: list[str]) -> int:
    failures = 0
    for probe in probe_plan(slug, pdf, critical):
        req = urllib.request.Request(f"https://{host}{probe.path}", method="GET")
        req.add_header("CF-Access-Client-Id", access_id)
        req.add_header("CF-Access-Client-Secret", access_secret)
        try:
            with _OPENER.open(req, timeout=30) as resp:
                status, headers, body = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:  # non-2xx still carries headers
            status, headers, body = e.code, e.headers, e.read()
        except Exception as e:  # noqa: BLE001 — any transport error fails the probe
            print(f"SMOKE-FAIL {probe.path}: {e}", file=sys.stderr)
            failures += 1
            continue
        ok = status == probe.expect_status
        if probe.assert_docs_build and not docs_build_ok(headers.get("X-Docs-Build"), expect_sha):
            ok = False
        if probe.assert_apex_build and not headers.get("X-Apex-Build"):
            ok = False
        if probe.assert_search_mount and not search_mount_present(
                body.decode("utf-8", errors="replace")):
            ok = False
        if not ok:
            print(f"SMOKE-FAIL {probe.path}: status={status} "
                  f"docs-build={headers.get('X-Docs-Build')}", file=sys.stderr)
            failures += 1
    print(json.dumps({"failures": failures}))
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--expect-sha", required=True)
    ap.add_argument("--access-id", required=True)
    ap.add_argument("--access-secret", required=True)
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--critical-list", default="scripts/docs_gates/critical-pages.txt")
    a = ap.parse_args()
    critical = [line.strip() for line in open(a.critical_list).read().splitlines()
                if line.strip() and not line.startswith("#")]
    return run(a.host, a.slug, a.expect_sha, a.access_id, a.access_secret, a.pdf, critical)


if __name__ == "__main__":
    raise SystemExit(main())
