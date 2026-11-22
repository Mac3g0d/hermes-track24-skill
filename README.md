# Hermes Track24 parcel tracking skill

[![tests](https://github.com/Mac3g0d/hermes-track24-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/Mac3g0d/hermes-track24-skill/actions/workflows/tests.yml)

Unofficial, read-only Track24 parcel status reader for [Hermes Agent](https://github.com/NousResearch/hermes-agent). This is not a commercial API client or an autonomous shipment-monitoring service.

## Install from the Hermes Skills Hub

This repository is laid out as a Hermes skills tap: every directory under `skills/` that contains a `SKILL.md` is one skill.

Install the skill directly from GitHub:

```sh
hermes skills install Mac3g0d/hermes-track24-skill/skills/track24-parcel-tracking
```

Or add the whole repository as a tap, then search and install from it:

```sh
hermes skills tap add Mac3g0d/hermes-track24-skill
```

```sh
hermes skills search track24
```

```sh
hermes skills install track24-parcel-tracking
```

Inspect before installing, and update later:

```sh
hermes skills inspect Mac3g0d/hermes-track24-skill/skills/track24-parcel-tracking
```

```sh
hermes skills update
```

New taps are installed with `community` trust and go through the Hermes security scanner. The skill ships only `SKILL.md` and `scripts/`.

## Layout

```text
skills/track24-parcel-tracking/
  SKILL.md                      skill manifest and agent instructions
  scripts/track24.py            async httpx tracker and CLI, with PEP 723 dependencies
  scripts/track24_constants.py  every constant, annotated with typing.Final
tests/                          pytest suite, not shipped with the skill
  conftest.py                   only registers the fixture plugins below
  fixtures/                     pytest fixtures loaded via pytest_plugins
  factories/                    polyfactory factories for synthetic Track24 payloads
  constants.py                  test constants, annotated with typing.Final
docs/COMPARISON.md              v1 vs v2 cost, tokens and runtime
pyproject.toml, uv.lock         uv project, pytest and tox configuration
```

## Features

- Async `httpx` client: several identifiers per run share one connection pool, at most 3 requests in flight.
- No copied browser cookies or session parameters; redirects are refused; response size is capped while streaming.
- Endpoint discovery from the observed public page format without executing JavaScript.
- CryptoJS JSON envelope decoding and exact tracking-identifier validation.
- JSON Lines output, one line per identifier; no delivery addresses or raw session variables.
- Typed errors (`ChallengeError`, `IdentifierMismatchError`, ...) reported by class name only.

## Run

Requires [uv](https://docs.astral.sh/uv/). The script declares its dependencies and Python version in a PEP 723 inline metadata block at the top of `track24.py`, so uv installs them on the first run:

```sh
uv run skills/track24-parcel-tracking/scripts/track24.py "$TRACK_CODE" "$OTHER_TRACK_CODE"
```

Each verified parcel prints a JSON summary line to stdout; each failure prints `{"track": ..., "ok": false, "error": ...}` to stderr. The exit code is 0 only when every identifier succeeded. No live user identifiers, credentials or captured shipment responses are included in this repository.

If the site's endpoint packing changes, discovery fails closed. An optional `--endpoint` accepts an operator-observed HTTPS /ajax/ URL on track24.ru only. See [SKILL.md](skills/track24-parcel-tracking/SKILL.md) for handling cached statuses, challenges, monitoring approval and verification.

## Development

```sh
uv sync
```

```sh
uv run pytest
```

```sh
uvx --with tox-uv tox -p auto
```

`tox` is run as a uv tool, not installed into the test environments. It runs these environments:

| Environment | Checks |
|---|---|
| `lint` | `ruff check` and `ruff format --check` |
| `type` | `mypy` (strict) and `ty check` |
| `security` | `bandit` on the shipped skill code |
| `3.10` … `3.14` | the pytest suite on each Python version |
| `integration` | only the integration tests (not in the default list) |

CI runs every tox environment, plus [gitleaks](https://github.com/gitleaks/gitleaks) over the full git history and [trivy](https://github.com/aquasecurity/trivy) over `uv.lock` (runtime and dev dependencies), secrets and configuration. Both scanners are installed from pinned releases after SHA-256 verification.

Tests follow Arrange / Act / Assert. Test modules contain only imports and test functions; fixtures live in `tests/fixtures/` and are loaded as plugins from `conftest.py`. Network traffic is mocked with `pytest_httpx`, other collaborators with `pytest-mock`, and payloads are generated with `polyfactory`:

- unit tests for literal parsing, packer decoding, endpoint allowlisting, CryptoJS decryption, identifier validation and the summary shape;
- integration tests for the full flow through httpx: page GET, endpoint discovery, form POST, decryption, verification, redirects, HTTP 403/429, challenges, size limits, reconnects, concurrency limits and the CLI output contract, including the script run as a subprocess from the installed layout;
- repository checks for the hub tap layout, `SKILL.md` frontmatter, PEP 723 metadata matching `pyproject.toml`, `typing.Final` constants, no line comments outside the PEP 723 block, no `from __future__ import annotations`, and test modules holding only tests.

## Releases

Pushing a `v*` tag that matches the `SKILL.md` version runs the whole CI pipeline (tox, gitleaks, trivy) and only then builds `track24-parcel-tracking-<tag>.zip` and `.tar.gz` from `skills/track24-parcel-tracking/` with SHA-256 sums, and publishes them as a GitHub release.

## Verification scope

Version 2.0.0 was exercised against live Qwintry, Ozon, Ural express and GUOO parcels, each returning a matching decrypted event; see [docs/COMPARISON.md](docs/COMPARISON.md). Other carriers are not claimed until separately verified. No exact reproduction of an old event is promised for a future live request.

## Boundaries

Check current Track24 terms before recurring or bulk use. Respect errors, challenges and rate limits. This tool does not bypass CAPTCHA, rotate proxies, schedule jobs, send notifications, complete tasks or delete files. The website is undocumented and may change. Cryptography here reproduces the public client format, not a general key-recovery mechanism.

License: MIT.
