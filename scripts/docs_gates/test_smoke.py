from __future__ import annotations

import io
import urllib.error
import urllib.request
from email.message import Message
from urllib.parse import urlsplit

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


# --- Hardening: explicit UA + round-based retry with an overall deadline. Mock at the _OPENER
# boundary (the object _probe_once() opens through, mirroring the redirect test above which
# drives smoke._OPENER directly). run()-level round tests inject a small plan via probe_plan and
# a path-keyed opener; sleeps are spied (or constants shrunk) so nothing wall-clocks. ---


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
    """Yields queued responses in order; an Exception item is raised (models a transport error,
    or a non-2xx delivered as HTTPError). Records each opened Request + the timeout it was
    called with, for assertions."""

    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls: list[urllib.request.Request] = []
        self.timeouts: list[float | None] = []

    def open(self, req: urllib.request.Request, timeout: float | None = None) -> object:
        self.calls.append(req)
        self.timeouts.append(timeout)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _RecordingBody(io.BytesIO):
    """HTTPError.fp stand-in: records close() (so tests can assert the response stream is
    closed) and can optionally raise on read (a transport error DURING body read). urllib's
    addbase binds read through to fp and closes fp on close(), so overriding them here is what
    e.read() / closing e actually hit."""

    def __init__(self, data: bytes = b"", raise_on_read: bool = False):
        super().__init__(data)
        self.close_calls = 0
        self._raise_on_read = raise_on_read

    def read(self, *args: object) -> bytes:  # noqa: D401
        if self._raise_on_read:
            raise OSError("reset during body read")
        return super().read(*args)

    def close(self) -> None:
        self.close_calls += 1
        super().close()


