"""Tests for swap_sources.py — run with:
  cd tests && PYTHONPATH=../scripts python -m pytest test_swap_sources.py -v

In the inverted model MD is the canonical source for migrated pages and RST
under the ``rst-<stem>.rst`` prefix is a fallback used only for stems listed
in ``docs/_rst_overrides.txt``. ``do_swap`` activates the override (renames
``rst-<stem>.rst`` → ``<stem>.rst`` and excludes ``<stem>.md``); ``do_restore``
undoes that.
"""
import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_docs(tmp_path: Path, stems: list[str]) -> Path:
    """Create a minimal docs/ tree with MD primary + rst-prefixed RST for each stem."""
    docs = tmp_path / "docs"
    for stem in stems:
        p = Path(stem)
        name = p.name
        parent = p.parent  # may be "." for flat stems
        target_dir = docs / parent if str(parent) != "." else docs
        target_dir.mkdir(parents=True, exist_ok=True)
        # MD file is the canonical source after the flip.
        (target_dir / f"{name}.md").write_text(f"# {name}\nDummy MyST for {stem}\n")
        # rst-prefixed RST file waiting to be activated as an override.
        (target_dir / f"rst-{name}.rst").write_text(f".. _{name}:\n\nDummy RST for {stem}\n")
    return docs


# ---------------------------------------------------------------------------
# parse_override_list
# ---------------------------------------------------------------------------

def test_parse_override_list_basic(tmp_path):
    from swap_sources import parse_override_list

    overrides_txt = tmp_path / "_rst_overrides.txt"
    overrides_txt.write_text(
        "# comment\n"
        "\n"
        "configuration/firewall/zone\n"
        "  quick-start  \n"  # leading/trailing whitespace
        "# another comment\n"
        "installation/virtual/vmware\n"
    )
    stems = parse_override_list(overrides_txt)
    assert stems == [
        "configuration/firewall/zone",
        "quick-start",
        "installation/virtual/vmware",
    ]


def test_parse_override_list_empty(tmp_path):
    from swap_sources import parse_override_list

    missing = tmp_path / "_rst_overrides.txt"
    assert parse_override_list(missing) == []


# ---------------------------------------------------------------------------
# do_swap (apply RST overrides)
# ---------------------------------------------------------------------------

def test_swap_renames_files(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\n")

    do_swap(docs)

    assert (docs / "quick-start.rst").exists(), "rst- file should be renamed to plain .rst"
    assert not (docs / "rst-quick-start.rst").exists(), "rst- prefix file should be gone"
    assert (docs / "quick-start.md").exists(), "MD file should still exist (just excluded)"


def test_swap_creates_state_file(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\n")

    do_swap(docs)

    state_file = docs / "_build" / "_rst_override_state.json"
    assert state_file.exists(), "state file should be created in _build/"

    state = json.loads(state_file.read_text())
    assert state["version"] == 2
    assert len(state["overrides"]) == 1

    entry = state["overrides"][0]
    assert entry["stem"] == "quick-start"
    assert "rst_from" in entry
    assert "rst_to" in entry
    assert "md_excluded" in entry


def test_swap_creates_exclude_file(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\n")

    do_swap(docs)

    exclude_file = docs / "_build" / "_md_exclude.txt"
    assert exclude_file.exists(), "exclude file should be created in _build/"

    lines = [l.strip() for l in exclude_file.read_text().splitlines() if l.strip()]
    assert "quick-start.md" in lines


# ---------------------------------------------------------------------------
# do_restore
# ---------------------------------------------------------------------------

def test_restore_undoes_renames(tmp_path):
    from swap_sources import do_restore, do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\n")

    do_swap(docs)
    assert (docs / "quick-start.rst").exists()

    do_restore(docs)

    assert (docs / "rst-quick-start.rst").exists(), "rst- prefix file should be restored"
    assert not (docs / "quick-start.rst").exists(), "plain .rst should be gone after restore"
    assert (docs / "quick-start.md").exists(), "MD file should remain untouched throughout"

    state_file = docs / "_build" / "_rst_override_state.json"
    exclude_file = docs / "_build" / "_md_exclude.txt"
    assert not state_file.exists(), "state file should be deleted after restore"
    assert not exclude_file.exists(), "exclude file should be deleted after restore"


def test_restore_noop_without_state(tmp_path):
    from swap_sources import do_restore

    docs = tmp_path / "docs"
    docs.mkdir()
    # Should not raise even with no state file
    do_restore(docs)  # no error = pass


# ---------------------------------------------------------------------------
# Collision / validation
# ---------------------------------------------------------------------------

def test_swap_fails_on_collision(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start", "cli"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\ncli\n")

    # Simulate a collision: unprefixed .rst already exists for "cli"
    (docs / "cli.rst").write_text(".. _cli:\nCollision RST\n")

    with pytest.raises(RuntimeError, match="collision"):
        do_swap(docs)

    # Rollback: first stem's rename should be undone
    assert (docs / "rst-quick-start.rst").exists(), "rollback should undo completed renames"
    assert not (docs / "quick-start.rst").exists(), "renamed file should not exist after rollback"

    # State file should NOT be written on failure
    state_file = docs / "_build" / "_rst_override_state.json"
    assert not state_file.exists(), "no state file should be written on failure"


# ---------------------------------------------------------------------------
# Rollback on rename failure (monkeypatched os.rename)
# ---------------------------------------------------------------------------

def test_swap_rollback_on_rename_failure(tmp_path, monkeypatch):
    """If os.rename raises on the second call, the first rename must be undone."""
    from swap_sources import do_swap

    stems = ["quick-start", "cli"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("quick-start\ncli\n")

    call_count = {"n": 0}
    real_rename = os.rename

    def failing_rename(src, dst):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated rename failure")
        real_rename(src, dst)

    monkeypatch.setattr(os, "rename", failing_rename)

    with pytest.raises(RuntimeError):
        do_swap(docs)

    # First rename (quick-start) should have been rolled back
    assert (docs / "rst-quick-start.rst").exists(), "rollback should undo the first rename"
    assert not (docs / "quick-start.rst").exists(), "renamed file should not exist after rollback"

    # No state file should exist
    assert not (docs / "_build" / "_rst_override_state.json").exists()


# ---------------------------------------------------------------------------
# Nested paths
# ---------------------------------------------------------------------------

def test_swap_nested_paths(tmp_path):
    from swap_sources import do_swap, do_restore

    stems = ["configuration/firewall/zone"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_rst_overrides.txt").write_text("configuration/firewall/zone\n")

    do_swap(docs)

    activated = docs / "configuration" / "firewall" / "zone.rst"
    rst_source = docs / "configuration" / "firewall" / "rst-zone.rst"
    assert activated.exists(), "nested rst file should be renamed"
    assert not rst_source.exists()

    exclude_file = docs / "_build" / "_md_exclude.txt"
    lines = [l.strip() for l in exclude_file.read_text().splitlines() if l.strip()]
    assert "configuration/firewall/zone.md" in lines

    do_restore(docs)

    assert rst_source.exists(), "nested rst- file should be restored"
    assert not activated.exists()
