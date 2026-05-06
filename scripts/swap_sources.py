#!/usr/bin/env python3
"""swap_sources.py — Pre-build swap/restore for incremental RST-to-MyST migration.

Usage
-----
  python scripts/swap_sources.py --swap          # rename md-{name}.md → {name}.md
  python scripts/swap_sources.py --restore       # undo renames
  python scripts/swap_sources.py --dry-run       # show what would be swapped
  python scripts/swap_sources.py --status        # show current swap state
  python scripts/swap_sources.py --swap --docs-dir /path/to/docs

Swap list
---------
  docs/_swap.txt — one stem per line, relative to docs/, comments (#) skipped.
  Example:
      # migrated pages
      configuration/firewall/zone
      quick-start

State files (in docs/_build/, gitignored)
-----------------------------------------
  _swap_state.json  — records completed renames
  _swap_exclude.txt — RST paths to pass to Sphinx exclude_patterns
"""

import argparse
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILE = "_swap_state.json"
EXCLUDE_FILE = "_swap_exclude.txt"
SWAP_LIST_FILE = "_swap.txt"
STATE_VERSION = 1


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_swap_list(path: Path) -> list:
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
    """Return (md_from, md_to, rst_path) as absolute Paths for a given stem."""
    p = Path(stem)
    name = p.name
    parent = p.parent  # may be PosixPath('.')
    if str(parent) == ".":
        target_dir = docs_dir
    else:
        target_dir = docs_dir / parent

    md_from = target_dir / f"md-{name}.md"    # source: md-prefixed
    md_to = target_dir / f"{name}.md"          # destination: plain .md
    rst_path = target_dir / f"{name}.rst"      # RST that will be excluded
    return md_from, md_to, rst_path


# ---------------------------------------------------------------------------
# do_swap
# ---------------------------------------------------------------------------

def do_swap(docs_dir: Path) -> None:
    """Rename md-{name}.md → {name}.md for each stem in _swap.txt.

    Validates collisions, records state, writes exclude file.
    Rolls back all completed renames on any failure.
    """
    docs_dir = Path(docs_dir)
    swap_list = parse_swap_list(docs_dir / SWAP_LIST_FILE)
    if not swap_list:
        print("swap_sources: no stems in swap list, nothing to do.", file=sys.stderr)
        return

    # Stale state: warn and auto-restore first
    state_path = _state_path(docs_dir)
    if state_path.exists():
        print(
            "swap_sources: WARNING — stale swap state detected. Auto-restoring before new swap.",
            file=sys.stderr,
        )
        do_restore(docs_dir)

    # Validate all stems before touching the filesystem
    planned = []  # list of (md_from, md_to, rst_path, stem)
    for stem in swap_list:
        md_from, md_to, rst_path = _resolve_stem_paths(docs_dir, stem)

        if not md_from.exists():
            print(
                f"swap_sources: skipping {stem!r} — md- source file not found: {md_from}",
                file=sys.stderr,
            )
            continue

        if not rst_path.exists():
            print(
                f"swap_sources: skipping {stem!r} — RST file not found: {rst_path}",
                file=sys.stderr,
            )
            continue

        if md_to.exists():
            raise RuntimeError(
                f"collision: both RST and unprefixed .md exist for stem {stem!r}. "
                f"Remove {md_to} before swapping."
            )

        planned.append((md_from, md_to, rst_path, stem))

    # Execute renames with rollback on failure
    completed = []  # list of (md_from, md_to) that succeeded
    try:
        for md_from, md_to, rst_path, stem in planned:
            os.rename(md_from, md_to)
            completed.append((md_from, md_to))
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
    swaps = []
    exclude_lines = []
    for md_from, md_to, rst_path, stem in planned:
        rel_from = md_from.relative_to(docs_dir)
        rel_to = md_to.relative_to(docs_dir)
        rel_rst = rst_path.relative_to(docs_dir)
        swaps.append({
            "stem": stem,
            "md_from": str(rel_from),
            "md_to": str(rel_to),
            "rst_excluded": str(rel_rst),
        })
        exclude_lines.append(str(rel_rst))

    state = {"version": STATE_VERSION, "swaps": swaps}
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _exclude_path(docs_dir).write_text("\n".join(exclude_lines) + "\n", encoding="utf-8")

    print(f"swap_sources: swapped {len(completed)} file(s).", file=sys.stderr)


# ---------------------------------------------------------------------------
# do_restore
# ---------------------------------------------------------------------------

def do_restore(docs_dir: Path) -> None:
    """Undo all renames recorded in _swap_state.json (reverse order)."""
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

    swaps = state.get("swaps", [])

    for entry in reversed(swaps):
        if not isinstance(entry, dict) or "md_from" not in entry or "md_to" not in entry:
            raise RuntimeError(
                f"swap_sources: malformed entry in {state_path}: {entry!r}. "
                f"Inspect manually."
            )
        md_from = docs_dir / entry["md_from"]   # original source (md-prefixed)
        md_to = docs_dir / entry["md_to"]        # current location (plain .md)
        if md_to.exists():
            os.rename(md_to, md_from)
        else:
            print(
                f"swap_sources: WARNING — expected swapped file not found: {md_to}",
                file=sys.stderr,
            )

    # Clean up state and exclude files
    state_path.unlink(missing_ok=True)
    exclude_path = _exclude_path(docs_dir)
    exclude_path.unlink(missing_ok=True)

    print(f"swap_sources: restored {len(swaps)} file(s).", file=sys.stderr)


# ---------------------------------------------------------------------------
# do_dry_run / do_status
# ---------------------------------------------------------------------------

def do_dry_run(docs_dir: Path) -> None:
    """Print what would be swapped without making any changes."""
    docs_dir = Path(docs_dir)
    swap_list = parse_swap_list(docs_dir / SWAP_LIST_FILE)
    if not swap_list:
        print("(dry-run) No stems in swap list.")
        return

    for stem in swap_list:
        md_from, md_to, rst_path = _resolve_stem_paths(docs_dir, stem)
        issues = []
        if not md_from.exists():
            issues.append("md- source missing")
        if not rst_path.exists():
            issues.append("RST missing")
        if md_to.exists():
            issues.append("COLLISION: plain .md already exists")
        if issues:
            print(f"  SKIP  {stem}: {', '.join(issues)}")
        else:
            print(f"  SWAP  {md_from.name} → {md_to.name}  (in {md_from.parent.relative_to(docs_dir) if md_from.parent != docs_dir else '.'})")


def do_status(docs_dir: Path) -> None:
    """Show current swap state."""
    docs_dir = Path(docs_dir)
    state_path = _state_path(docs_dir)
    if not state_path.exists():
        print("swap_sources: no active swap state.")
        return

    state = json.loads(state_path.read_text(encoding="utf-8"))
    swaps = state.get("swaps", [])
    print(f"swap_sources: {len(swaps)} file(s) currently swapped:")
    for entry in swaps:
        print(f"  {entry['md_from']} → {entry['md_to']}  (excludes {entry['rst_excluded']})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Swap md-prefixed MyST files in place of RST files before Sphinx builds."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--swap", action="store_true", help="Perform swap")
    group.add_argument("--restore", action="store_true", help="Restore original files")
    group.add_argument("--dry-run", action="store_true", help="Show what would be swapped")
    group.add_argument("--status", action="store_true", help="Show current swap state")

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
