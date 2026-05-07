# AGENTS.md — `vyos/vyos-1x`

## Project purpose

The user-visible VyOS package: command definitions (XML), conf-mode and op-mode scripts, Jinja2 templates, validators, migration scripts, and the Python `vyos.*` library that all of the above import. This is the largest single VyOS package and the primary surface for new feature work in 1.4+.

## Tech stack

- Python 3 (≥3.10) with `vyos.*` library under `python/vyos/`.
- XML interface and op-mode definitions, Jinja2 templates under `data/templates/`.
- C wrapper `libvyosconfig` (vendored at `libvyosconfig/`) — links statically against [`vyos/vyos1x-config`](https://github.com/vyos/vyos1x-config) (OCaml).
- Build: Debian packaging via `debhelper` + `dh-python`. Build-deps in `debian/control` (see `protobuf-compiler`, `libpcre2-dev`, `libffi-dev`, `python3-vici`, `python3-fastapi`, ...).
- Tests: `nose2` (`nose2.cfg`), Python `pylint`, ruff (`ruff.toml`).

## Build / test / run

```
# Debian package build (produces 6 binary packages)
dpkg-buildpackage -uc -us -tc -b
# Smoketests (against an installed VyOS, normally driven by vyos-build)
./scripts/build-command-templates ...   # XML preprocessor
make all                                # see Makefile targets
```

Produces: `vyos-1x`, `libvyosconfig0`, `vyos-1x-aws`, `vyos-1x-smoketest`, `vyos-1x-vmware`, `vyos-user-utils`.

Smoketests (`smoketest/`) run inside the QEMU harness invoked by `vyos-build`'s `scripts/check-qemu-install --smoketest`.

## Repository layout

- `python/vyos/` — importable Python library (`config.py`, `configtree.py` ctypes wrapper, `configsession.py`, `firewall.py`, `frrender.py`, ifconfig drivers).
- `src/conf_mode/` — set-mode entry-point scripts named after CLI components.
- `src/op_mode/` — show/op-mode scripts.
- `src/validators/` — value validators (Python; OCaml validators come from `vyos-utils`).
- `src/migration-scripts/` — config-format migrations between releases.
- `src/services/` — runtime services including the HTTP API implementation.
- `interface-definitions/` — XML CLI declarations (preprocessed via `scripts/build-command-templates`, `scripts/override-default`, `scripts/transclude-template`).
- `op-mode-definitions/` — op-mode XML.
- `data/templates/` — Jinja2 outputs (FRR, strongSwan, nftables, dnsmasq, ...).
- `libvyosconfig/` — C wrapper; source of the `libvyosconfig0` Debian package.
- `smoketest/` — `nose2` CLI smoketests.
- `schema/`, `mibs/`, `debian/`, `scripts/`.

## Cross-repo context

- Imports `libvyosconfig0` (built from in-tree `libvyosconfig/`, which wraps `vyos/vyos1x-config`).
- Calls OCaml validators from `vyos/vyos-utils` via `<validator name='...'/>` XML directives.
- Listed in `VyOS-Networks/vyos-build-packages/repos.toml` as the canonical 14-repo build set; consumed by `vyos/vyos-build` at ISO assembly time.
- `vyos/vyos-documentation` carries `docs/_include/vyos-1x` as a submodule **pinned to `sagitta`** — do not bump the doc submodule branch without a coordinated change.
- `VyOS-Networks/vyos-1x` is the private mirror twin (canonical here). The `pr-mirror-repo-sync.yml` reusable workflow is live for this repo.
- HTTP API runtime deps come from `vyos/vyos-http-api-tools`; the FastAPI implementation lives in `src/services/`.

The standalone `VyOS-Networks/libvyosconfig` repo is a parallel mirror with its own pipeline; the canonical source for downstream Debian builds is the in-tree `libvyosconfig/` directory here.

## Conventions

- Commit / PR title format: `component: T12345: description` (Phorge task ID at https://vyos.dev mandatory). Enforced by `vyos/.github/.github/workflows/check-pr-message.yml`.
- Branch model: `current` (rolling, default), `circinus` (1.5 LTS), `sagitta` (1.4 LTS), `equuleus` (1.3 LTS). Backports via `@Mergifyio backport <branch>`.
- Default-branch protection: 2 required approvals, status checks required.
- Linting (`vyos/.github` reusables): ruff 0.6.4, darker, pylint W0611, Jinja2 lint. `ruff.toml` and `nose2.cfg` at repo root.
- No `mergify.yml` — `vyos-1x` is one of the few mirror-pipeline consumers without it.

## Mirror relationship

Mirror twin: `VyOS-Networks/vyos-1x`. Canonical side is **here** (`vyos/vyos-1x`). PRs merged on a release-train branch are mirrored downstream by `pr-mirror-repo-sync.yml`.

## Notes for future contributors

- The vendored `libvyosconfig/` is **not** just a wrapper — it produces the `libvyosconfig0` Debian package. Edits there ripple to every consumer of the config-tree API.
- New features go here, not in the legacy `vyatta-cfg*` repos.
- 2 repo-level Actions secrets, 2 environments, 2 outbound webhooks (`ci.vyos.net`, `hooks.zapier.com`). Do not enumerate secret names in code or docs.
- License: GPL/LGPL dual; see `LICENSE`, `LICENSE.GPL`, `LICENSE.LGPL`.