def _http_error_read_boom(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://host.invalid/x", code, "msg", Message(), _RecordingBody(raise_on_read=True))


class _PathOpener:
    """Opener keyed by request path: each path maps to a queue consumed one item per probe of
    that path (item = _FakeResp, or an Exception that is raised). Records probed paths in order,
    so round scoping / retry counts are assertable across rounds that re-probe only failures."""

    def __init__(self, by_path: dict[str, list[object]]):
        self._by_path = {p: list(v) for p, v in by_path.items()}
        self.calls: list[str] = []
        self.timeouts: list[float | None] = []

    def open(self, req: urllib.request.Request, timeout: float | None = None) -> object:
        path = urlsplit(req.full_url).path
        self.calls.append(path)
        self.timeouts.append(timeout)
        item = self._by_path[path].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _plan(paths: list[str]) -> list[smoke.Probe]:
    """Minimal status-only plan (no build/search assertions) for run() round tests."""
    return [smoke.Probe(p, 200, assert_docs_build=False, assert_apex_build=False) for p in paths]


def test_probe_sends_explicit_user_agent(monkeypatch):
    opener = _FakeOpener([_FakeResp(200, {"X-Docs-Build": "sha1"})])
    monkeypatch.setattr(smoke, "_OPENER", opener)
    probe = smoke.Probe("/en/1.5/index.html", 200, assert_docs_build=True, assert_apex_build=False)
    ok, *_ = smoke._probe_once("host.example", probe, "sha1", "cf-id", "cf-secret")
    assert ok is True
    req = opener.calls[0]
    assert req.get_header("User-agent") == smoke.USER_AGENT   # urllib capitalizes the key
    assert req.get_header("Cf-access-client-id") == "cf-id"   # CF-Access headers still sent


def test_transport_error_recovers_in_second_round(monkeypatch):
    monkeypatch.setattr(smoke, "probe_plan",
                        lambda slug, pdf, critical: _plan(["/en/rolling/index.html"]))
    monkeypatch.setattr(smoke, "RETRY_SLEEP_SECONDS", 0)
    opener = _PathOpener({
        "/en/rolling/index.html": [OSError("dns hiccup"), _FakeResp(200, {})],
    })
    monkeypatch.setattr(smoke, "_OPENER", opener)
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 0
    # round 1 transport error, round 2 success — the same path is re-probed
    assert opener.calls == ["/en/rolling/index.html", "/en/rolling/index.html"]


def test_httperror_read_crash_is_contained_as_failure(monkeypatch):
    # agy-critical: a transport error DURING e.read() must not escape as a traceback.
    monkeypatch.setattr(smoke, "_OPENER", _FakeOpener([_http_error_read_boom(502)]))
    probe = smoke.Probe("/en/rolling/index.html", 200,
                        assert_docs_build=False, assert_apex_build=False)
    ok, status, docs_build, detail = smoke._probe_once("host", probe, "sha", "id", "sec")
    assert ok is False
    assert status is None and docs_build is None
    assert detail is not None and "reset during body read" in detail


def test_sleeps_once_per_inter_round_gap_not_per_probe(monkeypatch):
    monkeypatch.setattr(smoke, "probe_plan",
                        lambda slug, pdf, critical: _plan(["/a", "/b", "/c"]))
    sleeps: list[float] = []
    monkeypatch.setattr(smoke.time, "sleep", lambda s: sleeps.append(s))
    # /a and /b fail round 1 then pass round 2; /c passes round 1
    opener = _PathOpener({
        "/a": [_FakeResp(500, {}), _FakeResp(200, {})],
        "/b": [_FakeResp(500, {}), _FakeResp(200, {})],
        "/c": [_FakeResp(200, {})],
    })
    monkeypatch.setattr(smoke, "_OPENER", opener)
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 0
    assert sleeps == [smoke.RETRY_SLEEP_SECONDS]  # ONE inter-round sleep despite 2 failing probes


def test_second_round_reprobes_only_the_failed_path(monkeypatch):
    monkeypatch.setattr(smoke, "probe_plan",
                        lambda slug, pdf, critical: _plan(["/a", "/b", "/c"]))
    monkeypatch.setattr(smoke.time, "sleep", lambda s: None)
    opener = _PathOpener({
        "/a": [_FakeResp(200, {})],                      # passes round 1
        "/b": [_FakeResp(500, {}), _FakeResp(200, {})],  # fails r1, passes r2
        "/c": [_FakeResp(200, {})],                      # passes round 1
    })
    monkeypatch.setattr(smoke, "_OPENER", opener)
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 0
    assert opener.calls == ["/a", "/b", "/c", "/b"]  # only the failed path is re-probed


def test_run_reports_failure_count_and_nonzero_exit(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: _plan(["/a", "/b"]))
    monkeypatch.setattr(smoke, "MAX_ROUNDS", 1)  # single round, no retries
    monkeypatch.setattr(smoke, "_OPENER", _PathOpener({
        "/a": [_FakeResp(200, {})],
        "/b": [_FakeResp(500, {})],
    }))
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 1
    assert '{"failures": 1}' in capsys.readouterr().out


def test_run_reports_clean_and_zero_exit(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: _plan(["/a", "/b"]))
    monkeypatch.setattr(smoke, "_OPENER", _PathOpener({
        "/a": [_FakeResp(200, {})],
        "/b": [_FakeResp(200, {})],
    }))
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 0
    assert '{"failures": 0}' in capsys.readouterr().out


def test_deadline_counts_unresolved_as_failed(monkeypatch, capsys):
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: _plan(["/a", "/b"]))
    monkeypatch.setattr(smoke, "DEADLINE_SECONDS", 0)  # trips before the first probe
    opener = _PathOpener({"/a": [_FakeResp(200, {})], "/b": [_FakeResp(200, {})]})
    monkeypatch.setattr(smoke, "_OPENER", opener)
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 1
    captured = capsys.readouterr()
    assert "SMOKE-DEADLINE" in captured.err
    assert '{"failures": 2}' in captured.out
    assert opener.calls == []  # deadline reached before any probe ran


def test_probe_plan_dedups_index_html():
    plan = smoke.probe_plan("rolling", None, ["index.html", "cli.html"])
    index_probes = [p for p in plan if p.path == "/en/rolling/index.html"]
    assert len(index_probes) == 1                       # not duplicated by the critical list
    assert index_probes[0].assert_search_mount is True  # still the single search-mount probe
    assert sum(1 for p in plan if p.path == "/en/rolling/cli.html") == 1  # cli.html preserved


# --- CR round 2: close the HTTPError response stream (it owns a socket) + name the failed
# assertion in retry/fail logs. ---

def test_httperror_response_is_closed(monkeypatch):
    # HTTPError owns the response socket; the expected-404 path must close it, not leak.
    body = _RecordingBody(b"not found")
    monkeypatch.setattr(smoke, "_OPENER", _FakeOpener([
        urllib.error.HTTPError("https://host.invalid/x", 404, "msg", Message(), body)]))
    probe = smoke.Probe("/en/rolling/missing.html", 404,
                        assert_docs_build=False, assert_apex_build=False)
    ok, *_ = smoke._probe_once("host", probe, "sha", "id", "sec")
    assert ok is True                # 404 expected → passes
    assert body.close_calls >= 1     # response stream closed (no socket leak / ResourceWarning)


