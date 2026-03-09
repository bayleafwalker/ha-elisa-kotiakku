# Architecture

## Overview

This is a Home Assistant custom integration that polls the Elisa Kotiakku (Gridle) public REST API and exposes measurement data as sensor and button entities. It follows the standard HA custom component pattern: config flow → coordinator → platform entities.

```
custom_components/elisa_kotiakku/
├── __init__.py          # Entry point: sets up coordinator, forwards platforms
├── analytics.py         # Historical analytics engine (health, autonomy, rolling stats)
├── api.py               # Async HTTP client for the Gridle API
├── button.py            # Button platform — diagnostic maintenance buttons
├── config_flow.py       # UI-based configuration (API key, tariff, analytics options)
├── const.py             # Domain, URLs, intervals, device metadata, tariff constants
├── coordinator.py       # DataUpdateCoordinator — polls API, energy/economics/analytics state
├── diagnostics.py       # Diagnostics dump (redacts API key)
├── entity.py            # Base entity class (device info, attribution)
├── manifest.json        # HA integration metadata
├── sensor.py            # Sensor platform — measurement, energy, coordinator-derived entities
├── services.yaml        # Service definitions (backfill_energy, rebuild_economics)
├── strings.json         # Default UI strings
├── tariff.py            # Tariff config, presets, time-of-use resolution, pricing helpers
├── util.py              # Shared utilities (ISO 8601 parsing, duration helpers)
├── brand/               # Brand assets (icon.png, logo.png)
└── translations/
    ├── en.json          # English translations
    └── fi.json          # Finnish translations
```

## Data Flow

```
Gridle API  ──HTTP GET──▶  ElisaKotiakkuApiClient  ──▶  ElisaKotiakkuCoordinator
                                                              │
                           (polls every 5 min)                │
                                                              ▼
                                                    MeasurementData dataclass
                                                              │
                          ┌───────────────────────────────────┼──────────────────────────────────┐
                          │                                   │                                  │
                          ▼                                   ▼                                  ▼
               14 measurement sensors              6 cumulative energy        43 coordinator sensors
               (SensorEntity)                      sensors (TOTAL_INCREASING) (tariff, economics,
                                                                               analytics, debug)
                                                              │
                                                              ▼
                                                   3 diagnostic buttons
                                                   (ButtonEntity)
```

### API layer (`api.py`)

- `ElisaKotiakkuApiClient` wraps `aiohttp.ClientSession`.
- Sends `x-api-key` header for authentication.
- `async_get_latest()` — calls the endpoint without time params; returns last complete 5-minute window.
- `async_get_range(start_time, end_time)` — time-range queries for backfill and economics rebuild.
- `async_validate_key()` — lightweight auth check used during config flow.
- Validates response shape: top-level must be a list and each item must be a dict.
- Raises typed exceptions: `ElisaKotiakkuAuthError` (401/403), `ElisaKotiakkuRateLimitError` (429), `ElisaKotiakkuApiError` (generic / response shape / 422).

### Coordinator (`coordinator.py`)

- Subclasses `DataUpdateCoordinator[MeasurementData | None]`.
- 5-minute polling interval matches API's measurement window granularity.
- Translates API exceptions:
  - `ElisaKotiakkuAuthError` → `ConfigEntryAuthFailed` (triggers HA reauth flow)
  - `ElisaKotiakkuRateLimitError` → `UpdateFailed` and temporarily increases coordinator `update_interval` using `Retry-After` when available
  - Other API errors → `UpdateFailed`
- Maintains three independent persistent state stores:
  - **Energy store**: cumulative `kWh` counters derived from each 5-minute window. Tracks processed `period_end` values to deduplicate polling + backfill windows.
  - **Economics store**: tariff-based pricing totals (purchase cost, transfer, tax, export revenue, power fee, battery savings, attribution values). Invalidated on tariff-option changes (tariff signature mismatch).
  - **Analytics store**: historical battery-health and autonomy metrics (daily buckets, capacity episodes, rolling 30-day ratios).
