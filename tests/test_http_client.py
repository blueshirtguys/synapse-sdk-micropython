import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse._http_client import HttpClient, parse_url


class ParseUrlTests(unittest.TestCase):
    def test_https_default_port(self):
        target = parse_url("https://api.synapse.io")
        self.assertEqual(target.host, "api.synapse.io")
        self.assertEqual(target.port, 443)
        self.assertTrue(target.use_tls)

    def test_http_default_port(self):
        target = parse_url("http://localhost")
        self.assertEqual(target.host, "localhost")
        self.assertEqual(target.port, 80)
        self.assertFalse(target.use_tls)

    def test_explicit_port_overrides_default(self):
        target = parse_url("http://localhost:8000")
        self.assertEqual(target.host, "localhost")
        self.assertEqual(target.port, 8000)
        self.assertFalse(target.use_tls)

    def test_https_with_custom_port_keeps_tls(self):
        target = parse_url("https://api.synapse.io:8443")
        self.assertEqual(target.port, 8443)
        self.assertTrue(target.use_tls)

    def test_strips_trailing_path(self):
        target = parse_url("https://api.synapse.io/v1")
        self.assertEqual(target.host, "api.synapse.io")

    def test_no_scheme_defaults_to_https(self):
        target = parse_url("api.synapse.io")
        self.assertEqual(target.host, "api.synapse.io")
        self.assertEqual(target.port, 443)
        self.assertTrue(target.use_tls)

    def test_rejects_unsupported_scheme(self):
        with self.assertRaises(ValueError):
            parse_url("ftp://example.com")

    def test_rejects_missing_host(self):
        with self.assertRaises(ValueError):
            parse_url("https://")

    def test_rejects_invalid_port(self):
        with self.assertRaises(ValueError):
            parse_url("https://api.synapse.io:notaport")

    def test_rejects_out_of_range_port(self):
        with self.assertRaises(ValueError):
            parse_url("https://api.synapse.io:99999")


class HttpClientInitTests(unittest.TestCase):
    def test_stores_parsed_target_and_timeout(self):
        client = HttpClient("https://api.synapse.io", timeout=10.0)
        self.assertEqual(client.host, "api.synapse.io")
        self.assertEqual(client.port, 443)
        self.assertTrue(client.use_tls)
        self.assertEqual(client.timeout, 10.0)

    def test_default_timeout(self):
        client = HttpClient("https://api.synapse.io")
        self.assertEqual(client.timeout, 5.0)


class BuildRequestTests(unittest.TestCase):
    def test_includes_method_path_and_headers(self):
        client = HttpClient("https://api.synapse.io")
        request_bytes = client._build_request(
            "/api/devices/readings",
            b'{"a": 1}',
            headers={"Authorization": "Bearer key"},
        )
        request = request_bytes.decode("utf-8")

        self.assertTrue(request.startswith("POST /api/devices/readings HTTP/1.1\r\n"))
        self.assertIn("Host: api.synapse.io\r\n", request)
        self.assertIn("Content-Length: 8\r\n", request)
        self.assertIn("Authorization: Bearer key\r\n", request)
        self.assertTrue(request_bytes.endswith(b'{"a": 1}'))


if __name__ == "__main__":
    unittest.main()
