# Plagiarism Checker Plus for Python

Official client for the [Plagiarism Checker Plus API](https://plagiarismcheckerplus.com/integrations/api). Python 3.8+, standard library only, fully typed.

Use it to add a **plagiarism checker API** (score plus every matching source) and an **AI detector API** (a likelihood for each sentence) to your app. Overview pages: [Plagiarism Checker API](https://plagiarismcheckerplus.com/integrations/api) · [AI Detector API](https://plagiarismcheckerplus.com/ai-detector-api) · [API reference](https://app.plagiarismcheckerplus.com/api-docs)

Get a free API key in the [developer portal](https://app.plagiarismcheckerplus.com/developers). Test keys are free and unlimited, and every free account gets 2,000 live API words once, with no card. See [API pricing](https://plagiarismcheckerplus.com/api-pricing).

## Install

```sh
pip install plagiarism-checker-plus
```

The import name is `plagiarism_checker_plus`.

## Quick start

Get a free API key at https://app.plagiarismcheckerplus.com/developers (test keys are free and unlimited).

```python
import os
from plagiarism_checker_plus import PlagiarismCheckerPlus

client = PlagiarismCheckerPlus(os.environ["PCP_API_KEY"])

scan_id = client.create_scan(text, ["plagiarism", "ai_detect"])["id"]  # 50+ words for AI detection
scan = client.wait_for_scan(scan_id)  # polls GET /scans/{id} until done

if scan.get("sandbox"):
    print("Test key: these are sample results.")
plagiarism = scan["results"]["plagiarism"] or {}
print("Matched:", plagiarism.get("score"), "%", [s["url"] for s in plagiarism.get("sources", [])])
print("AI likelihood:", (scan["results"]["aiDetection"] or {}).get("score"), "%")  # a likelihood, not proof
```

## Test keys, free trial and pricing

- **Test keys** (`pcp_test_...`) are free and unlimited on every plan, including free. They never run a check: `create_scan` returns as usual and `get_scan` returns `completed` with fixed sample results in the same shape as a real scan, marked `"sandbox": true`. Use them to build and test your integration.
- **Free API trial**: each free account gets 2,000 API words once for live keys (`pcp_...`), with no card. When the trial cannot cover a request, the API returns `402 trial_exhausted` and nothing is charged.
- **Paid app plans** (Student, Personal, Team) use their plan words for API calls.
- **API plans**: Starter $29/month (300,000 words), Growth $99/month (1,500,000 words), Scale $399/month (7,500,000 words).
- **Pay as you go**: words from $6 (50,000 words, $0.12 per 1,000 words). Purchased words never expire.

A scan costs its word count once per tool: 800 words checked for plagiarism and AI costs 1,600 words. Prices: [API pricing](https://plagiarismcheckerplus.com/api-pricing). Keys, usage, billing and webhooks: [developer portal](https://app.plagiarismcheckerplus.com/developers). `get_account()` returns what is left in `trial` and `balances`, plus `autoTopup` and this key's `key.mode` and `key.monthlyWordCap`.

The rate limit is 60 requests a minute per key on paid app plans and for accounts with an API plan or purchased API words, and 10 a minute otherwise (free trial, test keys on the free plan).

## Handling errors

```python
from plagiarism_checker_plus import ErrorCodes, PlagiarismCheckerPlusError

try:
    scan_id = client.create_scan(essay_text, ["plagiarism", "ai_detect"], name="essay-draft-1")["id"]
    scan = client.wait_for_scan(scan_id)
    if scan["status"] == "failed":
        raise RuntimeError(f"Scan {scan_id} failed")
except PlagiarismCheckerPlusError as error:
    details = error.details  # the response's error object, with any detail fields
    if error.code == ErrorCodes.TEXT_TOO_SHORT:
        print("Send at least 30 words for plagiarism, 50 for AI detection.")
    elif error.code == ErrorCodes.TRIAL_EXHAUSTED:
        print("Free API trial used up. Buy words or choose an API plan:", details.get("billingUrl"))
    elif error.code == ErrorCodes.INSUFFICIENT_WORDS:
        print(f"Need {details.get('wordsNeeded')} words, {details.get('wordsAvailable')} available. Top up:", details.get("billingUrl"))
    elif error.code == ErrorCodes.KEY_CAP_REACHED:
        print(f"This key reached its monthly cap of {details.get('monthlyWordCap')} words.")
    elif error.status == 429:
        print(f"Rate limited. Retry in {error.retry_after}s.")
    else:
        raise
```

## Webhooks

Instead of polling, register an https endpoint in the [developer portal](https://app.plagiarismcheckerplus.com/developers) to receive `scan.completed` and `scan.failed` for checks made with live keys. Each delivery carries

```
PCP-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>
```

`verify_webhook_signature(secret, header, raw_body, tolerance=300)` checks it with the endpoint's signing secret (`whsec_...`). Pass the raw request body, before JSON parsing. It compares in constant time and rejects timestamps more than 300 seconds from now (the tolerance is configurable).

```python
import json
import os
from flask import Flask, request
from plagiarism_checker_plus import WEBHOOK_SIGNATURE_HEADER, verify_webhook_signature

app = Flask(__name__)

@app.post("/webhooks/pcp")
def pcp_webhook():
    raw = request.get_data()  # raw bytes, before JSON parsing
    if not verify_webhook_signature(os.environ["PCP_WEBHOOK_SECRET"], request.headers.get(WEBHOOK_SIGNATURE_HEADER), raw):
        return "Invalid signature", 400
    event = json.loads(raw)
    if event["type"] == "scan.completed":
        print("Scan done:", event["data"]["scan"]["id"])
    elif event["type"] == "scan.failed":
        print("Scan failed:", event["data"]["scan"]["id"])
    return "", 200
```

An event can be delivered more than once (retries). Use its `id` to ignore repeats.

## Methods

| Method | API call |
|---|---|
| `create_scan(text, tools, name=None)` | `POST /scans` |
| `get_scan(scan_id, include_text=False)` | `GET /scans/{id}` |
| `list_scans(page=None, limit=None)` | `GET /scans` |
| `get_account()` | `GET /account` |
| `wait_for_scan(scan_id, timeout=300, interval=2, max_interval=10)` | Polls until `completed` or `failed` |
| `verify_webhook_signature(secret, header, body, tolerance=300, now=None)` | Checks a webhook's `PCP-Signature` (module function, no API call) |

`wait_for_scan` grows the delay by 1.5x up to `max_interval`, waits for `Retry-After` on `429`, and raises `ScanTimeoutError` when `timeout` passes.

Failed calls raise `PlagiarismCheckerPlusError` with `status`, `code` (such as `trial_exhausted`, `insufficient_words`, `text_too_short`), `retry_after`, `body` (the parsed response) and `details` (its `error` object).

Run the tests with `python -m pytest` (or `python -m unittest discover -s tests` with `PYTHONPATH=src`).

## Error codes

Failed calls raise `PlagiarismCheckerPlusError`. It carries the HTTP status and the API error code (constants in `ErrorCodes`):

| Code | Status | Meaning |
|---|---|---|
| `invalid_request`, `invalid_json` | 400 | The request body or parameters are not valid. |
| `text_too_short` | 400 | Plagiarism needs at least 30 words, AI detection at least 50. Nothing is charged. |
| `doc_too_long` | 400 | The text is longer than the account allows per check. |
| `unauthorized`, `invalid_api_key`, `key_revoked` | 401 | Missing, unknown or revoked API key. |
| `trial_exhausted` | 402 | The free API trial (2,000 words) cannot cover this request. Includes `wordsNeeded`, `trialRemaining`, `trialTotal` and `billingUrl`. Buy words or choose an API plan; test keys stay free. Nothing is charged. |
| `insufficient_words` | 402 | Not enough words across all sources. Includes `wordsNeeded`, `wordsAvailable`, `balances` and `billingUrl`. Nothing is charged. |
| `key_cap_reached` | 402 | This key's monthly word cap would be exceeded. Includes `wordsNeeded`, `monthlyWordCap` and `usedThisMonth`. Raise the cap in the developer portal. |
| `email_unverified` | 403 | Verify the account's email address first. |
| `forbidden` | 403 | The key cannot access this resource. |
| `not_found` | 404 | No such scan for this key. |
| `rate_limited` | 429 | Too many requests. The client exposes `Retry-After` as `retry_after`. |
| `internal_error` | 500 | Something went wrong on our side. |
| `workers_unavailable` | 503 | Checks are temporarily unavailable. Retry later. |
| `plan_required` | 403 | **Deprecated, no longer returned.** Free accounts now get a free API trial and free test keys. `ErrorCodes.PLAN_REQUIRED` is kept so existing code still works. |

`wait_for_scan` raises `ScanTimeoutError` when it runs out of time. A scan whose status is `failed` is returned, not raised, so check `status`.

## Notes

- **An AI score is a likelihood, not proof** that someone used AI. A similarity score does not decide on its own whether text is plagiarism. Review the result yourself, and do not use either score alone to accuse anyone.
- Test-key scans carry `"sandbox": true` and contain sample data, not a real check.
- Each tool you run is billed at the full word count.
- Plagiarism Checker API overview: https://plagiarismcheckerplus.com/integrations/api
- AI Detector API overview: https://plagiarismcheckerplus.com/ai-detector-api
- API pricing: https://plagiarismcheckerplus.com/api-pricing
- API reference (try requests in the browser): https://app.plagiarismcheckerplus.com/api-docs
- Developer portal (keys, usage, billing, webhooks): https://app.plagiarismcheckerplus.com/developers
- The OpenAPI spec this client follows is in [`spec/openapi.json`](spec/openapi.json).

## Other languages

| Language | Repository | Install |
|---|---|---|
| JavaScript / TypeScript | [plagiarism-checker-plus-js](https://github.com/pcp-tech/plagiarism-checker-plus-js) | `npm install plagiarism-checker-plus` |
| **Python** (this repository) | [plagiarism-checker-plus-python](https://github.com/pcp-tech/plagiarism-checker-plus-python) | `pip install plagiarism-checker-plus` |
| PHP | [plagiarism-checker-plus-php](https://github.com/pcp-tech/plagiarism-checker-plus-php) | `composer require plagiarismcheckerplus/sdk` |
| Ruby | [plagiarism-checker-plus-ruby](https://github.com/pcp-tech/plagiarism-checker-plus-ruby) | `gem install plagiarism_checker_plus` |
| Go | [plagiarism-checker-plus-go](https://github.com/pcp-tech/plagiarism-checker-plus-go) | `go get github.com/pcp-tech/plagiarism-checker-plus-go` |
| Java | [plagiarism-checker-plus-java](https://github.com/pcp-tech/plagiarism-checker-plus-java) | Maven `com.plagiarismcheckerplus:sdk` |
| C# / .NET | [plagiarism-checker-plus-dotnet](https://github.com/pcp-tech/plagiarism-checker-plus-dotnet) | `dotnet add package PlagiarismCheckerPlus` |

## License

MIT. Copyright (c) 2026 Plagiarism Checker Plus.
