#!/usr/bin/env python3
"""swap_sources.py — Pre-build swap/restore for the RST override mechanism.

In this repo MD is the canonical source for migrated pages. RST kept around
under the ``rst-<stem>.rst`` prefix is a *fallback* — only consulted when a
page is explicitly listed in ``docs/_rst_overrides.txt`` to revert to the
legacy RST rendering.

This script flips the source files in place at build time so Sphinx renders
the RST instead of the MD for the listed stems, then restores everything
after the build.

Usage
-----
  python scripts/swap_sources.py --swap          # activate RST overrides
  python scripts/swap_sources.py --restore       # undo activated overrides
  python scripts/swap_sources.py --dry-run       # show what would be activated
  python scripts/swap_sources.py --status        # show current state
  python scripts/swap_sources.py --swap --docs-dir /path/to/docs

The ``--swap`` flag name is kept for backward compatibility with the Makefile
and Read the Docs config; semantically it now applies RST overrides.

Override list
-------------
  docs/_rst_overrides.txt — one stem per line, relative to docs/, comments
  (#) skipped. Pages listed here render from rst-<stem>.rst instead of
  <stem>.md at build time.

State files (in docs/_build/, gitignored)
-----------------------------------------
  _rst_override_state.json — records completed RST activations
  _md_exclude.txt          — MD source paths to pass to Sphinx exclude_patterns
"""

import argparse
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILE = "_rst_override_state.json"
EXCLUDE_FILE = "_md_exclude.txt"
OVERRIDE_LIST_FILE = "_rst_overrides.txt"
STATE_VERSION = 2  # bumped from 1 when the swap direction was inverted


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_override_list(path: Path) -> list:
    """Read *path* and return a list of stems (comments/blanks skipped).

    Returns [] if the file does not exist.
    """
    if not path.exists():
        return []
    stems = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            stems.append(stripped)
    return stems


def _build_dir(docs_dir: Path) -> Path:
    build = docs_dir / "_build"
    build.mkdir(parents=True, exist_ok=True)
    return build


def _state_path(docs_dir: Path) -> Path:
    return docs_dir / "_build" / STATE_FILE


def _exclude_path(docs_dir: Path) -> Path:
    return docs_dir / "_build" / EXCLUDE_FILE


def _resolve_stem_paths(docs_dir: Path, stem: str):
    """Return (rst_from, rst_to, md_path) as absolute Paths for a given stem."""
    p = Path(stem)
    name = p.name
    parent = p.parent  # may be PosixPath('.')
    if str(parent) == ".":
        target_dir = docs_dir
    else:
        target_dir = docs_dir / parent

    rst_from = target_dir / f"rst-{name}.rst"  # source: rst-prefixed
    rst_to = target_dir / f"{name}.rst"        # destination: plain .rst
    md_path = target_dir / f"{name}.md"        # MD that will be excluded
    return rst_from, rst_to, md_path


# ---------------------------------------------------------------------------
# do_swap (apply RST overrides)
# ---------------------------------------------------------------------------

def do_swap(docs_dir: Path) -> None:
    """Rename rst-{name}.rst → {name}.rst for each stem in _rst_overrides.txt.

    The matching <stem>.md is recorded in _md_exclude.txt so Sphinx ignores it
    during the build. Validates collisions, records state, writes exclude file.
    Rolls back all completed renames on any failure.
    """
    docs_dir = Path(docs_dir)
    override_list = parse_override_list(docs_dir / OVERRIDE_LIST_FILE)
    if not override_list:
        print("swap_sources: no stems in override list, nothing to do.", file=sys.stderr)
        return

    # Stale state: warn and auto-restore first
    state_path = _state_path(docs_dir)
    if state_path.exists():
        print(
            "swap_sources: WARNING — stale override state detected. Auto-restoring before re-applying.",
            file=sys.stderr,
        )
        do_restore(docs_dir)

    # Validate all stems before touching the filesystem
    planned = []  # list of (rst_from, rst_to, md_path, stem)
    for stem in override_list:
        rst_from, rst_to, md_path = _resolve_stem_paths(docs_dir, stem)

        if not rst_from.exists():
            print(
                f"swap_sources: skipping {stem!r} — rst- source file not found: {rst_from}",
                file=sys.stderr,
            )
            continue

        if not md_path.exists():
            print(
                f"swap_sources: skipping {stem!r} — MD file not found: {md_path}",
                file=sys.stderr,
            )
            continue

        if rst_to.exists():
            raise RuntimeError(
                f"collision: both rst- and unprefixed .rst exist for stem {stem!r}. "
                f"Remove {rst_to} before applying the override."
            )

        planned.append((rst_from, rst_to, md_path, stem))

    # Execute renames with rollback on failure
    completed = []  # list of (rst_from, rst_to) that succeeded
    try:
        for rst_from, rst_to, md_path, stem in planned:
            os.rename(rst_from, rst_to)
            completed.append((rst_from, rst_to))
    except Exception as exc:
        # Rollback completed renames in reverse order
        for from_path, to_path in reversed(completed):
            try:
                os.rename(to_path, from_path)
            except Exception as rollback_exc:
                print(
                    f"swap_sources: ROLLBACK ERROR for {to_path}: {rollback_exc}",
                    file=sys.stderr,
                )
        raise RuntimeError(f"swap_sources: rename failed, rolled back. Cause: {exc}") from exc

    if not completed:
        return

    # Build state and exclude data using relative paths (relative to docs_dir)
    _build_dir(docs_dir)
    overrides = []
    exclude_lines = []
    for rst_from, rst_to, md_path, stem in planned:
        rel_from = rst_from.relative_to(docs_dir)
        rel_to = rst_to.relative_to(docs_dir)
        rel_md = md_path.relative_to(docs_dir)
        overrides.append({
            "stem": stem,
            "rst_from": str(rel_from),
            "rst_to": str(rel_to),
            "md_excluded": str(rel_md),
        })
        exclude_lines.append(str(rel_md))

    state = {"version": STATE_VERSION, "overrides": overrides}
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _exclude_path(docs_dir).write_text("\n".join(exclude_lines) + "\n", encoding="utf-8")

    print(f"swap_sources: applied {len(completed)} RST override(s).", file=sys.stderr)


