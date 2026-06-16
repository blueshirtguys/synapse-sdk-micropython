import json
import socket
import ssl
import time

from collections import namedtuple

from .errors import HttpError
from ._retry import retry

ApiTarget = namedtuple("ApiTarget", ("host", "port", "use_tls"))


def _should_retry(e):
    if isinstance(e, HttpError):
        return e.status >= 500 or e.status == 429
    return isinstance(e, OSError)


def _parse_api_url(api_url: str):
    scheme, sep, rest = api_url.partition("://")

    if not sep:
        scheme, rest = "https", api_url

    if scheme not in ("http", "https"):
        raise ValueError("api_url must use http:// or https://, got: " + scheme)

    host_port, _, _path = rest.partition("/")

    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError("api_url has an invalid port: " + port_str)
    else:
        host = host_port
        port = 443 if scheme == "https" else 80

    if not host:
        raise ValueError("api_url is missing a host")
    if not (0 < port < 65536):
        raise ValueError("api_url port out of range: " + str(port))

    return ApiTarget(host, port, scheme == "https")


class SynapseClient:
    """Client for publishing device sensor readings to the Synapse API."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        timeout: float = 5.0,
    ):
        """
        Args:
            api_key: Synapse API key, sent as a Bearer token on every request.
            api_url: base URL of the Synapse API, e.g. "https://api.synapse.io".
                Both http:// (plain) and https:// (TLS) are supported; a bare
                host with no scheme is treated as https://.
            max_retries: number of retry attempts for transient failures
                (connection errors, 5xx responses, 429 rate limiting) before
                giving up. Set to 0 to disable retrying.
            retry_backoff: base delay in seconds between retries; the actual
                delay grows linearly with the attempt number (backoff * attempt).
            timeout: socket timeout in seconds for connecting to and reading
                from the API. Increase this on slow/unreliable networks
                (e.g. cellular) to avoid premature timeouts.
        """
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("api_key is required")
        if not isinstance(api_url, str) or not api_url:
            raise ValueError("api_url is required")

        target = _parse_api_url(api_url)

        self.api_key = api_key
        self.api_url = api_url
        self.api_host = target.host
        self.api_port = target.port
        self.use_tls = target.use_tls
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout

    def publishReadings(self, payload: dict):
        """Publish a batch of sensor readings to the Synapse API.

        Args:
            payload: a non-empty dict mapping sensor label (str) to its
                current reading (int or float), e.g. {"temp": 21.5}.

        Raises:
            ValueError: if payload is not a non-empty dict of numeric
                readings keyed by string labels.
            HttpError: if the API rejects the request (e.g. bad auth,
                malformed request) after any applicable retries.
            OSError: if a connection-level failure persists past the
                configured number of retries.
        """
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload must be a non-empty dict of sensor readings")

        for label, value in payload.items():
            if not isinstance(label, str) or not label:
                raise ValueError("payload keys must be non-empty strings")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"payload[{label!r}] must be a number, got {value!r}")

        return retry(
            self._send_readings,
            payload,
            max_retries=self.max_retries,
            backoff=self.retry_backoff,
            should_retry=_should_retry,
        )

    def _send_readings(self, payload: dict):
        body = {
            "readings": {k: v for k, v in payload.items()},
            "recorded_at": time.time(),
        }

        body_bytes = json.dumps(body).encode("utf-8")

        request = (
            "POST /api/devices/readings HTTP/1.1\r\n"
            f"Host: {self.api_host}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Authorization: Bearer {self.api_key}\r\n"
            f"Connection: close\r\n"
            "\r\n"
        )

        s = socket.socket()
        try:
            s.settimeout(self.timeout)
            s.connect((self.api_host, self.api_port))
            if self.use_tls:
                s = ssl.wrap_socket(s, server_hostname=self.api_host)

            s.send(request.encode("utf-8") + body_bytes)

            response = b""
            while True:
                chunk = s.recv(512)
                if not chunk:
                    break
                response += chunk
        finally:
            s.close()

        status = int(response.split(b" ", 2)[1])

        return self._check_status(status)

    def _check_status(self, status):
        if 200 <= status < 300:
            return
        if status == 400:
            raise HttpError(status, "Request invalid unable to publish readings")
        if status == 401:
            raise HttpError(status, "Request unauthorized unable to publish readings")
        if status == 403:
            raise HttpError(status, "Request forbidden unable to publish readings")
        raise HttpError(status, f"{status}: Request failed unknown error")