- Provides `async_backfill_energy(start_time, end_time)` to import historical windows into all three stores.
- Provides `async_rebuild_economics(start_time, end_time)` to reset and recompute economics + analytics from historical data without touching cumulative energy totals.
- Builds `TariffConfig` from config entry options; resolves `ActiveTariffRates` per-window using tariff mode, time-of-use schedule, and spot price.
- Tracks monthly power-fee hour buckets, monthly peak demands, and computes power-fee estimates under the configured rule.

### Tariff layer (`tariff.py`)

- `TariffConfig` — frozen dataclass built from config entry options; caches a tariff signature for stale-state detection.
- `ActiveTariffRates` — frozen dataclass with resolved per-window pricing (import/export unit price, margins, transfer fees, tax).
- Time-of-use resolution: day/night split (`07:00-22:00`) and seasonal day/night (`November 1-March 31`, weekdays only).
- Bundled preset snapshots for Caruna and Caruna Espoo transfer tariffs.
- `normalize_tariff_options()` applies preset defaults when a preset is selected.

### Analytics engine (`analytics.py`)

- `AnalyticsState` — mutable state container for daily buckets, capacity episodes, and rolling metrics.
- Heuristic battery capacity estimation from monotonic charge/discharge episodes (SoC delta ≥ 10 pp, energy ≥ 0.5 kWh, duration < 24h). Publishes median of latest 20 valid candidates.
- 30-day rolling analytics: self-sufficiency, solar self-consumption, battery supply ratio, temperature exposure, SoC stress hours.
- `DailyAnalyticsBucket` — aggregated per-day values pruned to maintain the rolling window.

### Config flow (`config_flow.py`)

- **User step**: user provides API key; validates with a live API call before creating the entry.
- **Reauthentication flow**: triggered when the coordinator receives a `ConfigEntryAuthFailed`. Prompts for a new API key, validates it, and updates the config entry.
- **Reconfigure flow**: allows changing API key from the UI after setup.
- **Options flow** (16 fields with native HA selectors):
  - Battery: `battery_expected_usable_capacity_kwh`
  - Data import: `startup_backfill_hours`
  - Tariff preset and mode: `tariff_preset` (dropdown), `tariff_mode` (dropdown)
  - Import pricing: `import_retailer_margin`, `grid_import_transfer_fee`
  - Day/night pricing: `day_import_retailer_margin`, `night_import_retailer_margin`, `day_grid_import_transfer_fee`, `night_grid_import_transfer_fee`
  - Tax and export: `electricity_tax_fee`, `export_retailer_adjustment`, `grid_export_transfer_fee`
  - Power fee: `power_fee_rule` (dropdown), `power_fee_rate`
- Uses `SelectSelector` for dropdowns with `translation_key` for descriptive labels, `NumberSelector` for numeric inputs with units.
- Uses a PBKDF2-HMAC SHA-256 fingerprint of API key as `unique_id` to prevent duplicate entries without storing raw secret as identifier.

### Sensor platform (`sensor.py`)

Three families of sensor descriptions, all declarative:

- **14 measurement sensors** (`ElisaKotiakkuSensorDescription`): battery, solar, grid, house power; 7 directional flow breakdowns; spot price; battery temperature. Each has a `value_fn` lambda extracting one field from `MeasurementData`.
- **6 cumulative energy sensors** (`ElisaKotiakkuEnergySensorDescription`): grid import/export, solar production, house consumption, battery charge/discharge. `state_class=TOTAL_INCREASING` for Energy Dashboard.
- **43 coordinator-derived sensors** (`ElisaKotiakkuCoordinatorSensorDescription`): tariff config debug (4), active tariff rates (8), economics totals (12), attribution values (4), power-fee tracking (2), analytics health/autonomy (12), and debug counters (5). Each has a `value_fn` lambda reading coordinator state.

Total: **63 sensor entities**, of which **25 are disabled by default** (7 flow breakdowns, 3 secondary energy counters, 15 diagnostic/debug coordinator sensors).

