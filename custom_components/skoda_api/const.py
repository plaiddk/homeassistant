"""Constants for the Škoda Public API integration."""

from homeassistant.const import Platform

DOMAIN = "skoda_api"
BASE_URL = "https://public.api.connect.skoda-auto.cz"

CONF_VIN = "vin"
CONF_SCAN_INTERVAL_MIN = "scan_interval_minutes"

# API allows 20 requests/hour per VIN (incl. commands); 6 min leaves room for ~10 commands/hour.
DEFAULT_SCAN_INTERVAL_MIN = 6
MIN_SCAN_INTERVAL_MIN = 3

# Delay before refreshing state after a command, so the car has time to report back.
COMMAND_REFRESH_DELAY = 60

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
