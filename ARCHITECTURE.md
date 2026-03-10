# Architecture

## Overview

This Home Assistant custom integration polls the Elisa Kotiakku (Gridle) public API every 5 minutes and exposes measurement, cumulative energy, economics, analytics, and maintenance entities.

Current design emphasizes separation of concerns:

- API access in `api.py`
- Orchestration in `coordinator.py`
- Domain state engines in `energy_store.py`, `economics_engine.py`, and `analytics.py`
- Payback math in `payback.py`
- Sensor platform split into focused modules

## Repository Structure

```text
custom_components/elisa_kotiakku/
├── __init__.py                 # Integration setup + service registration
├── api.py                      # Async Gridle API client + typed exceptions
├── analytics.py                # Historical analytics engine/state
├── energy_store.py             # Cumulative energy state + processing
├── economics_engine.py         # Economics/power-fee/savings state + processing
├── payback.py                  # Pure payback/profit calculations
├── coordinator.py              # DataUpdateCoordinator orchestration layer
├── sensor.py                   # Sensor platform entrypoint (aggregates modules)
├── sensor_measurement.py       # 14 measurement sensors
├── sensor_energy.py            # 6 cumulative energy sensors
├── sensor_derived.py           # 45 coordinator-derived sensors
├── button.py                   # 3 diagnostic buttons
├── config_flow.py              # Config flow + options flow (API key + pricing options)
├── diagnostics.py              # Diagnostics payload with API key redaction
├── entity.py                   # Shared base entity (device info, attribution)
├── tariff.py                   # Tariff config/presets/time-of-use logic
├── util.py                     # Shared datetime/duration helpers
├── const.py                    # Domain constants and option keys
├── services.yaml               # `backfill_energy`, `rebuild_economics`
├── strings.json                # Base UI strings
└── translations/               # en/fi translations
```

## Runtime Flow

```text
Gridle API --> ElisaKotiakkuApiClient --> ElisaKotiakkuCoordinator
                                           |-- EnergyStore
                                           |-- EconomicsEngine
                                           |-- AnalyticsState
                                           '-- Payback helpers
                                                    |
                                   sensor.py platform aggregates entities
                                    |- measurement
                                    |- energy
                                    '- derived
```

## Coordinator Responsibilities

`ElisaKotiakkuCoordinator` is now orchestration-focused:

- Fetch latest/range measurements from `ElisaKotiakkuApiClient`
- Handle API/auth/rate-limit error translation (`ConfigEntryAuthFailed`, `UpdateFailed`)
- Dispatch measurement processing to:
  - `EnergyStore` for cumulative kWh counters
  - `EconomicsEngine` for pricing/savings/power-fee state
  - `AnalyticsState` for historical health/autonomy metrics
- Persist domain stores separately via HA `Store`
- Expose stable getters consumed by sensor entities
- Run backfill/rebuild workflows

### Persistent Stores

Three independent stores are maintained per config entry:

1. Energy store (`..._energy`)
2. Economics store (`..._economics`)
3. Analytics store (`..._analytics`)

Economics state is invalidated when tariff signature changes.

## Sensor Model

Entity counts (current):

- 14 measurement sensors
- 6 cumulative energy sensors
- 45 coordinator-derived sensors
- **65 total sensors**

Buttons:

- 3 diagnostic buttons (`backfill_energy`, `rebuild_economics`, `force_data_refresh`)

Notes:

- `sensor.py` remains the HA platform entrypoint.
- `translation_key` + `has_entity_name = True` are used consistently.
- Existing entity IDs are preserved by keeping sensor keys unchanged.

## Service Layer

Integration-level services are registered once in `__init__.py`:

- `elisa_kotiakku.backfill_energy`
- `elisa_kotiakku.rebuild_economics`

Service flow:

- Resolve target entry/entries
- Validate loaded entries and entry IDs
- Run action through coordinator
- Wrap failures as `ServiceValidationError` with translation keys

## API Contract

Single endpoint used:

- `GET https://residential.gridle.com/api/public/measurements`
- Auth via `x-api-key` header

Usage:

- Latest window fetch for normal polling
- Range fetch for backfill/rebuild

## Design Constraints

- Python >= 3.12
- Home Assistant >= 2024.1
- UI config flow only (no YAML config)
- `aiohttp` only for HTTP (no extra runtime dependencies)
- Diagnostics must redact API key
- HACS-compatible layout under `custom_components/elisa_kotiakku/`

## Testing

Test suite covers coordinator, sensors, config flow, API client, diagnostics, tariff, analytics, payback, buttons, and integration setup paths.

Recent refactor validation includes sensor/coordinator/payback regression runs after module extraction.
