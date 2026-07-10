import json
from pathlib import Path
import pytest
from scripts.docs_gates import gates


@pytest.fixture()
def artifact(tmp_path: Path) -> Path:
    root = tmp_path / "en" / "rolling"
    root.mkdir(parents=True)
    for i in range(50):
        (root / f"p{i}.html").write_text(
            f'<html><head><link rel="canonical" href="https://docs.vyos.io/en/rolling/p{i}.html"/></head><body>x</body></html>'
        )
    (root / "index.html").write_text(
        '<html><head><link rel="canonical" href="https://docs.vyos.io/en/rolling/index.html"/></head></html>'
    )
    (root / "vyos-documentation.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "pagefind").mkdir()
    (root / "pagefind" / "pagefind.js").write_text("// index")
    (root / "installation").mkdir()
    (root / "installation" / "index.html").write_text(
        '<html><head><link rel="canonical" href="https://docs.vyos.io/en/rolling/installation/index.html"/></head></html>'
    )
    return tmp_path


def versions_arg(tmp_path: Path) -> Path:
    """Hermetic stand-in for workers/versions.json — writes a fixture-local
    manifest with the minimal schema the gates consume (mirrors the real
    file's shape for the rolling entry) so tests never depend on, or break
    from, edits to the repo file."""
    p = tmp_path / "versions.json"
    p.write_text(json.dumps({
        "schema_version": 2,
        "default_lang": "en",
        "default_version": "rolling",
        "languages": [{"code": "en", "label": "English"}],
        "versions": [
            {"slug": "rolling", "label": "Rolling (development)", "status": "dev",
             "binding": "DOCS_ROLLING", "aliases": ["latest"],
             "pdf": "/en/rolling/vyos-documentation.pdf"},
        ],
    }))
    return p


@pytest.fixture()
def versions(tmp_path: Path) -> Path:
    return versions_arg(tmp_path)


def test_pass_on_good_artifact(artifact: Path, versions: Path):
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html", "installation/index.html"])
    assert rc == 0


def test_fail_on_missing_critical_page(artifact: Path, versions: Path):
    (artifact / "en/rolling/installation/index.html").unlink()
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html", "installation/index.html"])
    assert rc == 1


def test_fail_on_count_collapse(artifact: Path, versions: Path, tmp_path: Path):
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"sha": "old", "page_count": 5000}))  # previous build 100x bigger
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=meta, critical=["index.html"])
    assert rc == 1


def test_fail_on_alias_canonical(artifact: Path, versions: Path):
    (artifact / "en/rolling/bad.html").write_text(
        '<html><head><link rel="canonical" href="https://docs.vyos.io/en/latest/bad.html"/></head></html>'
    )
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html"])
    assert rc == 1


def test_fail_on_missing_canonical(artifact: Path, versions: Path):
    (artifact / "en/rolling/nocanon.html").write_text(
        '<html><head></head><body>no canonical link at all</body></html>'
    )
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html"])
    assert rc == 1


def test_fail_on_oversize_file(artifact: Path, versions: Path):
    big = artifact / "en/rolling/huge.bin"
    big.write_bytes(b"\0" * (26 * 1024 * 1024))  # > 25 MiB
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html"])
    assert rc == 1


def test_fail_when_declared_pdf_missing(artifact: Path, versions: Path):
    (artifact / "en/rolling/vyos-documentation.pdf").unlink()
    rc = gates.run(artifact=artifact, slug="rolling", versions=versions,
                   previous_meta=None, critical=["index.html"])
    assert rc == 1