- All numeric sensors declare `suggested_display_precision` for consistent dashboard rendering.
- `PARALLEL_UPDATES = 0` — updates are centralised through the coordinator.
- Economics and analytics sensors expose helpful `extra_state_attributes` (e.g. `last_period_end`, `tariff_mode`, `value_basis`, `skipped_windows`).

### Button platform (`button.py`)

- **3 diagnostic maintenance buttons** (`ElisaKotiakkuButtonDescription`):
  - `backfill_energy` — imports last 24 hours of historical windows into energy, economics, and analytics.
  - `rebuild_economics` — resets and rebuilds economics and analytics from the last 24 hours.
  - `force_data_refresh` — triggers immediate coordinator refresh outside normal polling.
- All buttons are `entity_category=DIAGNOSTIC` with `device_class=UPDATE`.
- `PARALLEL_UPDATES = 1` — only one button operation runs at a time.
- Errors are wrapped as `HomeAssistantError` with `translation_key` for localised messages.

### Entity base (`entity.py`)

- `ElisaKotiakkuEntity` extends `CoordinatorEntity`.
- Sets `has_entity_name = True` (entities named via `translation_key` under the device).
- Single device per config entry (the Kotiakku system).

### Utilities (`util.py`)

- `parse_iso8601()` — safe ISO 8601 parser returning `None` on malformed input.
- `measurement_duration_hours()` — calculates window duration with a 5-minute fallback.

### Diagnostics (`diagnostics.py`)

- Dumps config (with API key redacted), latest measurement data, cumulative energy state, economics state, and analytics state.

### Services (`services.yaml`)

Two registered services:

- `elisa_kotiakku.backfill_energy` — imports historical windows via `async_get_range()`. Supports optional `entry_id`, `start_time`, `end_time`, and `hours` fields. Updates energy, economics, and analytics stores.
- `elisa_kotiakku.rebuild_economics` — resets economics and analytics then replays pricing and analytics from historical data. Does not touch cumulative energy totals.
- **Registration pattern**: both services are registered once in `async_setup()` (integration level), not per config entry. Guards prevent double-registration if HA reloads the integration. Services validate that at least one loaded entry exists at call time.
- All service-level validation errors raise `ServiceValidationError` with `translation_domain=DOMAIN` and a `translation_key` so HA renders them as human-readable messages (keys are in `strings.json` under `exceptions`).

### Startup Backfill Option

- On setup, the integration can automatically run a backfill for the last `N` hours (`startup_backfill_hours` option, default 0).
- This is useful for restoring Energy Dashboard continuity after HA downtime/restarts.

## API Schema

Single endpoint: `GET /api/public/measurements`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `start_time` | ISO 8601 datetime | No | Start of range (max 31 days from end) |
| `end_time` | ISO 8601 datetime | No | End of range |

Without parameters: returns the last complete 5-minute measurement window.

Response: JSON array of objects with fields:

| Field | Type | Unit | Sign convention |
|---|---|---|---|
| `period_start` | string | ISO 8601 | — |
| `period_end` | string | ISO 8601 | — |
| `battery_power_kw` | number\|null | kW | + discharging, − charging |
| `state_of_charge_percent` | number\|null | % | 0–100 |
| `solar_power_kw` | number\|null | kW | generation |
| `grid_power_kw` | number\|null | kW | + import, − export |
| `house_power_kw` | number\|null | kW | − consumption |
| `solar_to_house_kw` | number\|null | kW | flow magnitude |
| `solar_to_battery_kw` | number\|null | kW | flow magnitude |
| `solar_to_grid_kw` | number\|null | kW | flow magnitude |
| `grid_to_house_kw` | number\|null | kW | flow magnitude |
| `grid_to_battery_kw` | number\|null | kW | flow magnitude |
| `battery_to_house_kw` | number\|null | kW | flow magnitude |
| `battery_to_grid_kw` | number\|null | kW | flow magnitude |
| `spot_price_cents_per_kwh` | number\|null | c/kWh | — |
| `battery_temperature_celsius` | number\|null | °C | — |

