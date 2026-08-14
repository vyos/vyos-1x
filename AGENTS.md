# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project

VyOS user documentation, built with Sphinx and hosted on Read the Docs
at https://docs.vyos.io. Sources are MyST Markdown (`.md`) — the
migration off RST is complete, `source_suffix` in `docs/conf.py` is
`['.md']` only, and all canonical pages are `.md`.

Pre-migration RST originals are archived under `docs/_rst_legacy/` for
reference only — they are excluded from the build, not consulted by
Sphinx, and not indexed by Context7. Do not edit them.

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

## Lint

The repo doesn't ship a local lint config or pin a linter binary. CI
runs `scripts/doc-linter.py` (in-repo, invoked from
`.github/workflows/lint-doc.yml`) on changed files only, scoped to
`docs/` — see the CI section below. For local checks, manually grep
for the rules in [Source conventions](#source-conventions) (line
length, address space, suppression markers).

## Branches and versions

One long-lived branch per VyOS release line. Branch names are
constellations sorted by area:

| Branch | VyOS version |
|--------|--------------|
| `rolling` | rolling / 1.5+ (default branch — all new docs target this) |
| `circinus` | 1.5.x |
| `sagitta` | 1.4.x |
| `equuleus` | 1.3.x (legacy) |
| `crux` | 1.2.x (legacy) |

PRs target `rolling`. After merge, request backports via a **post-merge
comment** on the PR. Multiple branches go in a single command,
space-separated:

```text
@Mergifyio backport circinus sagitta
```

Only **Maintainers team members** can invoke `@Mergifyio` commands —
Mergify silently drops commands from anyone outside the team (no error
reply). If a backport doesn't trigger, check team membership first. Ask
a Maintainer to post the comment on your behalf.

Mergify only reads commands from **PR comments** — mentions in the PR
body are ignored.
Mergify is configured at the org level (no `.mergify.yml` in the repo).
The PR template has a `## Backport` section to declare intent, but that
does not trigger the backport; the comment does.

## Architecture

### Sphinx config (`docs/conf.py`)

- `source_suffix = ['.md']` — Sphinx only picks up MyST Markdown
  sources. The pre-migration RST originals under `docs/_rst_legacy/`
  are not registered as a source extension and are excluded from the
  build.
- MyST extensions: `colon_fence`, `deflist`, `fieldlist`, `substitution`.
- `myst_fence_as_directive = ["cfgcmd", "opcmd", "cmdincludemd"]` —
  MyST fences with these names get parsed as if they were RST
  directives. This is how command pages stay format-portable.
- Custom modules live in `docs/_ext/` (only files listed in
  `extensions = [...]` in `conf.py` are actual Sphinx extensions; the
  others are support scripts loaded ad hoc):
  - `vyos.py` (Sphinx extension, registered as `vyos`) — defines the
    `cfgcmd`, `opcmd`, `cmdinclude`, `cmdincludemd`, `cfgcmdlist`,
    `opcmdlist` directives and `cfgcmd`/`opcmd` roles that drive
    command coverage tracking.
  - `autosectionlabel.py` (Sphinx extension, registered as
    `autosectionlabel`) — connects to `doctree-read` to register
    sections as labels.
  - `testcoverage.py` — standalone helper that reads VyOS XML command
    definitions and exposes coverage stats; not a Sphinx extension.
  - `releasenotes.py` — standalone release-notes/changelog generator
    script; not a Sphinx extension.

### Source files

- `docs/<subdir>/<page>.md` — canonical MyST source for every page.
  The migration off RST is complete.
- `docs/_include/<name>.txt` — shared RST snippets included into MyST
  pages via `cmdincludemd`. Their content is parsed as RST so the
  legacy templates keep working unchanged.
- `docs/_rst_legacy/<subdir>/rst-<page>.rst` — archived pre-migration
  RST originals. Excluded from the Sphinx build and from the Context7
  index. Reference only.

**Editing rules:**

- Existing page: edit the `.md`. Do not touch the archived original
  under `_rst_legacy/`.