def test_httperror_response_is_closed_even_when_read_raises(monkeypatch):
    body = _RecordingBody(raise_on_read=True)
    monkeypatch.setattr(smoke, "_OPENER", _FakeOpener([
        urllib.error.HTTPError("https://host.invalid/x", 502, "msg", Message(), body)]))
    probe = smoke.Probe("/en/rolling/index.html", 200,
                        assert_docs_build=False, assert_apex_build=False)
    ok, _, _, detail = smoke._probe_once("host", probe, "sha", "id", "sec")
    assert ok is False
    assert detail is not None and "reset during body read" in detail
    assert body.close_calls >= 1     # close still attempted despite the read raising


def test_apex_build_failure_is_named_in_logs(monkeypatch, capsys):
    # 200 but no X-Apex-Build: without a named detail the log read "status=200 docs-build=None".
    probe = smoke.Probe("/versions.json", 200, assert_docs_build=False, assert_apex_build=True)
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: [probe])
    monkeypatch.setattr(smoke, "MAX_ROUNDS", 1)
    monkeypatch.setattr(smoke, "_OPENER", _PathOpener({"/versions.json": [_FakeResp(200, {})]}))
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 1
    err = capsys.readouterr().err
    assert "SMOKE-FAIL /versions.json:" in err
    assert "detail=apex-build" in err   # names the failed check
    assert "status=200" in err          # existing fields preserved


def test_search_mount_failure_is_named_in_logs(monkeypatch, capsys):
    # 200 + correct build, but the HTML lacks the #vyos-search mount div.
    probe = smoke.Probe("/en/rolling/index.html", 200, assert_docs_build=True,
                        assert_apex_build=False, assert_search_mount=True)
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: [probe])
    monkeypatch.setattr(smoke, "MAX_ROUNDS", 1)
    monkeypatch.setattr(smoke, "_OPENER", _PathOpener({
        "/en/rolling/index.html": [_FakeResp(200, {"X-Docs-Build": "goodsha"},
                                             b"<html>no search</html>")]}))
    assert smoke.run("host", "rolling", "goodsha", "id", "sec", None, []) == 1
    assert "detail=search-mount" in capsys.readouterr().err


def test_probe_once_detail_joins_multiple_failed_checks(monkeypatch):
    # wrong status AND missing X-Apex-Build → detail "status+apex-build"
    monkeypatch.setattr(smoke, "_OPENER", _FakeOpener([_FakeResp(500, {})]))
    probe = smoke.Probe("/versions.json", 200, assert_docs_build=False, assert_apex_build=True)
    ok, _, _, detail = smoke._probe_once("host", probe, "sha", "id", "sec")
    assert ok is False
    assert detail == "status+apex-build"


# --- Adversarial round: DEADLINE_SECONDS is a HARD bound — the per-probe socket timeout and the
# inter-round sleep are both capped to the remaining budget so neither can overshoot it. ---

def test_probe_timeout_capped_to_remaining_budget(monkeypatch):
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: _plan(["/a"]))
    monkeypatch.setattr(smoke, "DEADLINE_SECONDS", 5)  # << PROBE_TIMEOUT_SECONDS (30)
    opener = _PathOpener({"/a": [_FakeResp(200, {})]})
    monkeypatch.setattr(smoke, "_OPENER", opener)
    smoke.run("host", "rolling", "sha", "id", "sec", None, [])
    assert opener.timeouts, "the probe recorded the timeout it was opened with"
    t = opener.timeouts[0]
    assert 1 <= t <= smoke.DEADLINE_SECONDS    # capped DOWN to the ~5s remaining budget
    assert t < smoke.PROBE_TIMEOUT_SECONDS      # NOT the full 30s socket timeout


def test_inter_round_sleep_capped_to_remaining_budget(monkeypatch):
    monkeypatch.setattr(smoke, "probe_plan", lambda slug, pdf, critical: _plan(["/a"]))
    monkeypatch.setattr(smoke, "DEADLINE_SECONDS", 10)  # << RETRY_SLEEP_SECONDS (30)
    sleeps: list[float] = []
    monkeypatch.setattr(smoke.time, "sleep", lambda s: sleeps.append(s))
    opener = _PathOpener({"/a": [_FakeResp(500, {}), _FakeResp(200, {})]})  # fail r1, pass r2
    monkeypatch.setattr(smoke, "_OPENER", opener)
    assert smoke.run("host", "rolling", "sha", "id", "sec", None, []) == 0
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= smoke.DEADLINE_SECONDS  # capped to the ~10s remaining budget
    assert sleeps[0] < smoke.RETRY_SLEEP_SECONDS     # NOT the full 30s sleep