## Key Design Decisions

1. **No pip dependencies** — `aiohttp` is a HA core dependency; no external packages needed.
2. **Cloud polling (not local)** — the Gridle API is a cloud service; `iot_class: cloud_polling`.
3. **Single device per entry** — one API key = one Kotiakku installation = one HA device.
4. **Translation-based entity names** — uses `translation_key` so names are translatable and follow HA naming conventions.
5. **`runtime_data` pattern** — uses the modern `ConfigEntry.runtime_data` (type alias `ElisaKotiakkuConfigEntry`) instead of `hass.data[DOMAIN]` dict.
6. **Extra state attributes** — `period_start`/`period_end` attached to measurement sensors; `last_period_end`, `tariff_mode`, `value_basis` on economics/analytics sensors for data-freshness reasoning.
7. **Secret-safe unique IDs** — config entry identity uses a PBKDF2-HMAC hash fingerprint, not plain API key text.
8. **Rate-limit-aware polling** — coordinator applies temporary backoff on HTTP 429 and restores default interval after success.
9. **Energy Dashboard compatibility** — cumulative `kWh` counters are derived from 5-minute average power readings.
10. **Controlled backfill** — historical backfill runs through an explicit service call or button press, not automatic bulk imports.
11. **Tariff-signature invalidation** — economics state is discarded when tariff options change, preventing stale pricing data from persisting.
12. **Three-store persistence** — energy, economics, and analytics each have independent HA storage files, allowing selective rebuilds.
13. **Display precision** — all sensors declare `suggested_display_precision` so dashboards render values at appropriate decimal places without manual formatting.
14. **Diagnostic buttons** — maintenance operations (backfill, rebuild, refresh) are exposed as button entities in addition to services, enabling one-tap dashboard access.

## HA Integration Quality Scale

Implemented rules by tier:

### Bronze
| Rule | Status | Notes |
|---|---|---|
| `appropriate-polling` | ✅ | 5-min interval matches API granularity |
| `config-flow` | ✅ | UI-only config with `data_description` hints |
| `dependency-transparency` | ✅ | No pip deps (aiohttp is HA core) |
| `entity-unique-id` | ✅ | `{entry_id}_{sensor_key}` |
| `has-entity-name` | ✅ | Translation-key naming |
| `runtime-data` | ✅ | Modern `ConfigEntry.runtime_data` pattern |
| `test-before-configure` | ✅ | API key validated in config flow |
| `test-before-setup` | ✅ | `async_config_entry_first_refresh()` in `async_setup_entry` |
| `unique-config-entry` | ✅ | Hashed API-key fingerprint as `unique_id` + abort-if-configured |

### Silver
| Rule | Status | Notes |
|---|---|---|
| `config-entry-unloading` | ✅ | `async_unload_platforms` in `async_unload_entry` |
| `parallel-updates` | ✅ | `PARALLEL_UPDATES = 0` (sensors), `1` (buttons) |
| `reauthentication-flow` | ✅ | `async_step_reauth` / `async_step_reauth_confirm` |
| `reconfigure-flow` | ✅ | `async_step_reconfigure` |
| `options-flow` | ✅ | 16-field options with native selectors (tariff, pricing, analytics, power fee) |
| `test-coverage` | ✅ | 250 tests, 98 % coverage across all modules |

### Gold
| Rule | Status | Notes |
|---|---|---|
| `devices` | ✅ | Single device per config entry |
| `diagnostics` | ✅ | Redacts API key |
| `entity-category` | ✅ | Diagnostic category on temperature, spot price, tariff debug, analytics debug, and buttons |
| `entity-device-class` | ✅ | All sensors and buttons have appropriate device classes |
| `entity-disabled-by-default` | ✅ | 25 sensors disabled by default (flow breakdowns, secondary energy, debug/diagnostic) |
| `entity-translations` | ✅ | `translation_key` on all 63 sensors and 3 buttons |
