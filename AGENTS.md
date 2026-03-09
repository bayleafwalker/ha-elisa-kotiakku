# AGENTS.md — Project Constraints

## Project

Home Assistant custom integration for **Elisa Kotiakku** (home battery service by Elisa Finland). Fetches data from the Gridle public REST API and exposes sensor and button entities in Home Assistant.

## Constraints

- **Python ≥ 3.12**, Home Assistant ≥ 2024.1.
- Uses only `aiohttp` for HTTP (provided by HA core — no extra pip dependencies).
- Single API endpoint: `GET https://residential.gridle.com/api/public/measurements` with `x-api-key` header auth.
- API returns 5-minute averaged time-series data; integration polls every 5 minutes via `DataUpdateCoordinator`.
- Config flow accepts only an API key (no host/port/username).
- All sensor and button entities use `has_entity_name = True` with `translation_key` for naming.
- HACS-compatible repository layout: `custom_components/elisa_kotiakku/`.
- No YAML configuration — UI config flow only.
- API key must be redacted in diagnostics output.
- MIT licensed.