# ---------------------------------------------------------------------------
# do_restore
# ---------------------------------------------------------------------------

def do_restore(docs_dir: Path) -> None:
    """Undo all renames recorded in _rst_override_state.json (reverse order)."""
    docs_dir = Path(docs_dir)
    state_path = _state_path(docs_dir)

    if not state_path.exists():
        return  # no-op

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"swap_sources: cannot read state file {state_path}: {exc}. "
            f"Inspect or delete it manually."
        ) from exc

    version = state.get("version")
    if version != STATE_VERSION:
        raise RuntimeError(
            f"swap_sources: state file version {version!r} does not match "
            f"expected {STATE_VERSION!r}. Inspect {state_path} manually."
        )

    overrides = state.get("overrides", [])

    for entry in reversed(overrides):
        if not isinstance(entry, dict) or "rst_from" not in entry or "rst_to" not in entry:
            raise RuntimeError(
                f"swap_sources: malformed entry in {state_path}: {entry!r}. "
                f"Inspect manually."
            )
        rst_from = docs_dir / entry["rst_from"]  # original source (rst-prefixed)
        rst_to = docs_dir / entry["rst_to"]      # current location (plain .rst)
        if rst_to.exists():
            os.rename(rst_to, rst_from)
        else:
            print(
                f"swap_sources: WARNING — expected overridden file not found: {rst_to}",
                file=sys.stderr,
            )

    # Clean up state and exclude files
    state_path.unlink(missing_ok=True)
    exclude_path = _exclude_path(docs_dir)
    exclude_path.unlink(missing_ok=True)

    print(f"swap_sources: restored {len(overrides)} RST override(s).", file=sys.stderr)


# ---------------------------------------------------------------------------
# do_dry_run / do_status
# ---------------------------------------------------------------------------

def do_dry_run(docs_dir: Path) -> None:
    """Print what would be activated without making any changes."""
    docs_dir = Path(docs_dir)
    override_list = parse_override_list(docs_dir / OVERRIDE_LIST_FILE)
    if not override_list:
        print("(dry-run) No stems in override list.")
        return

    for stem in override_list:
        rst_from, rst_to, md_path = _resolve_stem_paths(docs_dir, stem)
        issues = []
        if not rst_from.exists():
            issues.append("rst- source missing")
        if not md_path.exists():
            issues.append("MD missing")
        if rst_to.exists():
            issues.append("COLLISION: plain .rst already exists")
        if issues:
            print(f"  SKIP  {stem}: {', '.join(issues)}")
        else:
            rel_dir = rst_from.parent.relative_to(docs_dir) if rst_from.parent != docs_dir else "."
            print(f"  APPLY  {rst_from.name} → {rst_to.name}  (in {rel_dir})")


def do_status(docs_dir: Path) -> None:
    """Show current override state."""
    docs_dir = Path(docs_dir)
    state_path = _state_path(docs_dir)
    if not state_path.exists():
        print("swap_sources: no active RST overrides.")
        return

    state = json.loads(state_path.read_text(encoding="utf-8"))
    overrides = state.get("overrides", [])
    print(f"swap_sources: {len(overrides)} RST override(s) currently active:")
    for entry in overrides:
        print(f"  {entry['rst_from']} → {entry['rst_to']}  (excludes {entry['md_excluded']})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Activate rst-prefixed RST files as the build source for stems "
                    "listed in docs/_rst_overrides.txt."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--swap", action="store_true",
                       help="Apply RST overrides (rename rst-<stem>.rst → <stem>.rst)")
    group.add_argument("--restore", action="store_true",
                       help="Restore original files after a previous --swap")
    group.add_argument("--dry-run", action="store_true",
                       help="Show what would be applied")
    group.add_argument("--status", action="store_true",
                       help="Show current override state")

    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=None,
        help="Path to docs/ directory (default: auto-detected from script location)",
    )

    args = parser.parse_args(argv)

    if args.docs_dir is None:
        # Default: repo_root/docs where repo_root = parent of scripts/
        repo_root = Path(__file__).resolve().parent.parent
        docs_dir = repo_root / "docs"
    else:
        docs_dir = args.docs_dir.resolve()

    if not docs_dir.is_dir():
        parser.error(f"docs directory not found: {docs_dir}")

    if args.swap:
        do_swap(docs_dir)
    elif args.restore:
        do_restore(docs_dir)
    elif args.dry_run:
        do_dry_run(docs_dir)
    elif args.status:
        do_status(docs_dir)


if __name__ == "__main__":
    main()
