"""Deploy-blocking sanity gates (spec §7.1).

Gates: file-count vs plan cap (<= 80% of 100k), per-file < 25 MiB, index.html +
critical-page presence, page-count delta vs previous deploy, canonical URLs must
start with the https://docs.vyos.io/en/<slug>/ prefix, declared PDF present,
Pagefind non-empty.
Exit 0 = deployable; exit 1 = blocked (one line per failed gate on stderr).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FILE_CAP = 100_000
CAP_FRACTION = 0.8
MAX_FILE = 25 * 1024 * 1024
COUNT_DELTA_MIN_RATIO = 0.5  # new build must have >= 50% of previous page count
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"')


def _fail(msgs: list[str], msg: str) -> None:
    msgs.append(msg)
    print(f"GATE-FAIL: {msg}", file=sys.stderr)


def run(artifact: Path, slug: str, versions: Path, previous_meta: Path | None,
        critical: list[str]) -> int:
    fails: list[str] = []
    root = artifact / "en" / slug
    manifest = json.loads(versions.read_text())
    entry = next((v for v in manifest["versions"] if v["slug"] == slug), None)
    if entry is None:
        _fail(fails, f"slug {slug} not in versions.json")
        return 1

    files = [p for p in artifact.rglob("*") if p.is_file()]
    if len(files) > FILE_CAP * CAP_FRACTION:
        _fail(fails, f"file count {len(files)} > 80% of {FILE_CAP} cap")
    for p in files:
        if p.stat().st_size > MAX_FILE:
            _fail(fails, f"{p.relative_to(artifact)} exceeds 25 MiB")

    for rel in ["index.html", *critical]:
        if not (root / rel).is_file():
            _fail(fails, f"critical page missing: en/{slug}/{rel}")

    pagefind = root / "pagefind"
    if not pagefind.is_dir() or not any(pagefind.iterdir()):
        _fail(fails, "Pagefind index missing or empty")

    if entry.get("pdf"):
        expected = artifact / entry["pdf"].lstrip("/")
        if not expected.is_file():
            _fail(fails, f"declared PDF missing: {entry['pdf']}")

    pages = [p for p in root.rglob("*.html")]
    if previous_meta is not None and previous_meta.is_file():
        prev = json.loads(previous_meta.read_text())
        if prev.get("page_count") and len(pages) < prev["page_count"] * COUNT_DELTA_MIN_RATIO:
            _fail(fails, f"page count collapsed: {len(pages)} vs previous {prev['page_count']}")

    want = f"https://docs.vyos.io/en/{slug}/"
    for p in pages:
        m = CANONICAL_RE.search(p.read_text(errors="ignore"))
        if m is None:
            _fail(fails, f"missing canonical link in en/{slug}/{p.relative_to(root)}")
            break  # one example is enough to block
        if not m.group(1).startswith(want):
            _fail(fails, f"bad canonical in en/{slug}/{p.relative_to(root)}: {m.group(1)}")
            break  # one example is enough to block

    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--versions", type=Path, required=True)
    ap.add_argument("--previous-meta", type=Path, default=None)
    ap.add_argument("--critical-list", type=Path,
                    default=Path("scripts/docs_gates/critical-pages.txt"))
    a = ap.parse_args()
    critical = [line.strip() for line in a.critical_list.read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    return run(a.artifact, a.slug, a.versions, a.previous_meta, critical)


if __name__ == "__main__":
    raise SystemExit(main())
