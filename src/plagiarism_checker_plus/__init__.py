"""Official Python client for the Plagiarism Checker Plus API."""

from .client import (
    DEFAULT_BASE_URL,
    ErrorCodes,
    PlagiarismCheckerPlus,
    PlagiarismCheckerPlusError,
    ScanTimeoutError,
    WEBHOOK_SIGNATURE_HEADER,
    WEBHOOK_TOLERANCE_SECONDS,
    parse_retry_after,
    verify_webhook_signature,
)

__all__ = [
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
__version__ = "1.1.0"
