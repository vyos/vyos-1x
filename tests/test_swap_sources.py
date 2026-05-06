"""Tests for swap_sources.py — run with:
  cd tests && PYTHONPATH=../scripts python -m pytest test_swap_sources.py -v
"""
import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_docs(tmp_path: Path, stems: list[str]) -> Path:
    """Create a minimal docs/ tree with RST + md-prefixed MD files for each stem."""
    docs = tmp_path / "docs"
    for stem in stems:
        p = Path(stem)
        name = p.name
        parent = p.parent  # may be "." for flat stems
        target_dir = docs / parent if str(parent) != "." else docs
        target_dir.mkdir(parents=True, exist_ok=True)
        # RST file that would normally be the Sphinx source
        (target_dir / f"{name}.rst").write_text(f".. _{name}:\n\nDummy RST for {stem}\n")
        # md- prefixed MyST file waiting to be swapped in
        (target_dir / f"md-{name}.md").write_text(f"# {name}\nDummy MyST for {stem}\n")
    return docs


# ---------------------------------------------------------------------------
# parse_swap_list
# ---------------------------------------------------------------------------

def test_parse_swap_list_basic(tmp_path):
    from swap_sources import parse_swap_list

    swap_txt = tmp_path / "_swap.txt"
    swap_txt.write_text(
        "# comment\n"
        "\n"
        "configuration/firewall/zone\n"
        "  quick-start  \n"  # leading/trailing whitespace
        "# another comment\n"
        "installation/virtual/vmware\n"
    )
    stems = parse_swap_list(swap_txt)
    assert stems == [
        "configuration/firewall/zone",
        "quick-start",
        "installation/virtual/vmware",
    ]


def test_parse_swap_list_empty(tmp_path):
    from swap_sources import parse_swap_list

    missing = tmp_path / "_swap.txt"
    assert parse_swap_list(missing) == []


# ---------------------------------------------------------------------------
# do_swap
# ---------------------------------------------------------------------------

def test_swap_renames_files(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (tmp_path / "docs" / "_swap.txt").write_text("quick-start\n")

    do_swap(docs)

    assert (docs / "quick-start.md").exists(), "md- file should be renamed to plain .md"
    assert not (docs / "md-quick-start.md").exists(), "md- prefix file should be gone"
    assert (docs / "quick-start.rst").exists(), "RST file should still exist"


def test_swap_creates_state_file(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_swap.txt").write_text("quick-start\n")

    do_swap(docs)

    state_file = docs / "_build" / "_swap_state.json"
    assert state_file.exists(), "state file should be created in _build/"

    state = json.loads(state_file.read_text())
    assert state["version"] == 1
    assert len(state["swaps"]) == 1

    entry = state["swaps"][0]
    assert entry["stem"] == "quick-start"
    assert "md_from" in entry
    assert "md_to" in entry
    assert "rst_excluded" in entry


def test_swap_creates_exclude_file(tmp_path):
    from swap_sources import do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_swap.txt").write_text("quick-start\n")

    do_swap(docs)

    exclude_file = docs / "_build" / "_swap_exclude.txt"
    assert exclude_file.exists(), "exclude file should be created in _build/"

    lines = [l.strip() for l in exclude_file.read_text().splitlines() if l.strip()]
    assert "quick-start.rst" in lines


# ---------------------------------------------------------------------------
# do_restore
# ---------------------------------------------------------------------------

def test_restore_undoes_renames(tmp_path):
    from swap_sources import do_restore, do_swap

    stems = ["quick-start"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_swap.txt").write_text("quick-start\n")

    do_swap(docs)
    assert (docs / "quick-start.md").exists()

    do_restore(docs)

    assert (docs / "md-quick-start.md").exists(), "md- prefix file should be restored"
    assert not (docs / "quick-start.md").exists(), "plain .md should be gone after restore"

    state_file = docs / "_build" / "_swap_state.json"
    exclude_file = docs / "_build" / "_swap_exclude.txt"
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
    (docs / "_swap.txt").write_text("quick-start\ncli\n")

    # Simulate a collision: unprefixed .md already exists for "cli"
    (docs / "cli.md").write_text("# collision\n")

    with pytest.raises(RuntimeError, match="collision"):
        do_swap(docs)

    # Rollback: first stem's rename should be undone
    assert (docs / "md-quick-start.md").exists(), "rollback should undo completed renames"
    assert not (docs / "quick-start.md").exists(), "renamed file should not exist after rollback"

    # State file should NOT be written on failure
    state_file = docs / "_build" / "_swap_state.json"
    assert not state_file.exists(), "no state file should be written on failure"


# ---------------------------------------------------------------------------
# Rollback on rename failure (monkeypatched os.rename)
# ---------------------------------------------------------------------------

def test_swap_rollback_on_rename_failure(tmp_path, monkeypatch):
    """If os.rename raises on the second call, the first rename must be undone."""
    from swap_sources import do_swap

    stems = ["quick-start", "cli"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_swap.txt").write_text("quick-start\ncli\n")

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
    assert (docs / "md-quick-start.md").exists(), "rollback should undo the first rename"
    assert not (docs / "quick-start.md").exists(), "renamed file should not exist after rollback"

    # No state file should exist
    assert not (docs / "_build" / "_swap_state.json").exists()


# ---------------------------------------------------------------------------
# Nested paths
# ---------------------------------------------------------------------------

def test_swap_nested_paths(tmp_path):
    from swap_sources import do_swap, do_restore

    stems = ["configuration/firewall/zone"]
    docs = _setup_docs(tmp_path, stems)
    (docs / "_swap.txt").write_text("configuration/firewall/zone\n")

    do_swap(docs)

    swapped = docs / "configuration" / "firewall" / "zone.md"
    md_source = docs / "configuration" / "firewall" / "md-zone.md"
    assert swapped.exists(), "nested md file should be renamed"
    assert not md_source.exists()

    exclude_file = docs / "_build" / "_swap_exclude.txt"
    lines = [l.strip() for l in exclude_file.read_text().splitlines() if l.strip()]
    assert "configuration/firewall/zone.rst" in lines

    do_restore(docs)

    assert md_source.exists(), "nested md- file should be restored"
    assert not swapped.exists()
