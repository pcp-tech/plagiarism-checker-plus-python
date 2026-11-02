# Plagiarism Checker Plus for Python

Official client for the [Plagiarism Checker Plus API](https://plagiarismcheckerplus.com/integrations/api). Python 3.8+, standard library only, fully typed.

The API needs a paid plan. A key on the free plan returns `403 plan_required`.

```sh
pip install plagiarism-checker-plus
```

```python
import os
from plagiarism_checker_plus import ErrorCodes, PlagiarismCheckerPlus, PlagiarismCheckerPlusError

client = PlagiarismCheckerPlus(os.environ["PCP_API_KEY"])

try:
    scan_id = client.create_scan(essay_text, ["plagiarism", "ai_detect"], name="essay-draft-1")["id"]
    scan = client.wait_for_scan(scan_id)

    plagiarism = scan["results"].get("plagiarism") or {}
    print("Matched:", plagiarism.get("score"), "%")
    for source in plagiarism.get("sources", []):
        print(source["url"])

    # A likelihood, not proof that the text was written by AI.
    print("AI likelihood:", (scan["results"].get("aiDetection") or {}).get("score"), "%")
except PlagiarismCheckerPlusError as error:
    if error.code == ErrorCodes.TEXT_TOO_SHORT:
        print("Send at least 30 words for plagiarism, 50 for AI detection.")
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

## Error handling

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
- API documentation: https://plagiarismcheckerplus.com/integrations/api
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
