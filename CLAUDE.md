# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VyOS user documentation, built with Sphinx and hosted on Read the Docs at https://docs.vyos.io. Sources are MyST Markdown (`.md`) for migrated pages and RST (`.rst`) for the rest. Both formats are first-class to Sphinx; MD is the canonical source for any page that has been migrated, and RST is the canonical source for pages that haven't.

A small swap mechanism exists for the rare case where a maintainer needs to render the legacy RST version of a page that already has an MD primary — see `RST override mechanism` below. The override list is empty by default.

## Build

```bash
# Docker (recommended — bundles Sphinx and the MyST/RTD plugin set)
docker build -t vyos/vyos-documentation docker
docker run --rm -it -v "$(pwd)":/vyos -w /vyos/docs \
  -e GOSU_UID=$(id -u) -e GOSU_GID=$(id -g) \
  vyos/vyos-documentation make html

# Live-reload server on port 8000
docker run --rm -it -p 8000:8000 -v "$(pwd)":/vyos -w /vyos/docs \
  -e GOSU_UID=$(id -u) -e GOSU_GID=$(id -g) \
  vyos/vyos-documentation make livehtml

# Local (Python 3, see requirements.txt for pinned versions)
pip install -r requirements.txt
cd docs && make html
```

Output: `docs/_build/html/`.

## Tests

`tests/test_swap_sources.py` imports `swap_sources` from `scripts/`, which is
not on `PYTHONPATH` by default. Run from the `tests/` directory:

```bash
cd tests
PYTHONPATH=../scripts python -m pytest                    # all tests
PYTHONPATH=../scripts python -m pytest test_swap_sources.py  # single file
```

## Lint

The repo doesn't ship a local lint config or pin a linter binary. CI runs
`vyoslinter` (`doc-linter.py` from the `vyos/.github` repo, via the
`lint-doc.yml` workflow) on changed files only — see the CI section
below. For local checks, manually grep for the rules in
[Source conventions](#source-conventions) (line length, address space,
suppression markers).

## Branches and versions

One long-lived branch per VyOS release line. Branch names are constellations sorted by area:

| Branch | VyOS version |
|--------|--------------|
| `current` | rolling / 1.5+ (default branch — all new docs target this) |
| `circinus` | 1.5.x |
| `sagitta` | 1.4.x |
| `equuleus` | 1.3.x (legacy) |
| `crux` | 1.2.x (legacy) |

PRs target `current`. After merge, request backports via Mergify comments on the PR:

```
@Mergifyio backport circinus
@Mergifyio backport sagitta
```

Mergify is configured at the org level (no `.mergify.yml` in the repo). The PR template has a `## Backport` section to declare intent.

## Architecture

### Sphinx config (`docs/conf.py`)

- `source_suffix = ['.rst', '.md']` — both formats build into the same site.
- MyST extensions: `colon_fence`, `deflist`, `fieldlist`, `substitution`.
- `myst_fence_as_directive = ["cfgcmd", "opcmd", "cmdincludemd"]` — MyST fences with these names get parsed as if they were RST directives. This is how command pages stay format-portable.
- Custom modules live in `docs/_ext/` (only files listed in `extensions = [...]` in `conf.py` are actual Sphinx extensions; the others are support scripts loaded ad hoc):
  - `vyos.py` (Sphinx extension, registered as `vyos`) — defines the `cfgcmd`, `opcmd`, `cmdinclude`, `cmdincludemd`, `cfgcmdlist`, `opcmdlist` directives and `cfgcmd`/`opcmd` roles that drive command coverage tracking.
  - `autosectionlabel.py` (Sphinx extension, registered as `autosectionlabel`) — connects to `doctree-read` to register sections as labels.
  - `testcoverage.py` — standalone helper that reads VyOS XML command definitions and exposes coverage stats; not a Sphinx extension.
  - `releasenotes.py` — standalone release-notes/changelog generator script; not a Sphinx extension.

