#!/usr/bin/env python3
"""import_myst.py — Import converted MD files from myst/* branches.

Usage
-----
  python scripts/import_myst.py --source myst/current --all
  python scripts/import_myst.py --source myst/current --pages quick-start configuration/firewall/zone
  python scripts/import_myst.py --source myst/current --all --force
  python scripts/import_myst.py --source myst/current --all --dry-run

Each imported file is written as md-{name}.md alongside the existing RST
file. Importing does not activate a page — use swap_sources.py for that.
"""

import argparse
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def git_show(ref: str, path: str) -> Optional[bytes]:
    """Run `git show {ref}:{path}` and return raw bytes, or None on error."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def list_myst_files(source: str) -> list[str]:
    """Return list of MD stems from `git ls-tree -r --name-only {source} -- docs/`.

    Stems are relative to docs/ with the .md extension stripped.
    Only .md files are returned.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", source, "--", "docs/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"import_myst: git ls-tree {source!r} failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )

    stems = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.endswith(".md"):
            continue
        # Strip leading "docs/" prefix and .md extension
        rel = line[len("docs/"):] if line.startswith("docs/") else line
        stem = rel[:-3]  # strip ".md"
        stems.append(stem)
    return stems


def list_rst_files(docs_dir: Path) -> set[str]:
    """Return set of stems (relative to docs_dir, no extension) for all *.rst files."""
    build_dir = (docs_dir / "_build").resolve()
    stems = set()
    for rst in docs_dir.rglob("*.rst"):
        try:
            rst.resolve().relative_to(build_dir)
            continue  # inside _build/, skip
        except ValueError:
            pass
        rel = rst.relative_to(docs_dir)
        stem = str(rel)[:-4]  # strip ".rst"
        stems.add(stem)
    return stems


def import_page(stem: str, md_content: bytes, docs_dir: Path, force: bool) -> bool:
    """Write md-{name}.md for the given stem.

    - Creates parent dirs as needed.
    - Skips (returns False) if identical content already exists.
    - Without --force: warns and skips (returns False) if different content exists.
    - With --force: overwrites (returns True).
    - Returns True on successful write.

    Refuses (raises ValueError) if *stem* would resolve outside *docs_dir*.
    """
    p = Path(stem)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"import_myst: refusing unsafe stem {stem!r}")
    name = p.name
    parent = p.parent
    if str(parent) == ".":
        target_dir = docs_dir
    else:
        target_dir = docs_dir / parent

    dest = target_dir / f"md-{name}.md"
    docs_root = docs_dir.resolve()
    if not dest.resolve().parent.is_relative_to(docs_root):
        raise ValueError(f"import_myst: refusing stem {stem!r} — escapes docs/")

    if dest.exists():
        existing = dest.read_bytes()
        if existing == md_content:
            return False  # identical — skip silently
        if not force:
            warnings.warn(
                f"import_myst: {dest} exists with different content; "
                f"use --force to overwrite",
                stacklevel=2,
            )
            return False
        # force=True — fall through to write

    target_dir.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(md_content)
    return True


# ---------------------------------------------------------------------------
# do_import
# ---------------------------------------------------------------------------

def do_import(
    source: str,
    pages: Optional[list],
    all_pages: bool,
    force: bool,
    dry_run: bool,
    docs_dir: Path,
) -> None:
    """Orchestrate import from source branch.

    If --all: list MD files from source, intersect with RST stems in docs_dir,
    import only those that have an RST counterpart.
    If --pages: import only the listed stems.
    """
    docs_dir = Path(docs_dir)

    if all_pages:
        myst_stems = list_myst_files(source)
        rst_stems = list_rst_files(docs_dir)
        candidate_stems = [s for s in myst_stems if s in rst_stems]
    else:
        candidate_stems = list(pages or [])

    imported = 0
    skipped = 0
    would_import = 0

    for stem in candidate_stems:
        # Path inside the branch: docs/{stem}.md
        ref_path = f"docs/{stem}.md"
        content = git_show(source, ref_path)
        if content is None:
            print(
                f"import_myst: WARNING — could not fetch {source}:{ref_path}",
                file=sys.stderr,
            )
            skipped += 1
            continue

        if dry_run:
            print(f"  (dry-run) would import {stem}")
            would_import += 1
            continue

        wrote = import_page(stem, content, docs_dir, force)
        if wrote:
            imported += 1
        else:
            skipped += 1

    if dry_run:
        print(
            f"import_myst: (dry-run) would import {would_import}, "
            f"skipped {skipped}.",
            file=sys.stderr,
        )
    else:
        print(
            f"import_myst: imported {imported}, skipped {skipped}.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Import MyST MD files from a myst/* branch with md- prefix."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Git ref to import from (e.g. myst/current)",
    )

    pages_group = parser.add_mutually_exclusive_group(required=True)
    pages_group.add_argument(
        "--pages",
        nargs="+",
        metavar="STEM",
        help="Specific page stems to import (e.g. quick-start configuration/firewall/zone)",
    )
    pages_group.add_argument(
        "--all",
        action="store_true",
        dest="all_pages",
        help="Import all MD files that have a matching RST counterpart",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing md- files even if content differs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing files",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=None,
        help="Path to docs/ directory (default: auto-detected from script location)",
    )

    args = parser.parse_args(argv)

    if args.docs_dir is None:
        docs_dir = DOCS_DIR
    else:
        docs_dir = args.docs_dir.resolve()

    if not docs_dir.is_dir():
        parser.error(f"docs directory not found: {docs_dir}")

    do_import(
        source=args.source,
        pages=args.pages,
        all_pages=args.all_pages,
        force=args.force,
        dry_run=args.dry_run,
        docs_dir=docs_dir,
    )


if __name__ == "__main__":
    main()
