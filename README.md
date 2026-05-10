# VyOS Documentation

Source for the VyOS user documentation hosted on Read the Docs at
https://docs.vyos.io.

[![Documentation Status](https://readthedocs.org/projects/vyos/badge/?version=rolling)](https://docs.vyos.io/en/rolling/?badge=rolling)

The earlier wiki for VyOS 1.1.x and pre-1.2.0 docs is preserved on the
[Wayback Machine](https://web.archive.org/web/20200225171529/https://wiki.vyos.net/wiki/Main_Page).

## Branches

The documentation repository tracks the same branch convention as the VyOS
source itself — one long-lived branch per release line, named after a
constellation:

| Branch | VyOS version | Role |
|--------|--------------|------|
| `rolling` | 1.5+ rolling | Default branch — all new contributions target this. |
| `circinus` | 1.5.x | LTS docs. |
| `sagitta` | 1.4.x | Previous LTS docs. |
| `equuleus` | 1.3.x | Legacy. |
| `crux` | 1.2.x | Legacy. |

New work lands on `rolling` first; backports to `circinus` and `sagitta` are
requested per-PR via Mergify. See [AGENTS.md](AGENTS.md) for the full
contributor guide.

## Build

The recommended build path is the bundled Docker image — it pins Sphinx and
the MyST/RTD plugin set to the same versions Read the Docs uses, so local
builds match production.

```bash
docker build -t vyos/vyos-documentation docker

# One-shot HTML build
docker run --rm -it -v "$(pwd)":/vyos -w /vyos/docs \
  -e GOSU_UID=$(id -u) -e GOSU_GID=$(id -g) \
  vyos/vyos-documentation make html

# Live-reload server on port 8000
docker run --rm -it -p 8000:8000 -v "$(pwd)":/vyos -w /vyos/docs \
  -e GOSU_UID=$(id -u) -e GOSU_GID=$(id -g) \
  vyos/vyos-documentation make livehtml
```

For a Python-only build (no Docker), use a virtualenv with the pinned
versions in `requirements.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd docs && make html
```

Output lands in `docs/_build/html/`.

## Contributing

See [AGENTS.md](AGENTS.md) for the full contributor guide — source format
conventions (MyST Markdown for migrated pages, RST for the rest), CLI
directive syntax, IP-address rules, the linter, and the bot review workflow.