### RST override mechanism

For pages that have been migrated from RST to MyST:

- `docs/<subdir>/<page>.md` — canonical MD source (primary).
- `docs/<subdir>/rst-<page>.rst` — preserved RST sibling kept around as an override
  option. The `rst-` prefix applies only to the **filename**, not the directory, so
  `configuration/firewall/zone` maps to `docs/configuration/firewall/rst-zone.rst`
  (not `docs/rst-configuration/firewall/zone.rst`). Excluded from the build by
  `exclude_patterns` in `conf.py`.
- `docs/_rst_overrides.txt` — one stem per line, relative to `docs/` (e.g.
  `configuration/firewall/zone`). Pages listed here render from
  `rst-<page>.rst` instead of `<page>.md`. Empty by default.
- `scripts/swap_sources.py` — CLI for `--swap` (apply overrides), `--restore`,
  `--dry-run`, `--status`. Build-time state lands in
  `docs/_build/_rst_override_state.json` and `docs/_build/_md_exclude.txt`
  (gitignored).

For pages that have NOT been migrated:

- `docs/<page>.rst` — original RST, no `rst-` prefix, no MD sibling.

**Editing rules:**
- Migrated page (has `<page>.md`): edit the `.md`. Don't touch the `rst-`-prefixed sibling unless you're maintaining a parallel RST version that someone has flagged in `_rst_overrides.txt`.
- Non-migrated page (RST-only): edit the `.rst`.
- New page: write it as `.md` from the start. The `md-` prefix that earlier MyST migration commits used is gone — never add it.

