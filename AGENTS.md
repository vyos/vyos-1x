# AGENTS.md

## Project purpose

The user-visible VyOS package: command definitions (XML), conf-mode and op-mode
scripts, Jinja2 templates, validators, migration scripts, and the Python
`vyos.*` library imported by all of the above.

This is the largest single VyOS package and the primary surface for new feature
work in 1.4+.

## Tech stack

- Python 3 (>=3.11) with the `vyos.*` library under `python/vyos/`.
- XML interface definitions for configure mode (conf-mode) are located in
  `interface-definitions/`. XML CLI building blocks can be split into include
  files to reduce duplication. Include files are in
  `interface-definitions/include/`.
- XML definitions for operational mode (op-mode) CLI commands are stored in
  `op-mode-definitions/`. They use the same include pattern as conf-mode.
  Include files are in `op-mode-definitions/include/`.
- Both conf-mode and op-mode make heavy use of Jinja2 as a templating engine.
  Jinja2 templates are either inline Python strings or stored as discrete files
  under `data/templates/`. Storing templates as files is preferred.
- C wrapper `libvyosconfig` (vendored at `libvyosconfig/`) builds
  `libvyosconfig.so.0` (shared library) using OCaml ctypes bindings against
  [`vyos/vyos1x-config`](https://github.com/vyos/vyos1x-config).
- Build: Debian packaging via `debhelper` + `dh-python`. Build dependencies are
  in `debian/control` (for example: `protobuf-compiler`, `libpcre2-dev`,
  `libffi-dev`, `python3-vici`, `python3-fastapi`,...).
- Tests: `nose2` (`nose2.cfg`), Python `pylint`, and ruff (`ruff.toml`).
- Runtime smoketests are located under `smoketest/`. These tests are used by
  `vyos-build` when assembling and testing ISO images.

## Build instructions

```bash
# Debian package build (produces 6 binary packages)
dpkg-buildpackage -uc -us -tc -b
# or
make deb

# In-tree build (XML preprocessing + shim compilation)
make all  # see Makefile targets
```

Produces: `vyos-1x`, `libvyosconfig0`, `vyos-1x-aws`, `vyos-1x-smoketest`,
`vyos-1x-vmware`, `vyos-user-utils`.

## Testing instructions

Two kinds of test, and picking the wrong one wastes a build cycle:

- Build-time (`src/tests/`, nose2). Run by `make all`, which chains the
  `libvyosconfig` and `test` targets - `libvyosconfig` is built and installed
  first if `/usr/lib/libvyosconfig.so.0` is absent. Beyond that there is no
  VyOS base system: no CLI, no `/sys` to speak of. Only for pure logic that
  needs none of those. Mocking the base system away to reach a runtime
  behaviour proves the branch was taken, not the outcome - put that in a
  smoketest instead.
- Runtime (`smoketest/`). Runs on a booted image inside the QEMU harness,
  invoked by `vyos-build`'s `scripts/check-qemu-install --smoketest`. This is
  where interface, service and commit behaviour belongs.

A single smoketest can be run from `vyos-build` without the whole suite:

```bash
make test -- --match protocols_bgp
```

Smoketests run on whatever hardware the harness provides. Do not assume jumbo
frames, wireless, or more than one member of anything - guard with
`skipTest()` where the shape is not guaranteed.

### Never run CLI configuration as root

When testing by hand on a router or DUT, run `configure`, `set`, `delete` and
`commit` as an admin user - **never** as `root`, and never via `sudo`.
Configuration under `root` is written into the overlay filesystem with root
ownership, and every other user is then locked out of the affected CLI node: a
later `delete` of that node fails with a permission error. A reboot clears it,
but losing the DUT state mid-test is a poor way to find that out.

`sudo` is fine - and often necessary - for inspecting or debugging the running
system: reading logs, `ip`/`nft`/`vtysh` output, `systemctl status`, poking at
`/run` and `/sys`. The rule is about the configuration CLI only.

## Repository layout

- `python/vyos/` - importable Python library (`config.py`, `configtree.py`
  ctypes wrapper, `configsession.py`, `firewall.py`, `frrender.py`, ifconfig
  drivers).
- `src/conf_mode/` - set-mode entry-point scripts named after CLI components.
- `src/op_mode/` - show/op-mode scripts.
- `src/validators/` - value validators (Python; OCaml validators come from
  `src/ocaml/`).
- `src/migration-scripts/` - config-format migrations between releases.
- `src/services/` - runtime services, including the HTTP API implementation.
- `interface-definitions/` - XML CLI declarations (preprocessed via
  `scripts/build-command-templates`, `scripts/override-default`,
  `scripts/transclude-template`).
- `op-mode-definitions/` - op-mode XML.
- `data/templates/` - Jinja2 input templates for third-party services consumed
  by VyOS (FRR, strongSwan, nftables, dnsmasq,...).
- `libvyosconfig/` - C wrapper; source of the `libvyosconfig0` Debian package.
- `smoketest/` - `nose2` CLI smoketests.
- `schema/`, `mibs/`, `debian/`, `scripts/`.

## Cross-repo context

- Imports `libvyosconfig0` (built from in-tree `libvyosconfig/`, which wraps
  `vyos/vyos1x-config`).
- Calls OCaml validators from `src/ocaml/` via `<validator name='...'/>` XML
  directives. OCaml validators reduce Python interpreter startup overhead and
  make configuration commits faster.
- `vyos/vyos-documentation` carries `docs/_include/vyos-1x` as a submodule
  **pinned to `sagitta`** — do not bump the doc submodule branch without a
  coordinated change.
- HTTP API runtime dependencies come from `vyos/vyos-http-api-tools`; the
  FastAPI implementation lives in `src/services/`.
- Testing a change end to end means getting it into an ISO. This repository is
  normally checked out at `vyos-build/packages/vyos-1x`, and `.deb`s built here
  land in `vyos-build/packages/`, where the ISO build picks them up in
  preference to the apt mirror. See that repository's AGENTS.md for the cycle.

## Conventions

- Commit and PR titles: see "Commit messages" below.
- See `CONTRIBUTING.md` for additional commit message guidance.
- Branch model: `rolling` (default), `scutum` (1.6), `circinus` (1.5 LTS),
  `sagitta` (1.4 LTS). Backports via `@Mergifyio backport <branch>`. Work
  never lands on these branches directly - see "Change workflow" below.
- Default-branch protection: 2 required approvals; required status checks.
- Linting (`vyos/.github` reusables): ruff 0.6.4, darker, pylint W0611, Jinja2
  lint. `ruff.toml` and `nose2.cfg` are at repository root.
- `.github/mergify.yml` drives the backport automation referenced above.

## Commit messages

- Title: `component: T1234: description`. The Phorge Task ID is required -
  <https://vyos.dev>. Enforced by `check-pr-message.yml`.
- A body is highly recommended, and limited to 150 words. Say what was wrong
  and what now happens instead; the diff shows the rest.
- Do not name functions, methods or files unless the message is meaningless
  without them. It reads as noise and eats the budget.
- Use `*` or `-` for a list, and only when one is genuinely needed.

## Change workflow

Every change follows the same three steps before a PR exists. None of them is
optional, and they happen in this order.

### 1. Work on a feature branch

Never commit to a release branch (`rolling`, `scutum`, `circinus`, `sagitta`)
directly. Branch from the release branch the change targets and name the branch
after the Phorge task, for example `T1234-bgp-peer-group`:

```bash
git fetch origin
git checkout -b T1234-short-description origin/rolling
```

The branch you fork from is the branch the PR merges into. A fix that belongs in
an LTS release starts from that LTS branch, not from `rolling` - backports in
the other direction are handled by `@Mergifyio backport <branch>`.

### 2. Rebase onto the common merge-base before submitting

Immediately before opening the PR, rebase the feature branch on top of the
current tip of its base branch. A merge commit is not a substitute; the history
must stay linear:

```bash
git fetch origin
git rebase origin/rolling     # or scutum / circinus / sagitta
```

Rebasing last means CI tests the code as it will exist after the merge, not
against a base that moved weeks ago. If the rebase changes anything non-trivial,
the smoketest run in step 3 has to be repeated on the rebased result.

### 3. Run the full smoketest suite

A PR is submitted only after a complete smoketest run has passed locally, with
the same steps the `.github/workflows/package-smoketest.yml` pipeline executes.
Build-time tests (`make all`) do not count - they never boot an image.

Build the package and an ISO carrying it, from the `vyos-build` checkout that
has this repository at `packages/vyos-1x`:

```bash
# in packages/vyos-1x
dpkg-buildpackage -uc -us -tc -b

# in the vyos-build root, ISO includes the smoketest package
sudo --preserve-env ./build-vyos-image \
  --architecture amd64 \
  --build-by <you@example.com> \
  --build-type release \
  --custom-package vyos-1x-smoketest \
  --version <version-string> \
  generic
```

Then run every test job the pipeline runs for the target branch, against that
ISO:

```bash
sudo make test-no-interfaces-no-vpp   # rolling, scutum, circinus
sudo make test-no-interfaces          # sagitta (no VPP split there)
sudo make test-interfaces             # CLI smoketests, interfaces only
sudo make testc                       # config load tests
sudo make testraid                    # RAID1 installation test
sudo make test-vpp                    # only where VPP is enabled
sudo make testcvpp                    # only where VPP is enabled
sudo make testtpm                     # only where TPM tests are enabled
```

Which of the optional jobs apply is not a guess: the per-branch flags
(`test_cli_command`, `test_vpp`, `test_tpm_tests`) live in
`.github/config/smoketest-branches.json`. Read that file for the target branch
and run exactly the set it selects.

All of them must pass. A failing or skipped-because-it-broke test is a reason to
fix the change, not a reason to open the PR and let the pipeline report it. If a
test cannot run locally for an environmental reason, say so explicitly in the PR
rather than claiming a clean run.

## Pull requests

- The PR body must use `.github/PULL_REQUEST_TEMPLATE.md` as it currently
  stands. GitHub pre-fills it; when opening a PR by other means (`gh pr create`,
  the API) read that file and start from its contents.
- Do not delete, reorder, rename or reformat its sections, checklists or HTML
  comments, and do not substitute a summary of your own. Reviewers and tooling
  rely on the fixed shape.
- Fill in the sections and tick the boxes that apply. Leave an inapplicable
  section empty rather than removing its heading, and leave a box unticked
  rather than deleting it.
- If the template itself looks wrong, say so in the PR - changing it is a
  separate change to `.github/PULL_REQUEST_TEMPLATE.md`, not something to do
  silently in a PR body.

## Code comments

- Comment only what the code cannot say. No restating the line below.
- Never state anything you have not verified. A confident wrong comment
  outlives the code and misleads every later reader.
- Keep them short. Nobody reads a novel in a source file.

## Notes for future contributors

- The vendored `libvyosconfig/` is **not** just a wrapper - it produces the
  `libvyosconfig0` Debian package. Edits there affect every consumer of the
  config-tree API.
- New features go here, not in the legacy `vyatta-cfg*` repositories.
- 2 repository-level Actions secrets, 2 environments, 2 outbound webhooks. Do
  not enumerate secret names or infrastructure endpoints in code or docs.
- License: GPL/LGPL dual; see `LICENSE`, `LICENSE.GPL`, `LICENSE.LGPL`.
