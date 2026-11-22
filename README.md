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
  scripts/track24.py            tracker and CLI
  scripts/track24_constants.py  every constant, annotated with typing.Final
tests/                          pytest suite, not shipped with the skill
  helpers/                      synthetic data, CryptoJS envelope builder, loopback fake Track24
pyproject.toml, uv.lock         uv project for development
```

## Features

- Python `urllib` page retrieval and POST; no copied browser cookies or user session parameters.
- Endpoint discovery from the observed public page format without executing JavaScript.
- CryptoJS JSON envelope decoding and exact tracking-identifier validation.
- Minimal JSON status output; no delivery addresses or raw session variables.
- Typed errors (`ChallengeError`, `IdentifierMismatchError`, ...) reported by class name only.

## Run

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```sh
uv run --no-project --with "pycryptodome>=3.20,<4" python skills/track24-parcel-tracking/scripts/track24.py "$TRACK_CODE"
```

Set `TRACK_CODE` to your own parcel identifier. No live user identifiers, credentials or captured shipment responses are included in this repository.

If the site's endpoint packing changes, discovery fails closed. An optional `--endpoint` accepts an operator-observed HTTPS /ajax/ URL on track24.ru only. See [SKILL.md](skills/track24-parcel-tracking/SKILL.md) for handling cached statuses, challenges, monitoring approval and verification.

## Development

```sh
uv sync
```

```sh
uv run pytest
```

```sh
uv run pytest -m integration
```

Tests follow Arrange / Act / Assert and use only synthetic data with no external network access:

- unit tests for literal parsing, packer decoding, endpoint allowlisting, CryptoJS decryption, identifier validation and the summary shape;
- integration tests that run the full flow over a real loopback HTTP server impersonating Track24: page GET, endpoint discovery, form POST, decryption, verification, HTTP 403/429, challenges, size limits and the CLI output contract, including the script run as a subprocess from the installed layout;
- repository checks for the hub tap layout, `SKILL.md` frontmatter, `typing.Final` constants and the no-line-comments rule.

## Verification scope

The implementation was exercised against one operator-owned Qwintry parcel and returned a matching decrypted event. Ural, GUOO and Ozon coverage is not claimed until separately verified. No exact reproduction of an old event is promised for a future live request.

## Boundaries

Check current Track24 terms before recurring or bulk use. Respect errors, challenges and rate limits. This tool does not bypass CAPTCHA, rotate proxies, schedule jobs, send notifications, complete tasks or delete files. The website is undocumented and may change. Cryptography here reproduces the public client format, not a general key-recovery mechanism.

License: MIT.
