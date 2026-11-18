# Plagiarism Checker Plus for Python

Official client for the [Plagiarism Checker Plus API](https://plagiarismcheckerplus.com/integrations/api). Python 3.8+, standard library only, fully typed.

Use it to add a **plagiarism checker API** (score plus every matching source) and an **AI detector API** (a likelihood for each sentence) to your app. Overview pages: [Plagiarism Checker API](https://plagiarismcheckerplus.com/integrations/api) · [AI Detector API](https://plagiarismcheckerplus.com/ai-detector-api) · [API reference](https://app.plagiarismcheckerplus.com/api-docs)

The API needs a paid plan. A key on the free plan returns `403 plan_required`. Create a key in the web app under [Settings › API](https://app.plagiarismcheckerplus.com/settings/api).

## Install

```sh
pip install plagiarism-checker-plus
```

The import name is `plagiarism_checker_plus`.

## Quick start

```python
import os
from plagiarism_checker_plus import PlagiarismCheckerPlus

client = PlagiarismCheckerPlus(os.environ["PCP_API_KEY"])

scan_id = client.create_scan(text, ["plagiarism", "ai_detect"])["id"]  # 50+ words for AI detection
scan = client.wait_for_scan(scan_id)  # polls GET /scans/{id} until done

plagiarism = scan["results"]["plagiarism"] or {}
print("Matched:", plagiarism.get("score"), "%", [s["url"] for s in plagiarism.get("sources", [])])
print("AI likelihood:", (scan["results"]["aiDetection"] or {}).get("score"), "%")  # a likelihood, not proof
```

## Handling errors

```python
from plagiarism_checker_plus import ErrorCodes, PlagiarismCheckerPlusError

try:
    scan_id = client.create_scan(essay_text, ["plagiarism", "ai_detect"], name="essay-draft-1")["id"]
    scan = client.wait_for_scan(scan_id)
    if scan["status"] == "failed":
        raise RuntimeError(f"Scan {scan_id} failed")
except PlagiarismCheckerPlusError as error:
    if error.code == ErrorCodes.TEXT_TOO_SHORT:
        print("Send at least 30 words for plagiarism, 50 for AI detection.")
    elif error.code == ErrorCodes.INSUFFICIENT_WORDS:
        print("Out of words (402). Top up or wait for the monthly reset.")
    elif error.code == ErrorCodes.PLAN_REQUIRED:
        print("This key's plan has no API access (403).")
    elif error.status == 429:
        print(f"Rate limited. Retry in {error.retry_after}s.")
    else:
        raise
```

## Methods

| Method | API call |
|---|---|
| `create_scan(text, tools, name=None)` | `POST /scans` |
| `get_scan(scan_id, include_text=False)` | `GET /scans/{id}` |
| `list_scans(page=None, limit=None)` | `GET /scans` |
| `get_account()` | `GET /account` |
| `wait_for_scan(scan_id, timeout=300, interval=2, max_interval=10)` | Polls until `completed` or `failed` |

`wait_for_scan` grows the delay by 1.5× up to `max_interval`, waits for `Retry-After` on `429`, and raises `ScanTimeoutError` when `timeout` passes.

Failed calls raise `PlagiarismCheckerPlusError` with `status`, `code` (such as `plan_required`, `text_too_short`, `doc_too_long`, `insufficient_words`) and `retry_after`.

Run the tests with `python -m unittest discover -s tests` and `PYTHONPATH=src`.

## Error codes

Failed calls raise `PlagiarismCheckerPlusError`. It carries the HTTP status and the API error code:

| Code | Status | Meaning |
|---|---|---|
| `plan_required` | 403 | The key's plan has no API access. The API needs a paid plan. |
| `text_too_short` | 400 | Plagiarism needs at least 30 words, AI detection at least 50. Nothing is charged. |
| `doc_too_long` | 400 | The text is longer than the plan allows per check. |
| `insufficient_words` | 402 | Not enough words left on the account. |

Other codes (for example on `401`, `404`, `429` or `503`) come through as the raw string the API sends. On `429` the client honours `Retry-After`. `wait_for_scan` raises `ScanTimeoutError` when it runs out of time. A scan whose status is `failed` is returned, not raised, so check `status`.

## Notes

- **An AI score is a likelihood, not proof** that someone used AI. A similarity score does not decide on its own whether text is plagiarism. Review the result yourself, and do not use either score alone to accuse anyone.
- **The API needs a paid plan.** A key on the free plan returns `403 plan_required`.
- Each tool you run is billed at the full word count. The rate limit is 60 requests a minute per key.
- Plagiarism Checker API overview: https://plagiarismcheckerplus.com/integrations/api
- AI Detector API overview: https://plagiarismcheckerplus.com/ai-detector-api
- API reference (try requests in the browser): https://app.plagiarismcheckerplus.com/api-docs
- Create an API key: https://app.plagiarismcheckerplus.com/settings/api
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
