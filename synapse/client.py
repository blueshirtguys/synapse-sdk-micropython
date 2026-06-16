import json
import time

from .errors import HttpError
from ._http_client import HttpClient
from ._retry import retry

_ERROR_MESSAGES = {
    400: "Request invalid unable to publish readings",
    401: "Request unauthorized unable to publish readings",
    403: "Request forbidden unable to publish readings",
}


def _should_retry(e):
    if isinstance(e, HttpError):
        return e.status >= 500 or e.status == 429
    return isinstance(e, OSError)


class SynapseClient:
    """Client for publishing device sensor readings to the Synapse API."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        timeout: float = 5.0,
        on_retry=None,
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
            on_retry: optional callback called as on_retry(exception, attempt)
                each time a transient failure triggers a retry. Useful for
                logging/diagnostics in the field; not called on the final,
                non-retried failure.
        """
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("api_key is required")
        if not isinstance(api_url, str) or not api_url:
            raise ValueError("api_url is required")

        self.api_key = api_key
        self.api_url = api_url
        self._http = HttpClient(api_url, timeout=timeout)
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.on_retry = on_retry

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

        def send():
            body = {
                "readings": {k: v for k, v in payload.items()},
                "recorded_at": time.time(),
            }
            body_bytes = json.dumps(body).encode("utf-8")

            return self._http.post(
                "/api/devices/readings",
                body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )

        status = retry(
            send,
            max_retries=self.max_retries,
            backoff=self.retry_backoff,
            should_retry=_should_retry,
            on_retry=self.on_retry,
        )
        self._check_status(status)

    def _check_status(self, status):
        if 200 <= status < 300:
            return
        message = _ERROR_MESSAGES.get(status, f"{status}: Request failed unknown error")
        raise HttpError(status, message)
