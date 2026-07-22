from __future__ import annotations

import io
import urllib.error
import urllib.request
from email.message import Message

from scripts.docs_gates import smoke
from scripts.docs_gates.conftest import REDIRECT_LOCATION, REDIRECT_PATH


def test_probe_plan_scoped_to_slug():
    plan = smoke.probe_plan("1.5", pdf="/en/1.5/vyos-documentation.pdf",
                            critical=["index.html", "cli/index.html"])
    urls = [p.path for p in plan]
    assert "/en/1.5/index.html" in urls
    assert "/en/1.5/cli/index.html" in urls
    assert "/en/1.5/vyos-documentation.pdf" in urls
    assert "/en/1.5/definitely-missing-page-xyz.html" in urls  # 404-status probe
    assert "/versions.json" in urls and "/healthz" in urls      # apex specials
    assert not any(u.startswith("/en/rolling/") for u in urls)  # scoped (§7.1.2)


def test_assertions_follow_header_contract():
    plan = smoke.probe_plan("1.5", pdf=None, critical=["index.html"])
    content = next(p for p in plan if p.path == "/en/1.5/index.html")
    assert content.expect_status == 200 and content.assert_docs_build is True
    apex = next(p for p in plan if p.path == "/versions.json")
    assert apex.assert_docs_build is False and apex.assert_apex_build is True
    missing = next(p for p in plan if "definitely-missing" in p.path)
    assert missing.expect_status == 404


def test_skip_sentinel_relaxes_sha_to_presence_only():
    # expect_sha == "SKIP" (nightly sweep, Task 3.5): header must be PRESENT but any value passes
    assert smoke.docs_build_ok("anything", expect_sha="SKIP") is True
    assert smoke.docs_build_ok(None, expect_sha="SKIP") is False
    assert smoke.docs_build_ok("abc", expect_sha="abc") is True
    assert smoke.docs_build_ok("abc", expect_sha="def") is False


# --- Phase-2 obligation (authorized addition, not in the original brief): the
# index.html probe must assert the CF-built HTML carries the `#vyos-search`
# mount div, so CI catches a build that silently forgot to set
# DOCS_VERSION_SLUG (which would ship stock RTD search instead of Pagefind). ---

def test_probe_plan_asserts_search_mount_on_index_only():
    plan = smoke.probe_plan("1.5", pdf=None, critical=["index.html", "cli/index.html"])
    index = next(p for p in plan if p.path == "/en/1.5/index.html")
    assert index.assert_search_mount is True
    other_content = [p for p in plan if p.path != "/en/1.5/index.html" and p.assert_docs_build]
    assert other_content and all(p.assert_search_mount is False for p in other_content)


# --- CodeRabbit finding: smoke's probe requests must mirror parity.py's _NoRedirect
# opener — an exact-status probe (200/404) that silently followed a 3xx would report
# whatever the redirect target returns instead of the redirect itself. ---

def test_opener_observes_redirect_directly_not_followed(redirect_http_server):
    # End-to-end: a real local HTTP server returns a 301, opened through smoke.py's
    # module-level _OPENER (the exact object `run()` uses) — proves it's actually
    # wired to refuse the redirect, matching run()'s HTTPError-catch handling of 3xx.
    req = urllib.request.Request(f"http://{redirect_http_server}{REDIRECT_PATH}", method="GET")
    try:
        smoke._OPENER.open(req, timeout=5)
        raise AssertionError("expected HTTPError for a 301 with the no-redirect opener")
    except urllib.error.HTTPError as e:
        assert e.code == 301
        assert e.headers.get("Location") == REDIRECT_LOCATION


def test_search_mount_present():
    assert smoke.search_mount_present('<div id="vyos-search" role="search"></div>') is True
    assert smoke.search_mount_present('<html><body>no search here</body></html>') is False


# --- Hardening (this change): explicit UA + per-probe retry. Mock at the _OPENER boundary
# (the exact object _probe_once() opens through, mirroring the redirect test above which drives
# smoke._OPENER directly), and shrink RETRY_SLEEP_SECONDS to 0 so retries don't wall-clock. ---


class _FakeResp:
    """Stand-in for what _OPENER.open() yields: a context manager exposing .status /
    .headers / .read()."""

    def __init__(self, status: int, headers: dict[str, str], body: bytes = b""):
        self.status = status
        self.headers = headers
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _FakeOpener:
    """Yields queued responses in order; an Exception item is raised (models a transport
    error, or a non-2xx delivered as HTTPError). Records each opened Request for assertions."""

    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls: list[urllib.request.Request] = []

    def open(self, req: urllib.request.Request, timeout: float | None = None) -> object:
        self.calls.append(req)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _http_error(code: int, headers: dict[str, str]) -> urllib.error.HTTPError:
    hdrs = Message()
    for k, v in headers.items():
        hdrs[k] = v
    return urllib.error.HTTPError("https://host.invalid/x", code, "msg", hdrs, io.BytesIO(b""))


def test_probe_sends_explicit_user_agent(monkeypatch):
    opener = _FakeOpener([_FakeResp(200, {"X-Docs-Build": "sha1"})])
    monkeypatch.setattr(smoke, "_OPENER", opener)
    probe = smoke.Probe("/en/1.5/index.html", 200, assert_docs_build=True, assert_apex_build=False)
    ok, *_ = smoke._probe_once("host.example", probe, "sha1", "cf-id", "cf-secret")
    assert ok is True
    req = opener.calls[0]
    assert req.get_header("User-agent") == smoke.USER_AGENT   # urllib capitalizes the key
    assert req.get_header("Cf-access-client-id") == "cf-id"   # CF-Access headers still sent


def test_retry_passes_when_second_attempt_ok(monkeypatch):
    monkeypatch.setattr(smoke, "RETRY_SLEEP_SECONDS", 0)
    opener = _FakeOpener([
        _FakeResp(307, {"X-Docs-Build": "stale"}),    # attempt 1: previous-version blip
        _FakeResp(200, {"X-Docs-Build": "goodsha"}),  # attempt 2: propagation settled
    ])
    monkeypatch.setattr(smoke, "_OPENER", opener)
    probe = smoke.Probe("/en/1.5/cli.html", 200, assert_docs_build=True, assert_apex_build=False)
    assert smoke._probe_with_retries("host", probe, "goodsha", "id", "sec") is True
    assert len(opener.calls) == 2


def test_retry_fails_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(smoke, "RETRY_SLEEP_SECONDS", 0)
    opener = _FakeOpener([_FakeResp(307, {"X-Docs-Build": "stale"})
                          for _ in range(smoke.MAX_ATTEMPTS)])
    monkeypatch.setattr(smoke, "_OPENER", opener)
    probe = smoke.Probe("/en/1.5/index.html", 200, assert_docs_build=True, assert_apex_build=False)
    assert smoke._probe_with_retries("host", probe, "goodsha", "id", "sec") is False
    assert len(opener.calls) == smoke.MAX_ATTEMPTS   # tried the full budget


def test_expected_404_passes_first_attempt_without_retry(monkeypatch):
    monkeypatch.setattr(smoke, "RETRY_SLEEP_SECONDS", 0)
    opener = _FakeOpener([_http_error(404, {})])  # 404 delivered as HTTPError, like urllib
    monkeypatch.setattr(smoke, "_OPENER", opener)
    probe = smoke.Probe("/en/1.5/definitely-missing.html", 404,
                        assert_docs_build=False, assert_apex_build=False)
    assert smoke._probe_with_retries("host", probe, "sha", "id", "sec") is True
    assert len(opener.calls) == 1   # a legitimately-expected 404 must NOT burn retries