Running `make html` runs the swap automatically (it's a no-op when the override list is empty, which is the default state).

### Command directives

`.. cfgcmd::`, `.. opcmd::`, and `.. cmdinclude::` are the VyOS-specific Sphinx directives in RST. They are tracked for command coverage — do **not** convert them to plain `.. code-block::`. In MyST the same directives are written as fenced blocks: ```` ```{cfgcmd} set system ... ```` (enabled by `myst_fence_as_directive`). The MyST include directive is named `cmdincludemd` (not `cmdinclude`) so that template parsing follows MyST rules in MD pages and RST rules in RST pages — pick `cmdinclude` in `.rst`, `cmdincludemd` in `.md`.

## Source conventions

### RST heading hierarchy

```
##### Title (overline+underline, one per file)
***** Chapters
===== Sections
----- Subsections
^^^^^ Subsubsections
""""" Paragraphs
```

The first heading in every RST file uses `#` overline+underline. Field lists (e.g., `:lastproofread:`) or labels may precede it.

### Formatting

- 80-character line limit (exception: inside `.. code-block::` / fenced code blocks — `<pre>` preserves source verbatim).
- American English.
- Indent with 2 spaces.
- Blank lines around headings.
- Inline code: use double backticks per RST convention (the [Inline markup](https://docutils.sourceforge.io/docs/user/rst/quickref.html#inline-markup) section of the docutils quick reference).

### IP addresses (linter-enforced)

Allowed without suppression:
- RFC 5737 IPv4 docs: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- RFC 3849 IPv6 docs: `2001:db8::/32`
- RFC 1918 private ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), `0.0.0.0/0`

Allowed ASN: `64496-64511` (16-bit), `65536-65551` (32-bit).
Allowed MAC ranges: `00-53-00`–`00-53-FF` (unicast), `90-10-00`–`90-10-FF` (multicast).

**Requires `stop/start_vyoslinter` suppression:**
- Real public IPs (e.g., `8.8.8.8` for DNS examples).
- NAT64 well-known prefix `64:ff9b::/96`.
- Lines over 80 chars (URLs, certificate fingerprints).

### Linter suppression markers

```rst
.. stop_vyoslinter

.. code-block:: none

   content with real IPs or long lines here

.. start_vyoslinter
```

In MyST `.md` files use the comment form `% stop_vyoslinter` / `% start_vyoslinter` for top-level Markdown content. Inside `{eval-rst}` blocks (where the embedded content is parsed as RST) keep the RST form `.. stop_vyoslinter` / `.. start_vyoslinter` — the linter scans the source line literally and only the form that matches the surrounding parser is recognized. Likewise, `.txt` template files (included via `{include}` or `cmdincludemd`) keep the RST form.

Markers must always come in pairs. Indentation may match the surrounding directive (indented inside a block) or sit at column 0 (top-level) — both are valid.

### Configuration page structure

1. **Theory** — what it is, when to use it, relevant RFCs.
2. **Configuration** — all CLI options as `.. cfgcmd::` (RST) or ```` ```{cfgcmd} ```` (MD).
3. **Examples** — practical configurations with topology diagrams.
4. **Known issues** — problems and workarounds.
5. **Debugging** — log collection, `show` commands, state indicators.

### `.. TODO::` markers

Two valid uses:
1. **Tracking** marker on pages that still need `cfgcmd`/`opcmd` conversion — intentional.
2. **Stale** marker on pages that already have full content — should be removed.

A PR that both adds and removes TODOs is not contradictory; intent matters.

## LLM-Facing Files (`llms.txt`, `llms-full.txt`)

Both files are regenerated on every `html` and `readthedocs` builder run.
The `dirhtml` builder is intentionally skipped — production publishes
only via `html`/`readthedocs`, and we don't render llms.txt for builds
we don't ship. Local `make dirhtml` is a developer convenience and
won't emit `llms.txt`.

Files are shipped at the docs root for each version
(`https://docs.vyos.io/en/<version>/llms.txt`, `.../llms-full.txt`).

- **`llms-full.txt`** — auto-generated by the `sphinx_llms_txt` extension from
  the full corpus. No curation; configured by `llms_txt_file = False` (which
  disables the extension's *index* output, not the full output).
- **`llms.txt`** — curated overview rendered at build time from
  `docs/_templates/llms.txt.j2`. URLs and the version line are interpolated
  from `html_baseurl` and `release` so the file always matches the branch.
  The render lives in `_write_llms_txt(app, exception)` in `docs/conf.py`,
  wired via `app.connect('build-finished', ...)`.

When adding new top-level sections to the docs, add a corresponding bullet in
`docs/_templates/llms.txt.j2`. Branch-specific differences (e.g. sagitta has
no `vpp/` or `contributing/index`) live in that branch's copy of the template.

## Read the Docs Layout

RTD slugs as of 2026-05-04 (verified via API):

| Slug | Verbose | Branch | Role |
|---|---|---|---|
| `rolling` | current | `current` | canonical for rolling/next major |
| `1.5` | circinus | `circinus` | canonical for current LTS |
| `1.4` | sagitta | `sagitta` | canonical for previous LTS |
| `1.3`, `1.2` | equuleus, crux | older | canonical for older releases |

URL-level redirect aliases (resolve to the canonicals above):
`/en/latest/* → /en/rolling/`, `/en/lts/* → /en/1.5/`,
`/en/stable/* → /en/lts/`, `/en/circinus*`, `/en/sagitta*`,
`/en/equuleus*`, `/en/crux*` → numeric slugs.

`html_baseurl` per branch must point at the canonical (numeric or `rolling`),
not the alias, so `<link rel="canonical">` and the sitemap match what RTD
serves and crawlers skip the redirect hop.

## CI

- **vyoslinter** (`doc-linter.py` from the `vyos/.github` repo, run via `lint-doc.yml`) — line length and IP rules, on changed files only.
- **Sphinx build** — runs on Read the Docs for every PR; preview URL appears as a check.
- **CLA check** — contributors must sign the VyOS CLA before merge.
- **Conflict check** — fails the PR if it doesn't merge cleanly into base.
