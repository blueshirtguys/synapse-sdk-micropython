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
    def __init__(
        self,
        api_key: str,
        api_url: str,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ):
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

    def publishReadings(self, payload: dict):
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
            s.settimeout(5)
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
