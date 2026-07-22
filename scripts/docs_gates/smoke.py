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
import time
import urllib.request

APEX_PATHS = ["/versions.json", "/healthz", "/robots.txt", "/sitemap.xml"]
SEARCH_MOUNT_MARKER = 'id="vyos-search"'

# Explicit UA so the gate never depends on a Cloudflare edge exemption for the default
# Python-urllib UA. The Browser Integrity Check blocked that UA until a skip rule was added;
# the gate must not silently rely on that rule surviving.
USER_AGENT = "vyos-docs-smoke/1.0 (+https://github.com/vyos/vyos-documentation)"

# Round-based retry (module-level so tests can shrink them). A freshly-deployed worker version
# can lose a propagation race: for a few minutes a probe may be served by the PREVIOUS version
# (wrong status / stale X-Docs-Build). Rather than fail-fast, each round re-probes ONLY the
# still-failing probes — this preserves the full per-probe failure enumeration (diagnostic
# value) while adding at most (MAX_ROUNDS - 1) inter-round sleeps. Envelope widened to 5 rounds
# x 30s after an observed propagation wave outlasted 3 rounds x 20s (a path still stale at
# round 3): 4 x 30s = 2 min now covers the observed 1-2+ min waves. The green path still costs
# zero extra time (no retries), and DEADLINE_SECONDS=480 still bounds the worst case.
MAX_ROUNDS = 5
RETRY_SLEEP_SECONDS = 30
DEADLINE_SECONDS = 480
# Per-socket-op timeout (connect + read), capped down to the remaining deadline budget on each
# probe so a probe that starts late cannot overshoot DEADLINE_SECONDS. Pages are small, so this
# socket-op timeout also bounds body reads adequately — no separate body-read deadline is needed.
PROBE_TIMEOUT_SECONDS = 30


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
    # `critical` may itself list "index.html" (it does in critical-pages.txt); drop it so the
    # index page is probed exactly once — as plan[0], the sole search-mount probe below.
    critical = [rel for rel in critical if rel != "index.html"]
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


def _probe_once(host: str, probe: Probe, expect_sha: str, access_id: str, access_secret: str,
                timeout: float = PROBE_TIMEOUT_SECONDS,
                ) -> tuple[bool, int | None, str | None, str | None]:
    """One probe attempt. Returns (ok, status, docs_build, detail). `detail` names the failed
    check(s) — "status" / "docs-build" / "apex-build" / "search-mount" joined by "+", or the
    transport error text — and is None when ok. `timeout` is the per-socket-op deadline (connect
    + read); run() caps it to the remaining budget so a late probe can't overshoot the overall
    deadline. ANY exception in the open OR body-read path (including a transport error DURING
    HTTPError.read()) is contained and yields (False, None, None, <error text>): a retryable
    failure, never a traceback. The HTTPError response stream is always closed — it owns a
    socket, so a bare e.read() would leak it."""
    req = urllib.request.Request(f"https://{host}{probe.path}", method="GET")
    req.add_header("CF-Access-Client-Id", access_id)
    req.add_header("CF-Access-Client-Secret", access_secret)
    req.add_header("User-Agent", USER_AGENT)
    try:
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                status, headers, body = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:  # non-2xx still carries headers/body
            with e:  # HTTPError is file-like and owns the response socket — always close it
                status, headers, body = e.code, e.headers, e.read()
    except Exception as e:  # noqa: BLE001 — open OR read failure → retryable probe result
        return False, None, None, str(e)
    reasons: list[str] = []
    if status != probe.expect_status:
        reasons.append("status")
    if probe.assert_docs_build and not docs_build_ok(headers.get("X-Docs-Build"), expect_sha):
        reasons.append("docs-build")
    if probe.assert_apex_build and not headers.get("X-Apex-Build"):
        reasons.append("apex-build")
    if probe.assert_search_mount and not search_mount_present(
            body.decode("utf-8", errors="replace")):
        reasons.append("search-mount")
    detail = "+".join(reasons) if reasons else None
    return not reasons, status, headers.get("X-Docs-Build"), detail


def run(host: str, slug: str, expect_sha: str, access_id: str, access_secret: str,
        pdf: str | None, critical: list[str]) -> int:
    """Probe the whole plan, then re-probe ONLY the still-failing probes each round (up to
    MAX_ROUNDS, one RETRY_SLEEP_SECONDS between rounds). A probe passing in ANY round passes;
    a single propagation blip served by the previous worker version cannot fail the gate.
    DEADLINE_SECONDS bounds total wall-clock — on breach, unresolved probes count as failed."""
    plan = probe_plan(slug, pdf, critical)
    start = time.monotonic()
    deadline = start + DEADLINE_SECONDS      # absolute — a hard upper bound on total wall-clock
    pending = list(plan)                     # probes not yet passed
    detail_by_path: dict[str, str] = {}      # last failure detail per path, for logging
    deadline_hit = False

    def _remaining() -> float:
        return deadline - time.monotonic()

    for round_num in range(1, MAX_ROUNDS + 1):
        if not pending:
            break
        still_failing: list[Probe] = []
        unprobed: list[Probe] = []
        for i, probe in enumerate(pending):
            remaining = _remaining()         # checked before each probe
            if remaining < 1:                # < 1s budget: don't start a probe that could overshoot
                deadline_hit = True
                unprobed = pending[i:]       # not reached this round → still unresolved
                break
            ok, status, docs_build, detail = _probe_once(
                host, probe, expect_sha, access_id, access_secret,
                timeout=min(PROBE_TIMEOUT_SECONDS, max(1, remaining)))
            if ok:
                continue
            still_failing.append(probe)
            detail_by_path[probe.path] = (
                f"status={status} docs-build={docs_build} detail={detail}")
        pending = still_failing + unprobed
        if deadline_hit or not pending or round_num == MAX_ROUNDS:
            break
        remaining = _remaining()             # checked before the inter-round sleep
        if remaining <= 0:                   # no budget left → deadline path (skip the sleep)
            deadline_hit = True
            break
        for probe in pending:
            print(f"SMOKE-RETRY {probe.path}: round {round_num} "
                  f"{detail_by_path[probe.path]}", file=sys.stderr)
        time.sleep(min(RETRY_SLEEP_SECONDS, remaining))   # never sleep past the deadline

    if deadline_hit:
        print("SMOKE-DEADLINE: overall deadline reached — remaining probes counted as failed",
              file=sys.stderr)
    for probe in pending:
        print(f"SMOKE-FAIL {probe.path}: {detail_by_path.get(probe.path, 'unresolved')}",
              file=sys.stderr)
    failures = len(pending)
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
