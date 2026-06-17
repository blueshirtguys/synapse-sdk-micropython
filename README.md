# synapse-sdk-micropython

[![Tests](https://github.com/blueshirtguys/synapse-sdk-micropython/actions/workflows/tests.yml/badge.svg)](https://github.com/blueshirtguys/synapse-sdk-micropython/actions/workflows/tests.yml)

MicroPython SDK for publishing device sensor readings to the Synapse API.

## Install

Copy the `synapse/` directory onto your device's filesystem (e.g. via `mpremote cp -r synapse :`),
or install with `mip`:

```python
import mip
mip.install("github:blueshirtguys/synapse-sdk-micropython")
```

## Usage

See [examples/main.py](examples/main.py) for a complete, runnable device script (WiFi connect,
clock sync, periodic publish loop). Minimal version:

```python
import network
import ntptime
import time

from synapse import SynapseClient, HttpError

# Connect to WiFi (adjust for your network setup)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect("your-ssid", "your-password")
while not wlan.isconnected():
    time.sleep(0.5)

# Sync the device clock so recorded_at timestamps are accurate
try:
    ntptime.settime()
except OSError:
    pass  # proceed with whatever time the RTC already has

# Convert MicroPython epoch (2000-01-01) to Unix epoch (1970-01-01)
recorded_at = time.time() + 946684800

client = SynapseClient(
    api_key="sdt_your-token-here=",
    api_url="https://api.synapse.matthewcoleman.dev",
)

try:
    client.publishReadings({"temp": 21.5, "humidity": 47}, recorded_at)
except HttpError as e:
    print("Synapse API rejected the request:", e.status, e)
except OSError as e:
    print("failed to reach Synapse API:", e)
```

## Configuration

| Argument | Description |
|---|---|
| `api_key` | Synapse API key, sent as a Bearer token. |
| `api_url` | Base URL of the API, e.g. `https://api.synapse.matthewcoleman.dev`. Supports `http://` for local/dev endpoints. |
| `max_retries` | Number of retries for transient failures (connection errors, 5xx, 429). Default `3`. Set `0` to disable. |
| `retry_backoff` | Base delay in seconds between retries (grows linearly with attempt number). Default `1.0`. |
| `timeout` | Socket timeout in seconds for connecting/reading. Increase on slow networks (e.g. cellular). Default `5.0`. |
| `on_retry` | Optional `fn(exception, attempt)` called each time a transient failure triggers a retry — useful for logging in the field. Not called on the final failure. Default `None`. |

## Error handling

- `HttpError` (subclass of `OSError`) — raised when the API responds with a non-2xx status after
  any applicable retries. Carries the original status code as `.status`.
- `OSError` — raised for connection-level failures (timeouts, refused connections, TLS handshake
  failures) that persist past `max_retries`.
- `ValueError` — raised for invalid configuration or a malformed `payload` passed to
  `publishReadings`.

## Testing

Validation, URL parsing, retry policy, and status-handling logic are pure Python with no
MicroPython-only dependencies, so they run under plain CPython:

```sh
python3 -m unittest discover -s tests -v
```

This does not exercise the actual socket/TLS transport — that requires real hardware (or the
MicroPython Unix port) since it depends on `usocket`/`ussl` device behavior.

## Local secrets

Never commit your `api_key` or WiFi credentials. Keep them in a `config.json` or `secrets.py` on
the device's filesystem — both are already excluded via `.gitignore`.

## License

[MIT](LICENSE)
