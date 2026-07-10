import urllib.error
import urllib.request

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
