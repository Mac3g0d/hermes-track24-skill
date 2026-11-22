# Hermes Track24 parcel tracking skill

Unofficial, read-only Track24 parcel status reader for Hermes Agent. This is not a commercial API client or an autonomous shipment-monitoring service.

## Features

- Python `urllib` page retrieval and POST; no copied browser cookies or user session parameters.
- Endpoint discovery from the observed public page format without executing JavaScript.
- CryptoJS JSON envelope decoding and exact tracking-identifier validation.
- Minimal JSON status output; no delivery addresses or raw session variables.
- Six offline unit tests with synthetic data.

## Run

Requires Python 3.10+ and PyCryptodome. Install dependencies into an operator-approved project environment, not a system Python:

```sh
python -m pip install -r requirements.txt
python scripts/track24.py "$TRACK_CODE"
python -m unittest discover -s tests -v
```

Set `TRACK_CODE` to your own parcel identifier. No live user identifiers, credentials or captured shipment responses are included in this repository.

If the site's endpoint packing changes, discovery fails closed. An optional `--endpoint` accepts an operator-observed HTTPS /ajax/ URL on track24.ru only. See [SKILL.md](SKILL.md) for handling cached statuses, challenges, monitoring approval and verification.

## Install as a Hermes skill

Copy this directory (SKILL.md plus scripts/ and tests/) into your approved active profile's skills directory as `track24-parcel-tracking`. The name in SKILL.md is authoritative. Do not replace another profile's files.

## Verification scope

The implementation was exercised against one operator-owned Qwintry parcel and returned a matching decrypted event. Ural, GUOO and Ozon coverage is not claimed until separately verified. No exact reproduction of an old event is promised for a future live request.

## Boundaries

Check current Track24 terms before recurring or bulk use. Respect errors, challenges and rate limits. This tool does not bypass CAPTCHA, rotate proxies, schedule jobs, send notifications, complete tasks or delete files. The website is undocumented and may change. Cryptography here reproduces the public client format, not a general key-recovery mechanism.

License: MIT.
