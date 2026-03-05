"""Constants for the Elisa Kotiakku integration."""

from datetime import timedelta

DOMAIN = "elisa_kotiakku"

CONF_API_KEY = "api_key"

API_BASE_URL = "https://residential.gridle.com/api/public"
API_MEASUREMENTS_URL = f"{API_BASE_URL}/measurements"

# Polling interval — API provides 5-minute windows, poll every 5 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_WINDOW_HOURS = DEFAULT_SCAN_INTERVAL.total_seconds() / 3600

SERVICE_BACKFILL_ENERGY = "backfill_energy"
ATTR_ENTRY_ID = "entry_id"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_HOURS = "hours"
DEFAULT_BACKFILL_HOURS = 24
MAX_BACKFILL_HOURS = 24 * 31

ENERGY_TOTAL_KEYS: tuple[str, ...] = (
    "grid_import_energy",
    "grid_export_energy",
    "solar_production_energy",
    "house_consumption_energy",
    "battery_charge_energy",
    "battery_discharge_energy",
)

ATTRIBUTION = "Data provided by Elisa Kotiakku (Gridle)"
MANUFACTURER = "Elisa"
MODEL = "Kotiakku"
