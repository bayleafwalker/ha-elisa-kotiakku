"""Constants for the Elisa Kotiakku integration."""

from datetime import timedelta

DOMAIN = "elisa_kotiakku"

CONF_API_KEY = "api_key"
CONF_STARTUP_BACKFILL_HOURS = "startup_backfill_hours"
CONF_TARIFF_PRESET = "tariff_preset"
CONF_TARIFF_MODE = "tariff_mode"
CONF_IMPORT_RETAILER_MARGIN = "import_retailer_margin"
CONF_EXPORT_RETAILER_ADJUSTMENT = "export_retailer_adjustment"
CONF_GRID_IMPORT_TRANSFER_FEE = "grid_import_transfer_fee"
CONF_GRID_EXPORT_TRANSFER_FEE = "grid_export_transfer_fee"
CONF_ELECTRICITY_TAX_FEE = "electricity_tax_fee"
CONF_DAY_IMPORT_RETAILER_MARGIN = "day_import_retailer_margin"
CONF_NIGHT_IMPORT_RETAILER_MARGIN = "night_import_retailer_margin"
CONF_DAY_GRID_IMPORT_TRANSFER_FEE = "day_grid_import_transfer_fee"
CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE = "night_grid_import_transfer_fee"
CONF_POWER_FEE_RULE = "power_fee_rule"
CONF_POWER_FEE_RATE = "power_fee_rate"
CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH = (
    "battery_expected_usable_capacity_kwh"
)

API_BASE_URL = "https://residential.gridle.com/api/public"
API_MEASUREMENTS_URL = f"{API_BASE_URL}/measurements"

# Polling interval — API provides 5-minute windows, poll every 5 minutes
DEFAULT_SCAN_INTERVAL = timedelta(minutes=5)
DEFAULT_WINDOW_HOURS = DEFAULT_SCAN_INTERVAL.total_seconds() / 3600

SERVICE_BACKFILL_ENERGY = "backfill_energy"
SERVICE_REBUILD_ECONOMICS = "rebuild_economics"
ATTR_ENTRY_ID = "entry_id"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_HOURS = "hours"
DEFAULT_BACKFILL_HOURS = 24
DEFAULT_STARTUP_BACKFILL_HOURS = 0
MAX_BACKFILL_HOURS = 24 * 31

TARIFF_PRESET_CUSTOM = "custom"
TARIFF_PRESET_CARUNA_ESPOO_GENERAL_2026_01 = "caruna_espoo_general_2026_01"
TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01 = "caruna_espoo_night_2026_01"
TARIFF_PRESETS: tuple[str, ...] = (
    TARIFF_PRESET_CUSTOM,
    TARIFF_PRESET_CARUNA_ESPOO_GENERAL_2026_01,
    TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
)

TARIFF_MODE_SPOT_ONLY = "spot_only"
TARIFF_MODE_FLAT = "flat"
TARIFF_MODE_DAY_NIGHT = "day_night"
TARIFF_MODES: tuple[str, ...] = (
    TARIFF_MODE_SPOT_ONLY,
    TARIFF_MODE_FLAT,
    TARIFF_MODE_DAY_NIGHT,
)

POWER_FEE_RULE_NONE = "none"
POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS = "monthly_max_all_hours"
POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS = "monthly_top3_all_hours"
POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME = (
    "monthly_top3_winter_weekday_daytime"
)
POWER_FEE_RULES: tuple[str, ...] = (
    POWER_FEE_RULE_NONE,
    POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME,
)

DEFAULT_TARIFF_MODE = TARIFF_MODE_SPOT_ONLY
DEFAULT_TARIFF_PRESET = TARIFF_PRESET_CUSTOM
DEFAULT_IMPORT_RETAILER_MARGIN = 0.0
DEFAULT_EXPORT_RETAILER_ADJUSTMENT = 0.0
DEFAULT_GRID_IMPORT_TRANSFER_FEE = 0.0
DEFAULT_GRID_EXPORT_TRANSFER_FEE = 0.0
DEFAULT_ELECTRICITY_TAX_FEE = 0.0
DEFAULT_DAY_IMPORT_RETAILER_MARGIN = 0.0
DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN = 0.0
DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE = 0.0
DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE = 0.0
DEFAULT_POWER_FEE_RULE = POWER_FEE_RULE_NONE
DEFAULT_POWER_FEE_RATE = 0.0
DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH = 0.0

ENERGY_TOTAL_KEYS: tuple[str, ...] = (
    "grid_import_energy",
    "grid_export_energy",
    "solar_production_energy",
    "house_consumption_energy",
    "battery_charge_energy",
    "battery_discharge_energy",
)

ECONOMICS_TOTAL_KEYS: tuple[str, ...] = (
    "purchase_cost",
    "import_transfer_cost",
    "electricity_tax_cost",
    "export_revenue",
    "export_transfer_cost",
    "power_fee_cost",
    "net_site_cost",
    "battery_savings",
    "solar_used_in_house_value",
    "solar_export_net_value",
    "battery_house_supply_value",
)

ECONOMICS_DEBUG_KEYS: tuple[str, ...] = (
    "skipped_savings_windows",
    "economics_processed_periods",
)

ECONOMICS_ATTRIBUTION_SKIP_KEYS: tuple[str, ...] = (
    "solar_used_in_house_value",
    "solar_export_net_value",
    "battery_house_supply_value",
)

ANALYTICS_DEBUG_KEYS: tuple[str, ...] = (
    "usable_capacity_candidate_count",
    "analytics_processed_periods",
    "analytics_total_day_buckets",
    "analytics_rolling_day_buckets",
)

ATTRIBUTION = "Data provided by Elisa Kotiakku (Gridle)"
MANUFACTURER = "Elisa"
MODEL = "Kotiakku"
