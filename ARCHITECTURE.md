# Architecture

## Overview

This is a Home Assistant custom integration that polls the Elisa Kotiakku (Gridle) public REST API and exposes measurement data as sensor entities. It follows the standard HA custom component pattern: config flow → coordinator → platform entities.

```
custom_components/elisa_kotiakku/
├── __init__.py          # Entry point: sets up coordinator, forwards platforms
├── api.py               # Async HTTP client for the Gridle API
├── config_flow.py       # UI-based configuration (API key input + validation)
├── const.py             # Domain, URLs, intervals, device metadata constants
├── coordinator.py       # DataUpdateCoordinator — polls API every 5 min
├── diagnostics.py       # Diagnostics dump (redacts API key)
├── entity.py            # Base entity class (device info, attribution)
├── manifest.json        # HA integration metadata
├── sensor.py            # Sensor platform — power + cumulative energy entities
├── services.yaml        # Service definitions (historical energy backfill)
├── strings.json         # Default UI strings
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
                                                              ▼
                                                  Power sensors + energy sensors
                                                    (SensorEntity instances)
```

### API layer (`api.py`)

- `ElisaKotiakkuApiClient` wraps `aiohttp.ClientSession`.
- Sends `x-api-key` header for authentication.
- `async_get_latest()` — calls the endpoint without time params; returns last complete 5-minute window.
- `async_get_range(start_time, end_time)` — time-range queries (for future use).
- `async_validate_key()` — lightweight auth check used during config flow.
- Raises typed exceptions: `ElisaKotiakkuAuthError` (401/403), `ElisaKotiakkuRateLimitError` (429), `ElisaKotiakkuApiError` (generic).

### Coordinator (`coordinator.py`)

- Subclasses `DataUpdateCoordinator[MeasurementData | None]`.
- 5-minute polling interval matches API's measurement window granularity.
- Translates API exceptions:
  - `ElisaKotiakkuAuthError` → `ConfigEntryAuthFailed` (triggers HA reauth flow)
  - `ElisaKotiakkuRateLimitError` → `UpdateFailed` and temporarily increases coordinator `update_interval` using `Retry-After` when available
  - Other API errors → `UpdateFailed`
- Maintains cumulative energy totals (kWh) derived from each 5-minute window.
- Persists cumulative totals and the last processed `period_end` via HA storage.
- Tracks processed `period_end` values to deduplicate polling + backfill windows.
- Provides `async_backfill_energy(start_time, end_time)` to import historical windows into totals.

### Config flow (`config_flow.py`)

- **User step**: user provides API key; validates with a live API call before creating the entry.
- **Reauthentication flow**: triggered when the coordinator receives a `ConfigEntryAuthFailed`. Prompts for a new API key, validates it, and updates the config entry.
- **Reconfigure flow**: allows changing API key from the UI after setup.
- **Options flow**: supports `startup_backfill_hours` (automatic historical import on startup).
- Uses a SHA-256 fingerprint of API key as `unique_id` to prevent duplicate entries without storing raw secret as identifier.

### Sensor platform (`sensor.py`)

- Declarative sensor descriptions using `SensorEntityDescription` subclass.
- Each description has a `value_fn` lambda that extracts one field from `MeasurementData`.
- 14 measurement sensors covering: battery, solar, grid, house, power-flow breakdown, spot price, temperature.
- 6 cumulative energy sensors (`kWh`, `TOTAL_INCREASING`) for Energy Dashboard usage:
  - grid import/export
  - solar production
  - house consumption
  - battery charge/discharge
- Measurement sensors expose `period_start`/`period_end` attributes.
- Energy sensors expose `last_period_end` (latest window included in cumulative totals).
- `PARALLEL_UPDATES = 0` — updates are centralised through the coordinator.
- `entity_category = DIAGNOSTIC` on `battery_temperature` and `spot_price`.
- `entity_registry_enabled_default = False` on the 7 power-flow breakdown sensors (less commonly needed).

### Entity base (`entity.py`)

- `ElisaKotiakkuEntity` extends `CoordinatorEntity`.
- Sets `has_entity_name = True` (entities named via `translation_key` under the device).
- Single device per config entry (the Kotiakku system).

### Diagnostics (`diagnostics.py`)

- Dumps config (with API key redacted), latest measurement data, and cumulative energy state.

### Services (`services.yaml`)

- `elisa_kotiakku.backfill_energy` imports historical windows via `async_get_range()`.
- Supports optional `entry_id`, `start_time`, `end_time`, and `hours` fields.
- Updates cumulative energy entities without requiring direct database writes.

### Startup Backfill Option

- On setup, the integration can automatically run a backfill for the last `N` hours (`startup_backfill_hours` option).
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
6. **Extra state attributes** — `period_start`/`period_end` attached to every sensor so automations can reason about data freshness.
7. **Secret-safe unique IDs** — config entry identity uses a hash fingerprint, not plain API key text.
8. **Rate-limit-aware polling** — coordinator applies temporary backoff on HTTP 429 and restores default interval after success.
9. **Energy Dashboard compatibility** — cumulative `kWh` counters are derived from 5-minute average power readings.
10. **Controlled backfill** — historical backfill runs through an explicit service call, not automatic bulk imports.

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
| `parallel-updates` | ✅ | `PARALLEL_UPDATES = 0` (coordinator-based) |
| `reauthentication-flow` | ✅ | `async_step_reauth` / `async_step_reauth_confirm` |
| `reconfigure-flow` | ✅ | `async_step_reconfigure` |
| `options-flow` | ✅ | `startup_backfill_hours` option |
| `test-coverage` | ✅ | 91 tests covering all modules |

### Gold
| Rule | Status | Notes |
|---|---|---|
| `devices` | ✅ | Single device per config entry |
| `diagnostics` | ✅ | Redacts API key |
| `entity-category` | ✅ | Diagnostic category on temperature / spot price |
| `entity-device-class` | ✅ | All sensors have appropriate device classes |
| `entity-disabled-by-default` | ✅ | 7 flow-breakdown sensors disabled by default |
| `entity-translations` | ✅ | `translation_key` on all entities |
