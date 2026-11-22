---
name: track24-parcel-tracking
description: "Read-only Track24 parcel status: fetch, decrypt and verify the latest event for an exact tracking code."
version: 2.0.0
author: Mac3g0d
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tracking, parcels, track24, logistics]
    related_skills: [shopping-research, blocked-page-recovery]
---

# Track24 parcel tracking

Read shipment events from the public Track24 web flow. This is an unofficial integration, not a supported Track24 API. Recheck current terms and do not bypass access challenges. A successful web request is not permission for bulk scraping.

## When to Use

Use for operator-owned parcel status checks on Track24 and diagnosis of its public web flow. Not for identifying parcel owners, bulk collection or automatically scheduling checks.

## Execution

Run `scripts/track24.py` from this skill's directory with one or more exact tracking identifiers (at most 10 per run). It needs Python 3.10+, `httpx` and `pycryptodome`; use `uv` so nothing is installed into a system interpreter. `scripts/track24_constants.py` must stay next to the script. Example identifiers in docs are placeholders, not live parcels.

```sh
uv run --no-project --with "httpx>=0.27,<1" --with "pycryptodome>=3.20,<4" python scripts/track24.py "$TRACK_CODE"
```

Pass several identifiers in one call instead of calling the script once per parcel: they share one connection pool and run concurrently (at most 3 requests in flight), and repeated identifiers are fetched once.

Output is JSON Lines in argument order. Each verified parcel prints a summary line to stdout. Each failure prints `{"track": "<code>", "ok": false, "error": "<ErrorType>"}` to stderr, plus `http_status` when `error` is `http_error`. Exit code is 0 only when every identifier succeeded. Error types: `InvalidTrackCodeError`, `MissingLiteralError`, `EndpointError`, `DecryptionError`, `ResponseTooLargeError`, `UnexpectedRedirectError`, `ChallengeError`, `ServiceStatusError`, `IdentifierMismatchError`, and httpx transport errors such as `ConnectError` or `ReadTimeout`. A connection that could not be opened is retried once; nothing else is retried.

The script retrieves the public page, reads its `cp` literal, discovers the tracking endpoint from a literal or the observed dictionary-packed assignment WITHOUT executing JavaScript, POSTs form data, and decodes the CryptoJS AES passphrase envelope. AES-CBC uses OpenSSL-style MD5 derivation with the supplied salt. None of the encryption parameters are printed. Never hardcode a user's cookies, browser key, UUID, fingerprint, IP, address or track number into the skill or repository.

If endpoint discovery changes, fail closed. After inspecting a legitimate successful browser request, an operator may provide `--endpoint https://track24.ru/ajax/<observed-name>.ajax.php`. Only HTTPS URLs on the exact Track24 host and /ajax/ path are accepted. Do not guess endpoint hashes or execute downloaded JavaScript.

## Verification and reporting

- Require HTTP success, decrypted `status=ok`, the exact matching `data.trackCode` and no challenge. HTTP 200 can contain an encrypted error; ciphertext alone is not proof of tracking success.
- Read `data.lastPoint` for the selected latest event. Do not assume `events[-1]` is newest: sorting can change. Preserve event ID, operation date/time and source-update time separately. Timezone is unknown unless explicitly supplied.
- Distinguish cached provider data (`sources`) from fetch time. A new fetch does not imply a new carrier event.
- Treat `deliveredStatus=1` as a delivered flag; do not mark the user's task done merely because tracking was fetched or a parcel reached a hub.
- The CLI prints a minimal status summary, not full delivery addresses or raw page/session data. Do not upload live tracking responses as test fixtures.
- Runtime transport differences matter: curl and a browser may fail while Python urllib succeeds. Measure rather than claim a permanent IP ban or assert a specific WAF cause. Stop on 403/429/challenges; no proxy rotation, fingerprint spoofing or challenge bypass. Do not use archived pages as current parcel status.
- Live execution was verified for Qwintry, Ozon, Ural express and GUOO shipments; other carriers are unverified. Test one exact identifier per carrier before claiming support. No live user identifier is stored in this skill.

## Monitoring is a separate opt-in

This skill does not schedule jobs, send messages, close tasks, install dependencies automatically or delete files. Obtain approval for a monitoring schedule and destination. Persist state incrementally; notify only on changed events, stop after confirmed delivery and keep fetch failures separate from carrier changes. For Vuti, scheduled notifications go to Home, not DM. Do not automate polling before current usage terms and each source's proof path have been checked.

## Known limits

The website can change its endpoint, packing, cryptography or response schema without notice. The current decoder only supports the observed JSON CryptoJS format and fails closed otherwise. No arbitrary browser-session replay, CAPTCHA handling, retries beyond one reconnect, redirects, push delivery or tracking-number auto-normalization is provided. Tests use explicitly synthetic crypto data and no network. Live smoke tests are opt-in and require an operator-owned parcel.
