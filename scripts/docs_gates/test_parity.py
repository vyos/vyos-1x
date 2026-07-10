import json
import sys
import urllib.error

from scripts.docs_gates import parity
from scripts.docs_gates.conftest import REDIRECT_LOCATION, REDIRECT_PATH


def test_sitemap_url_extraction():
    xml = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           "<url><loc>https://docs.vyos.io/en/1.5/a.html</loc></url>"
           "<url><loc>https://docs.vyos.io/en/1.5/b/</loc></url></urlset>")
    assert parity.urls_from_sitemap(xml) == ["/en/1.5/a.html", "/en/1.5/b/"]


def test_alias_corpus_includes_pdf_and_alias_rows():
    rows = parity.alias_corpus()
    assert ("/en/latest/", 301, "/en/rolling/") in rows
    assert ("/_/downloads/en/1.5/pdf/", 301, "/en/1.5/vyos-documentation.pdf") in rows


def test_fetch_never_follows_redirects_unit():
    # unit-level sanity check on the handler class in isolation (kept alongside the
    # end-to-end test below, which is what actually proves the opener is wired up)
    handler = parity._NoRedirect()
    assert handler.redirect_request(None, None, 301, "Moved", {}, "https://x/") is None


def test_fetch_never_follows_redirects(redirect_http_server, monkeypatch):
    # End-to-end: real local HTTP server returns a 301, exercised through the PUBLIC
    # fetch() entrypoint (not just the handler class) — proves _OPENER is actually
    # wired into fetch() and surfaces (301, Location) instead of following it.
    monkeypatch.setattr(parity, "_SCHEME", "http")
    status, location = parity.fetch(redirect_http_server, REDIRECT_PATH, None, "GET")
    assert status == 301
    assert location == REDIRECT_LOCATION


def test_default_slugs_scoped_to_cf_built_versions():
    # 1.3/1.2 have NO RTD sitemaps (spec §15a.5); legacy parity belongs to the
    # snapshot repo's crawl-inventory job, not this sweep
    assert parity.DEFAULT_SLUGS == "rolling,1.5,1.4"


def test_fetch_records_transport_error_as_status_zero(monkeypatch):
    # a DNS blip / timeout must fail the single probe, not abort the whole run
    class _Boom:
        def open(self, req, timeout=None):
            raise urllib.error.URLError("dns blip")

    monkeypatch.setattr(parity, "_OPENER", _Boom())
    assert parity.fetch("host.invalid", "/en/rolling/", None) == (0, None)


def test_main_always_writes_report_on_transport_errors(tmp_path, monkeypatch):
    # sitemap status probe says 200, but the body fetch raises mid-sweep:
    # the run must record per-slug failures, keep going, and STILL write the report
    report = tmp_path / "parity-report.json"
    monkeypatch.setattr(parity, "fetch", lambda *a, **k: (200, None))

    def _boom(*a, **k):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(parity.urllib.request, "urlopen", _boom)
    monkeypatch.setattr(sys, "argv", ["parity", "--sitemap-host", "sitemap.invalid",
                                      "--probe-host", "probe.invalid",
                                      "--report", str(report)])
    rc = parity.main()
    assert rc == 1
    data = json.loads(report.read_text())
    assert data["failures"]  # report written despite transport errors
    assert any("sitemap" in f["reason"] for f in data["failures"])
