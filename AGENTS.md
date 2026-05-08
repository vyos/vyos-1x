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

Smoketests (`smoketest/`) run inside the QEMU harness invoked by
`vyos-build`'s `scripts/check-qemu-install --smoketest`.

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

## Conventions

- Commit/PR titles must follow: `component: T1234: description`. Phorge IDs are
  at <https://vyos.dev>. This is enforced by the
  `check-pr-message.yml` reusable workflow.
- See `CONTRIBUTING.md` for additional commit message guidance.
- Branch model: `current` (rolling, default), `circinus` (1.5 LTS), `sagitta`
  (1.4 LTS), `equuleus` (1.3 LTS). Backports via
  `@Mergifyio backport <branch>`.
- Default-branch protection: 2 required approvals; required status checks.
- Linting (`vyos/.github` reusables): ruff 0.6.4, darker, pylint W0611, Jinja2
  lint. `ruff.toml` and `nose2.cfg` are at repository root.
- No `mergify.yml` - `vyos-1x` is one of the few mirror-pipeline consumers
  without it.

## Notes for future contributors

- The vendored `libvyosconfig/` is **not** just a wrapper - it produces the
  `libvyosconfig0` Debian package. Edits there affect every consumer of the
  config-tree API.
- New features go here, not in the legacy `vyatta-cfg*` repositories.
- 2 repository-level Actions secrets, 2 environments, 2 outbound webhooks. Do
  not enumerate secret names or infrastructure endpoints in code or docs.
- License: GPL/LGPL dual; see `LICENSE`, `LICENSE.GPL`, `LICENSE.LGPL`.