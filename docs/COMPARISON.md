# v1 vs v2: cost, tokens and script efficiency

Measured on 2026-11-22 against live Track24 with five real parcels: Qwintry, Ozon, Ural express (two parcels) and GUOO. All five carriers returned a verified, decrypted `lastPoint`.

- **v1**: commit `7dde028`, the `urllib` script, one identifier per process.
- **v2**: this branch, `httpx` + `asyncio`, several identifiers per process.

## Script runtime (5 parcels, 3 rounds)

| Metric | v1 (5 sequential processes) | v2 (1 process, concurrent) |
|---|---|---|
| Wall time per round | 17.3 / 18.7 / 17.8 s | 1.75 / 1.64 / 1.69 s |
| CPU time per round | 0.39 / 0.45 / 0.44 s | 0.23 / 0.22 / 0.25 s |
| Verified parcels per round | 4 / 4 / 4 | 5 / 5 / 5 |
| Process start-up (`--help`, median) | 0.063 s | 0.111 s |

v2 finishes a 5-parcel check about **10× faster** and uses about **half the CPU**. The connection pool is reused and up to 3 requests run at once.

v2 also verified every parcel, while v1 lost one parcel in each round to a transient `URLError`. v2 retries only failures to open a connection, where no request reached Track24. Blocking statuses (403/429), challenges and read timeouts are still never retried.

Importing `httpx` costs about 50 ms more at start-up. That is only noticeable for a single parcel and is far smaller than one network round trip (about 1.5 s).

## Tokens the agent pays for

Token counts are estimates: about 3.5 characters per token for ASCII and code, about 2 for Cyrillic. The `count_tokens` API and tokenizer downloads were not reachable from the measurement environment.

| Item | v1 | v2 |
|---|---|---|
| `SKILL.md` loaded on activation | ~1,221 | ~1,546 |
| `description` in hub search results | ~17 | ~30 |
| Tool calls to check 5 parcels | 5 | 1 |
| Command text the model writes | 5 × ~11 | 1 × ~30 (`uv run scripts/track24.py` + 5 codes) |
| Tool output read back | ~450 | ~528 |
| Script source, if the agent reads it | ~1,958 | ~4,613 + ~1,246 constants |

v2's `SKILL.md` is about 325 tokens larger because it documents the JSON Lines contract, the error types and the batching rule. Each line of output also carries `track`, so failures can be matched to their parcel.

The main saving is the number of turns. Each extra tool call makes the model re-read its whole context: 4 extra round trips in v1 for 5 parcels.

## Cost of one 5-parcel check

The model below assumes 20,000 tokens of agent context, cached and re-read on every turn. It also assumes about 25 tokens of tool-result framing per call and about 45 / 85 output tokens per v1 / v2 call. Prices are first-party API list prices per million tokens: input / output / cache read.

| Model | Prices | v1 | v2 | v2 / v1 |
|---|---|---|---|---|
| Claude Opus 5.5 | $4 / $20 / $0.20 | $0.0317 | $0.0141 | 0.44 |
| Claude Sonnet 5.5 | $2 / $10 / $0.10 | $0.0158 | $0.0070 | 0.44 |
| Claude Haiku 5.5 | $0.10 / $0.50 / ~$0.01 | $0.0013 | $0.0005 | 0.38 |

At 4 checks a day for 30 days on Claude Opus 5.5, that is about **$3.80 for v1 and $1.69 for v2**, before any retries. With v1, every transient failure costs one more full turn to re-run the parcel; v2 retries inside the same call. The saving grows with the agent's context size and with the number of parcels per check, up to the cap of 10 per run.

## Quality and safety

| Aspect | v1 | v2 |
|---|---|---|
| Parcels per call | 1 | up to 10, deduplicated, order kept |
| Redirects | followed by `urllib` | refused (`UnexpectedRedirectError`) |
| Connection failure | `URLError`, parcel lost | one reconnect, then a typed error |
| Size limit | read after download | enforced while streaming |
| Failure output | `{"ok": false, "error": ...}` | the same plus `track` for each parcel |
| Tests | 6 unittest cases | 131 pytest cases, tox on Python 3.10 to 3.14 |
