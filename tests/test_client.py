import hashlib
import hmac
import json
import unittest

from plagiarism_checker_plus import (
    ErrorCodes,
    PlagiarismCheckerPlus,
    PlagiarismCheckerPlusError,
    ScanTimeoutError,
    WEBHOOK_SIGNATURE_HEADER,
    verify_webhook_signature,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        status, headers_out, payload = self.responses.pop(0)
        return status, headers_out, json.dumps(payload).encode() if payload is not None else b""


class ClientTest(unittest.TestCase):
    def test_create_scan(self):
        t = FakeTransport([(202, {}, {"id": "s1", "status": "processing"})])
        client = PlagiarismCheckerPlus("pcp_test", transport=t)
        self.assertEqual(client.create_scan("text", ["plagiarism"], "draft")["id"], "s1")
        method, url, headers, body = t.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://app.plagiarismcheckerplus.com/api/public/v1/scans")
        self.assertEqual(headers["Authorization"], "Bearer pcp_test")
        self.assertEqual(json.loads(body), {"text": "text", "tools": ["plagiarism"], "name": "draft"})

    def test_query_parameters(self):
        t = FakeTransport([(200, {}, {"id": "s1"}), (200, {}, {"data": []})])
        client = PlagiarismCheckerPlus("k", transport=t)
        client.get_scan("s1", include_text=True)
        client.list_scans(page=2, limit=5)
        self.assertTrue(t.calls[0][1].endswith("/scans/s1?include_text=true"))
        self.assertTrue(t.calls[1][1].endswith("/scans?page=2&limit=5"))

    def test_error_code_and_details(self):
        billing = "https://app.plagiarismcheckerplus.com/developers/billing"
        t = FakeTransport([(402, {}, {"error": {
            "code": "insufficient_words", "message": "Not enough API words",
            "wordsNeeded": 900, "wordsAvailable": 100, "billingUrl": billing,
        }})])
        client = PlagiarismCheckerPlus("k", transport=t)
        with self.assertRaises(PlagiarismCheckerPlusError) as ctx:
            client.create_scan("text", ["plagiarism"])
        self.assertEqual(ctx.exception.status, 402)
        self.assertEqual(ctx.exception.code, ErrorCodes.INSUFFICIENT_WORDS)
        self.assertEqual(ctx.exception.details["billingUrl"], billing)
        self.assertEqual(ctx.exception.details["wordsNeeded"], 900)

    def test_error_code_constants(self):
        self.assertEqual(ErrorCodes.TRIAL_EXHAUSTED, "trial_exhausted")
        self.assertEqual(ErrorCodes.KEY_CAP_REACHED, "key_cap_reached")
        self.assertEqual(ErrorCodes.PLAN_REQUIRED, "plan_required")  # deprecated, kept for compatibility

    def test_wait_honours_retry_after(self):
        t = FakeTransport([
            (200, {}, {"id": "s1", "status": "processing"}),
            (429, {"Retry-After": "3"}, {"error": {"code": "rate_limited", "message": "Slow down"}}),
            (200, {}, {"id": "s1", "status": "completed"}),
        ])
        waits = []
        client = PlagiarismCheckerPlus("k", transport=t)
        scan = client.wait_for_scan("s1", interval=1.0, sleep=waits.append)
        self.assertEqual(scan["status"], "completed")
        self.assertEqual(waits, [1.0, 3.0])

    def test_wait_times_out(self):
        t = FakeTransport([(200, {}, {"id": "s1", "status": "processing"})])
        client = PlagiarismCheckerPlus("k", transport=t)
        with self.assertRaises(ScanTimeoutError):
            client.wait_for_scan("s1", timeout=0.01, interval=1.0, sleep=lambda s: None)



class WebhookSignatureTest(unittest.TestCase):
    secret = "whsec_test_secret"
    body = '{"id":"evt_1","type":"scan.completed","createdAt":"2026-11-18T00:00:00Z","data":{}}'
    t = 1800000000

    def sign(self, ts, payload, key=None):
        key = key or self.secret
        return hmac.new(key.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()

    def test_valid_signature(self):
        header = f"t={self.t},v1={self.sign(self.t, self.body)}"
        self.assertEqual(WEBHOOK_SIGNATURE_HEADER, "PCP-Signature")
        self.assertTrue(verify_webhook_signature(self.secret, header, self.body, now=self.t + 10))
        self.assertTrue(verify_webhook_signature(self.secret, header, self.body.encode(), now=self.t))
        rotated = f"t={self.t},v1={self.sign(self.t, self.body, 'other')},v1={self.sign(self.t, self.body)}"
        self.assertTrue(verify_webhook_signature(self.secret, rotated, self.body, now=self.t))

    def test_rejects_bad_signatures(self):
        header = f"t={self.t},v1={self.sign(self.t, self.body)}"
        self.assertFalse(verify_webhook_signature("whsec_wrong", header, self.body, now=self.t))
        self.assertFalse(verify_webhook_signature(self.secret, header, self.body + " ", now=self.t))
        self.assertFalse(verify_webhook_signature(self.secret, f"v1={self.sign(self.t, self.body)}", self.body, now=self.t))
        self.assertFalse(verify_webhook_signature(self.secret, f"t={self.t}", self.body, now=self.t))
        self.assertFalse(verify_webhook_signature(self.secret, None, self.body, now=self.t))
        self.assertFalse(verify_webhook_signature(self.secret, f"t={self.t},v1=\u00e9\u00e9", self.body, now=self.t))

    def test_tolerance(self):
        header = f"t={self.t},v1={self.sign(self.t, self.body)}"
        self.assertFalse(verify_webhook_signature(self.secret, header, self.body, now=self.t + 301))
        self.assertFalse(verify_webhook_signature(self.secret, header, self.body, now=self.t - 301))
        self.assertTrue(verify_webhook_signature(self.secret, header, self.body, now=self.t + 500, tolerance=600))


if __name__ == "__main__":
    unittest.main()
