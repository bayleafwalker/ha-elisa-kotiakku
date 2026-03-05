"""Constants for the Elisa Kotiakku integration."""

from datetime import timedelta

DOMAIN = "elisa_kotiakku"

CONF_API_KEY = "api_key"

API_BASE_URL = "https://residential.gridle.com/api/public"
API_MEASUREMENTS_URL = f"{API_BASE_URL}/measurements"

# Polling interval — API provides 5-minute windows, poll every 5 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)

ATTRIBUTION = "Data provided by Elisa Kotiakku (Gridle)"
MANUFACTURER = "Elisa"
MODEL = "Kotiakku"
