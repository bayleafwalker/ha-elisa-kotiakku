# AGENTS.md — ha-elisa-kotiakku

## Tech Stack

Primary language: Python ≥ 3.12. Home Assistant integration (no standalone test runner — use `pytest` with HA test helpers). No extra pip dependencies beyond `aiohttp` (provided by HA core). Markdown for documentation.

## Environment setup

No project-specific environment variables required. No cluster context — this is a HACS-compatible integration deployed via Home Assistant, not a standalone service.

**Validation:** Confirm Python ≥ 3.12 is active before running tests.

## Development workflow

- Run the full test suite after making changes and report pass/fail before committing.
- **Never commit with failing tests.**
- Behavior changes must include updated or new tests in the same commit.
- Keep all integration code inside `custom_components/elisa_kotiakku/`.
- Use only `aiohttp` for HTTP — do not introduce new pip dependencies.

### Self-healing test loop

If tests fail after a change, diagnose the root cause, fix, and re-run — up to **5 cycles** — before escalating. Only escalate if still failing after 5 attempts or if a design decision is required.

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
