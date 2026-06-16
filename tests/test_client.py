import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse.client import SynapseClient, _should_retry
from synapse.errors import HttpError


class ShouldRetryTests(unittest.TestCase):
    def test_retries_5xx(self):
        self.assertTrue(_should_retry(HttpError(500)))
        self.assertTrue(_should_retry(HttpError(503)))

    def test_retries_429(self):
        self.assertTrue(_should_retry(HttpError(429)))

    def test_does_not_retry_4xx(self):
        for status in (400, 401, 403, 404, 422):
            self.assertFalse(_should_retry(HttpError(status)), f"status {status}")

    def test_retries_plain_oserror(self):
        self.assertTrue(_should_retry(OSError("connection refused")))

    def test_does_not_retry_unrelated_exceptions(self):
        self.assertFalse(_should_retry(ValueError("bug")))


def make_client(**overrides):
    kwargs = dict(api_key="test-key", api_url="https://api.synapse.io")
    kwargs.update(overrides)
    return SynapseClient(**kwargs)


class InitValidationTests(unittest.TestCase):
    def test_rejects_missing_api_key(self):
        with self.assertRaises(ValueError):
            make_client(api_key="")

    def test_rejects_non_string_api_key(self):
        with self.assertRaises(ValueError):
            make_client(api_key=123)

    def test_rejects_missing_api_url(self):
        with self.assertRaises(ValueError):
            make_client(api_url="")

    def test_defaults(self):
        client = make_client()
        self.assertEqual(client.max_retries, 3)
        self.assertEqual(client.retry_backoff, 1.0)
        self.assertEqual(client._http.timeout, 5.0)

    def test_timeout_passed_through_to_http_client(self):
        client = make_client(timeout=10.0)
        self.assertEqual(client._http.timeout, 10.0)


class PublishReadingsValidationTests(unittest.TestCase):
    def test_rejects_non_dict_payload(self):
        client = make_client()
        with self.assertRaises(ValueError):
            client.publishReadings(None)
        with self.assertRaises(ValueError):
            client.publishReadings([1, 2, 3])

    def test_rejects_empty_payload(self):
        client = make_client()
        with self.assertRaises(ValueError):
            client.publishReadings({})

    def test_rejects_non_string_keys(self):
        client = make_client()
        with self.assertRaises(ValueError):
            client.publishReadings({1: 2.0})

    def test_rejects_bool_values(self):
        client = make_client()
        with self.assertRaises(ValueError):
            client.publishReadings({"flag": True})

    def test_rejects_non_numeric_values(self):
        client = make_client()
        with self.assertRaises(ValueError):
            client.publishReadings({"temp": "21.5"})


class CheckStatusTests(unittest.TestCase):
    def test_2xx_returns_none(self):
        client = make_client()
        self.assertIsNone(client._check_status(200))
        self.assertIsNone(client._check_status(204))
        self.assertIsNone(client._check_status(299))

    def test_400_raises_http_error(self):
        client = make_client()
        with self.assertRaises(HttpError) as ctx:
            client._check_status(400)
        self.assertEqual(ctx.exception.status, 400)

    def test_401_raises_http_error(self):
        client = make_client()
        with self.assertRaises(HttpError) as ctx:
            client._check_status(401)
        self.assertEqual(ctx.exception.status, 401)

    def test_403_raises_http_error(self):
        client = make_client()
        with self.assertRaises(HttpError) as ctx:
            client._check_status(403)
        self.assertEqual(ctx.exception.status, 403)

    def test_unknown_status_still_carries_real_code(self):
        client = make_client()
        with self.assertRaises(HttpError) as ctx:
            client._check_status(404)
        self.assertEqual(ctx.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
