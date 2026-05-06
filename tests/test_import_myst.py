"""Tests for import_myst.py — run with:
  cd tests && PYTHONPATH=../scripts python3 -m pytest test_import_myst.py -v
"""
import warnings
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# import_page tests (no git dependency)
# ---------------------------------------------------------------------------

def test_import_single_page(tmp_path):
    """Creates md-{name}.md with the given content."""
    from import_myst import import_page

    docs = tmp_path / "docs"
    docs.mkdir()
    content = b"# quick-start\nHello MyST\n"

    result = import_page("quick-start", content, docs, force=False)

    assert result is True
    dest = docs / "md-quick-start.md"
    assert dest.exists()
    assert dest.read_bytes() == content


def test_import_skip_identical(tmp_path):
    """Returns False and does not modify the file when content is identical."""
    from import_myst import import_page

    docs = tmp_path / "docs"
    docs.mkdir()
    content = b"# quick-start\nIdentical content\n"
    dest = docs / "md-quick-start.md"
    dest.write_bytes(content)
    mtime_before = dest.stat().st_mtime_ns

    result = import_page("quick-start", content, docs, force=False)

    assert result is False
    assert dest.read_bytes() == content
    assert dest.stat().st_mtime_ns == mtime_before


def test_import_warn_different_without_force(tmp_path):
    """Returns False and keeps old content when content differs and force=False."""
    from import_myst import import_page

    docs = tmp_path / "docs"
    docs.mkdir()
    old_content = b"# old content\n"
    new_content = b"# new content\n"
    dest = docs / "md-quick-start.md"
    dest.write_bytes(old_content)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = import_page("quick-start", new_content, docs, force=False)

    assert result is False
    assert dest.read_bytes() == old_content
    assert len(caught) == 1
    assert "force" in str(caught[0].message).lower()


def test_import_overwrite_with_force(tmp_path):
    """Returns True and writes new content when force=True."""
    from import_myst import import_page

    docs = tmp_path / "docs"
    docs.mkdir()
    old_content = b"# old content\n"
    new_content = b"# new content\n"
    dest = docs / "md-quick-start.md"
    dest.write_bytes(old_content)

    result = import_page("quick-start", new_content, docs, force=True)

    assert result is True
    assert dest.read_bytes() == new_content


def test_import_nested_path(tmp_path):
    """Creates parent dirs and writes md-{name}.md in the correct nested location."""
    from import_myst import import_page

    docs = tmp_path / "docs"
    docs.mkdir()
    content = b"# zone\nFirewall zone docs\n"

    result = import_page("configuration/firewall/zone", content, docs, force=False)

    assert result is True
    dest = docs / "configuration" / "firewall" / "md-zone.md"
    assert dest.exists()
    assert dest.read_bytes() == content
    # Parent dirs were created
    assert (docs / "configuration" / "firewall").is_dir()