- New page: write it as `.md` from the start. The `md-` prefix that
  earlier MyST migration commits used is gone — never add it.
- `_include/*.txt` snippets stay RST — see the next section.

### Command directives

The VyOS-specific Sphinx directives are `cfgcmd`, `opcmd`, and
`cmdincludemd`. In MyST pages they are written as fenced code blocks
with `{cfgcmd}`, `{opcmd}`, or `{cmdincludemd}` as the info string
(enabled by `myst_fence_as_directive`). They are tracked for command
coverage — do **not** replace them with plain `text` or `bash`
fences.

For RST contexts (`{eval-rst}` blocks and `_include/*.txt` snippets),
the directives are written `.. cfgcmd::`, `.. opcmd::`, and
`.. cmdinclude::`. `cmdinclude` is the RST-side include form;
`cmdincludemd` is the MyST-side form. They resolve to the same
include logic but follow the host file's parser, so pick
`cmdinclude` in `.txt`/RST contexts and `cmdincludemd` in `.md`.

## Source conventions

### RST heading hierarchy

Applies only to RST contexts — `_include/*.txt` snippets and
`{eval-rst}` blocks inside MyST pages. Canonical pages are MyST and
use ATX `#` / `##` / `###` etc. headings; this hierarchy does not
apply to them.

```
##### Title (overline+underline, one per file)
***** Chapters
===== Sections
----- Subsections
^^^^^ Subsubsections
""""" Paragraphs
```

The first heading in every embedded RST snippet that introduces a
title uses `#` overline+underline. Field lists (e.g.,
`:lastproofread:`) or labels may precede it.

### Formatting

- 80-character line limit (exception: inside `.. code-block::` /
  fenced code blocks — `<pre>` preserves source verbatim).
- American English.
- Indent with 2 spaces.
- Blank lines around headings.
- Inline code: single backticks in MyST (the canonical form). Double
  backticks only inside `{eval-rst}` blocks and `_include/*.txt`
  snippets, per RST convention.

### IP addresses (linter-enforced)

Allowed without suppression:
- RFC 5737 IPv4 docs: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- RFC 3849 IPv6 docs: `2001:db8::/32`
- RFC 1918 private ranges: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), `0.0.0.0/0`

Allowed ASN: `64496-64511` (16-bit), `65536-65551` (32-bit).
Allowed MAC ranges: `00-53-00`–`00-53-FF` (unicast),
`90-10-00`–`90-10-FF` (multicast).

**Requires `stop/start_vyoslinter` suppression:**

