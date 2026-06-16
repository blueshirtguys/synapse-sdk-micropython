import json
import socket
import ssl
import time

from .errors import HttpError
from ._retry import retry


def _should_retry(e):
    if isinstance(e, HttpError):
        return e.status >= 500 or e.status == 429
    return isinstance(e, OSError)


class SynapseClient:
    def __init__(self, api_key: str, api_url: str, max_retries: int = 3, retry_backoff: float = 1.0):
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("api_key is required")
        if not isinstance(api_url, str) or not api_url:
            raise ValueError("api_url is required")

        self.api_key = api_key
        self.api_url = api_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    def publishReadings(self, payload: dict):
        return retry(
            self._send_readings, payload,
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
            f"Host: {self.api_url}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Authorization: Bearer {self.api_key}\r\n"
            f"Connection: close\r\n"
            "\r\n"
        )

        s = socket.socket()
        try:
            s.settimeout(5)
            s.connect((self.api_url, 443))
            s = ssl.wrap_socket(s, server_hostname=self.api_url)

            s.send(request.encode("utf-8") + body_bytes)

            response = b""
            while True:
                chunk = s.recv(512)
                if not chunk:
                    break
                response += chunk
        finally:
            s.close()

        status = int(response.split(b" ")[1])

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
