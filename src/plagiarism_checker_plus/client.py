"""Client for the Plagiarism Checker Plus public API. Standard library only."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

DEFAULT_BASE_URL = "https://app.plagiarismcheckerplus.com/api/public/v1"
VERSION = "1.1.0"

#: Header that carries the webhook signature.
WEBHOOK_SIGNATURE_HEADER = "PCP-Signature"
#: How old a signed webhook timestamp may be, in seconds, before it is rejected.
WEBHOOK_TOLERANCE_SECONDS = 300

# (method, url, headers, body) -> (status, headers, body)
Transport = Callable[[str, str, Mapping[str, str], Optional[bytes]], Tuple[int, Mapping[str, str], bytes]]


class ErrorCodes:
    #: Deprecated: no longer returned. Free accounts get a free API trial and free test keys.
    PLAN_REQUIRED = "plan_required"
    TEXT_TOO_SHORT = "text_too_short"
    DOC_TOO_LONG = "doc_too_long"
    #: 402: not enough words across all sources (body: wordsNeeded, wordsAvailable, balances, billingUrl).
    INSUFFICIENT_WORDS = "insufficient_words"
    #: 402: the free API trial cannot cover the request (body: wordsNeeded, trialRemaining, trialTotal, billingUrl).
    TRIAL_EXHAUSTED = "trial_exhausted"
    #: 402: the key's monthly word cap would be exceeded (body: wordsNeeded, monthlyWordCap, usedThisMonth).
    KEY_CAP_REACHED = "key_cap_reached"
    INVALID_REQUEST = "invalid_request"
    INVALID_JSON = "invalid_json"
    UNAUTHORIZED = "unauthorized"
    INVALID_API_KEY = "invalid_api_key"
    KEY_REVOKED = "key_revoked"
    EMAIL_UNVERIFIED = "email_unverified"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    WORKERS_UNAVAILABLE = "workers_unavailable"
    INTERNAL_ERROR = "internal_error"


class PlagiarismCheckerPlusError(Exception):
    """A non-2xx response. `code` is the API's error code, such as insufficient_words.

    `body` is the parsed response; `details` is its `error` object, which on 402
    errors carries fields such as wordsNeeded and billingUrl.
    """

    def __init__(
        self,
        message: str,
        status: int = 0,
        code: Optional[str] = None,
        retry_after: Optional[float] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after
        self.body = body

    @property
    def details(self) -> Dict[str, Any]:
        """The response's `error` object (code, message and any detail fields), or {}."""
        error = self.body.get("error") if isinstance(self.body, dict) else None
        return error if isinstance(error, dict) else {}


class ScanTimeoutError(Exception):
    def __init__(self, scan_id: str, timeout: float) -> None:
        super().__init__(f"Scan {scan_id} did not finish within {timeout} seconds")
        self.scan_id = scan_id


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Seconds from a Retry-After header (delta-seconds or HTTP date), or None."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def verify_webhook_signature(
    secret: str,
    header: Optional[str],
    body: Any,
    tolerance: float = WEBHOOK_TOLERANCE_SECONDS,
    now: Optional[float] = None,
) -> bool:
    """Check a webhook's PCP-Signature header against the raw request body.

    The header is ``t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>``.
    Pass the body exactly as received (bytes or str), before JSON parsing.
    Returns False for a missing or malformed header, a wrong signature, or a
    timestamp more than ``tolerance`` seconds from ``now`` (default: the current time).
    Signatures are compared in constant time.
    """
    if not secret or not header or body is None:
        return False
    timestamp: Optional[int] = None
    signatures: List[str] = []
    for part in str(header).split(","):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "t" and value.isdigit() and value.isascii():
            timestamp = int(value)
        elif key == "v1" and value and all(c in "0123456789abcdefABCDEF" for c in value):
            signatures.append(value.lower())
    if timestamp is None or not signatures:
        return False
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        return False
    raw = body.encode("utf-8") if isinstance(body, str) else bytes(body)
    expected = hmac.new(secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def _urllib_transport(timeout: float) -> Transport:
    def send(method: str, url: str, headers: Mapping[str, str], body: Optional[bytes]):
        request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers.items()), error.read()

    return send


class PlagiarismCheckerPlus:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: Optional[Transport] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._transport = transport or _urllib_transport(timeout)

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = self.base_url + path
        params = {k: v for k, v in (query or {}).items() if v is not None}
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": f"plagiarism-checker-plus-python/{VERSION}",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        status, response_headers, raw = self._transport(method, url, headers, data)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            payload = None
        if not 200 <= status < 300:
            error = payload.get("error") if isinstance(payload, dict) else None
            error = error if isinstance(error, dict) else {}
            retry = next((v for k, v in response_headers.items() if k.lower() == "retry-after"), None)
            raise PlagiarismCheckerPlusError(
                error.get("message") or f"HTTP {status}",
                status=status,
                code=error.get("code"),
                retry_after=parse_retry_after(retry),
                body=payload,
            )
        return payload

    def create_scan(self, text: str, tools: Sequence[str], name: Optional[str] = None) -> Dict[str, Any]:
        """Submit text. tools: any of "plagiarism" and "ai_detect"."""
        body: Dict[str, Any] = {"text": text, "tools": list(tools)}
        if name is not None:
            body["name"] = name
        return self._request("POST", "/scans", body=body)

    def get_scan(self, scan_id: str, include_text: bool = False) -> Dict[str, Any]:
        """Read a scan and its results."""
        query = {"include_text": "true"} if include_text else None
        return self._request("GET", "/scans/" + urllib.parse.quote(scan_id, safe=""), query=query)

    def list_scans(self, page: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """List scans, newest first."""
        return self._request("GET", "/scans", query={"page": page, "limit": limit})

    def get_account(self) -> Dict[str, Any]:
        """Plan, word balances, free API trial (``trial``), ``balances``, ``autoTopup`` and this key's ``key`` mode and cap."""
        return self._request("GET", "/account")

    def wait_for_scan(
        self,
        scan_id: str,
        timeout: float = 300.0,
        interval: float = 2.0,
        max_interval: float = 10.0,
        include_text: bool = False,
        sleep: Callable[[float], None] = time.sleep,
    ) -> Dict[str, Any]:
        """Poll until the scan is completed or failed, honouring Retry-After on 429."""
        deadline = time.monotonic() + timeout
        delay = interval
        while True:
            wait = delay
            try:
                scan = self.get_scan(scan_id, include_text=include_text)
                if scan.get("status") in ("completed", "failed"):
                    return scan
                delay = min(delay * 1.5, max_interval)
            except PlagiarismCheckerPlusError as error:
                if error.status != 429:
                    raise
                wait = error.retry_after if error.retry_after is not None else delay
            if time.monotonic() + wait > deadline:
                raise ScanTimeoutError(scan_id, timeout)
            sleep(wait)


__all__: List[str] = [
    "DEFAULT_BASE_URL",
    "ErrorCodes",
    "PlagiarismCheckerPlus",
    "PlagiarismCheckerPlusError",
    "ScanTimeoutError",
    "WEBHOOK_SIGNATURE_HEADER",
    "WEBHOOK_TOLERANCE_SECONDS",
    "parse_retry_after",
    "verify_webhook_signature",
]