- Real public IPs (e.g., a DNS server's address in a DNS forwarder
  example, or an upstream peer's address in an EBGP example).
- NAT64 well-known prefix `64:ff9b::/96`.
- Lines over 80 chars (URLs, certificate fingerprints).

### Linter suppression markers

```rst
.. stop_vyoslinter

.. code-block:: none

   content with real IPs or long lines here

.. start_vyoslinter
```

In MyST `.md` files use the comment form `% stop_vyoslinter` /
`% start_vyoslinter` for top-level Markdown content. Inside
`{eval-rst}` blocks (where the embedded content is parsed as RST)
keep the RST form `.. stop_vyoslinter` / `.. start_vyoslinter` — the
linter scans the source line literally and only the form that matches
the surrounding parser is recognized. Likewise, `.txt` template files
(included via `{include}` or `cmdincludemd`) keep the RST form.

Markers must always come in pairs. Indentation may match the
surrounding directive (indented inside a block) or sit at column 0
(top-level) — both are valid.

### Configuration page structure

1. **Theory** — what it is, when to use it, relevant RFCs.
2. **Configuration** — all CLI options as `.. cfgcmd::` directives
   (in RST contexts) or `{cfgcmd}` fenced code blocks (in MD).
3. **Examples** — practical configurations with topology diagrams.
4. **Known issues** — problems and workarounds.
5. **Debugging** — log collection, `show` commands, state indicators.

### `{todo}` markers

In MyST pages, write TODO markers as `{todo}` fenced directives
(triple-backtick or `:::` fenced blocks with `{todo}` as the info
string). In RST contexts (`{eval-rst}` blocks, `_include/*.txt`
snippets) use the RST form `.. TODO::`. Two valid uses:

1. **Tracking** marker on pages that still need `cfgcmd`/`opcmd`
   conversion — intentional.
2. **Stale** marker on pages that already have full content — should
   be removed.

A PR that both adds and removes TODOs is not contradictory; intent matters.

## LLM-Facing Files (`llms.txt`, `llms-full.txt`)

Both files are regenerated on every `html` and `readthedocs` builder run.
The `dirhtml` builder is intentionally skipped — production publishes
only via `html`/`readthedocs`, and we don't render `llms.txt` for builds
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

When adding new top-level sections to the docs, add a corresponding
bullet in `docs/_templates/llms.txt.j2`. Branch-specific differences
(e.g. sagitta has no `vpp/index.md` or `contributing/index.md`) live
in that branch's copy of the template.

## Read the Docs Layout

RTD slugs as of 2026-05-04 (verified via API). Re-verify via the RTD
Versions API (project `vyos`) and update the date stamp before editing this
table.

| Slug | Verbose | Branch | Role |
|---|---|---|---|
| `rolling` | rolling | `rolling` | canonical for rolling/next major |
| `1.5` | circinus | `circinus` | canonical for current LTS |
| `1.4` | sagitta | `sagitta` | canonical for previous LTS |
| `1.3`, `1.2` | equuleus, crux | older | canonical for older releases |

URL-level redirect aliases (resolve to the canonicals above):
`/en/latest/* → /en/rolling/`, `/en/lts/* → /en/1.5/`,
`/en/stable/* → /en/lts/`, `/en/circinus/* → /en/1.5/`,
`/en/sagitta/* → /en/1.4/`, `/en/equuleus/* → /en/1.3/`,
`/en/crux/* → /en/1.2/`.

`html_baseurl` per branch must point at the canonical (numeric or `rolling`),
not the alias, so `<link rel="canonical">` and the sitemap match what RTD
serves and crawlers skip the redirect hop.

## CI

- **doc-linter** (`scripts/doc-linter.py` in-repo, invoked via
  `.github/workflows/lint-doc.yml`) — line length and IP rules, on
  changed files under `docs/` only. Repo-root meta files
  (README.md, AGENTS.md, `.github/copilot-instructions.md`) are out
  of scope.
- **AI Validation** (`.github/workflows/ai-validation.yml`) —
  cross-checks the changed `docs/**/*.md` against the VyOS CLI
  definitions in the `vyos-1x` source tree for the corresponding
  branch, and posts findings as inline review comments plus a summary
  comment on the PR. Only runs when a PR touches Markdown under
  `docs/`. Skips — with a notice — when the required repository
  secrets aren't configured, and on Mergify-authored backport PRs.
- **Sphinx build** — runs on Read the Docs for every PR; preview URL
  appears as a check.
- **CLA check** — contributors must sign the VyOS CLA before merge.
- **Conflict check** — fails the PR if it doesn't merge cleanly into base.

### Bot review workflow

CodeRabbit is the automated reviewer on this repo. It runs on its own —
in the normal case there is nothing to invoke by hand. Iterate in draft
while the work is in flux, then flip to ready when you want review.

- **Drafts are skipped.** CodeRabbit ignores draft PRs entirely.
- **Review fires automatically** when a PR is flipped to ready
  (`gh pr ready <num>`), and again on every subsequent push.
- **The walkthrough comment is edited in place.** CodeRabbit usually
  updates its existing comment rather than posting a new one — for
  example to "no actionable comments". No new comment does not mean no
  new review; re-read the existing one.
- **Rate limits silently drop a review.** If CodeRabbit is rate-limited
  when an event fires, that review is skipped with no error. Comment
  `@coderabbitai review` once the limit window resets. This is the only
  case where triggering it by hand is appropriate.

Copilot is not part of this workflow — do not invoke `@copilot review`.
If Copilot threads do appear because someone invoked it manually,
address them like any other reviewer feedback.
