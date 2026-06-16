"""Example device script: connect to WiFi, sync the clock, and publish a
sensor reading to the Synapse API on a fixed interval.

Copy this onto a device alongside the `synapse/` package (and a `config.py`
or `config.json` of your own, see README.md) as a starting point for real
firmware.
"""

import time

import network
import ntptime

from synapse import HttpError, SynapseClient

WIFI_SSID = "your-ssid"
WIFI_PASSWORD = "your-password"
API_KEY = "your-api-key"
API_URL = "https://api.synapse.io"
PUBLISH_INTERVAL_S = 60


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)


def try_sync_clock():
    try:
        ntptime.settime()
    except OSError:
        pass


def read_sensors():
    """Replace with real sensor reads — this is just a placeholder."""
    return {"temp": 21.5, "humidity": 47}


def main():
    connect_wifi()
    try_sync_clock()

    client = SynapseClient(api_key=API_KEY, api_url=API_URL)

    while True:
        try:
            client.publishReadings(read_sensors())
        except HttpError as e:
            print("Synapse API rejected the request:", e.status, e)
        except OSError as e:
            print("failed to reach Synapse API:", e)

        time.sleep(PUBLISH_INTERVAL_S)


if __name__ == "__main__":
    main()
