# Elisa Kotiakku — Home Assistant Integration

[![CI](https://github.com/bayleafwalker/ha-elisa-kotiakku/actions/workflows/ci.yml/badge.svg)](https://github.com/bayleafwalker/ha-elisa-kotiakku/actions/workflows/ci.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> [!IMPORTANT]
> Unofficial custom integration. Not affiliated with or endorsed by Elisa.

Custom Home Assistant integration for [Elisa Kotiakku](https://elisa.fi/kotiakku/) home battery systems. It fetches 5-minute measurement windows from the Gridle public API and exposes battery, solar, grid, house, and cumulative energy sensors.

## Highlights

- 5-minute polling aligned with source data granularity
- Full UI config flow (API key only)
- Energy Dashboard-ready cumulative `kWh` sensors (`TOTAL_INCREASING`)
- Historical backfill action: `elisa_kotiakku.backfill_energy`
- Reauthentication + reconfiguration support
- English and Finnish UI translations

## Quick start

1. Install through HACS (recommended) or manually copy `custom_components/elisa_kotiakku`.
2. Restart Home Assistant.
3. Add integration from **Settings -> Devices & Services**.
4. Paste API key from the Elisa Kotiakku app.
5. (Optional) run a backfill after first setup.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** -> three-dot menu -> **Custom repositories**.
3. Add repository URL: `https://github.com/bayleafwalker/ha-elisa-kotiakku` and category **Integration**.
4. Search for **Elisa Kotiakku** and install.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/elisa_kotiakku` into `config/custom_components/`.
2. Restart Home Assistant.

### Installation parameters

| Parameter | Required | Description |
|---|---|---|
| Repository URL | HACS only | `https://github.com/bayleafwalker/ha-elisa-kotiakku` |
| Home Assistant version | Yes | `2024.1` or newer |
| Python version | Yes | `3.12` or newer |

## Configuration

### Get your API key

1. Open **Elisa Kotiakku** mobile app.
2. Go to **Settings -> Data**.
3. Under **API**, select **Create key**.
4. Copy the generated key.

### Add the integration

1. Open **Settings -> Devices & Services -> Add Integration**.
2. Search **Elisa Kotiakku**.
3. Paste API key.
4. Finish setup.

### Options

In **Settings -> Devices & Services -> Elisa Kotiakku -> Configure**:

- `startup_backfill_hours`: automatically import historical windows at startup (`0` disables).

### Configuration parameters

| Parameter | Required | Where set | Description |
|---|---|---|---|
| `api_key` | Yes | Config flow | API key generated in the Kotiakku app |
| `startup_backfill_hours` | No | Options flow | Hours of history to import on startup |

## Supported devices

- Elisa Kotiakku systems with Gridle public API access
- One config entry per API key / installation
- Not supported: local-only inverter interfaces (for example direct Modbus)

## Supported functionality

- Read-only sensors: battery, solar, grid, house, spot price, cumulative energy
- One action: `elisa_kotiakku.backfill_energy`
- Reauthentication and reconfiguration via UI

## Sensor entities

| Entity | Unit | Description |
|---|---|---|
| Battery power | kW | Positive = discharging, negative = charging |
| Battery state of charge | % | Battery SoC (0-100) |
| Battery temperature | °C | Battery temperature |
| Solar power | kW | Solar generation |
| Grid power | kW | Positive = import, negative = export |
| House power | kW | Household consumption |
| Solar to house | kW | Direct solar usage |
| Solar to battery | kW | Solar charging battery |
| Solar to grid | kW | Solar export |
| Grid to house | kW | Grid to load flow |
| Grid to battery | kW | Grid charging battery |
| Battery to house | kW | Battery to load flow |
| Battery to grid | kW | Battery export |
| Spot price | c/kWh | Electricity spot price |
| Grid import energy | kWh | Cumulative import (Energy Dashboard) |
| Grid export energy | kWh | Cumulative export (Energy Dashboard) |
| Solar production energy | kWh | Cumulative solar production |
| House consumption energy | kWh | Cumulative house consumption |
| Battery charge energy | kWh | Cumulative battery charging |
| Battery discharge energy | kWh | Cumulative battery discharging |

## Actions

Use `elisa_kotiakku.backfill_energy` to import historical windows into cumulative energy counters.

```yaml
action: elisa_kotiakku.backfill_energy
data:
  hours: 48
```

Optional fields:

- `entry_id`: target a single integration entry (if multiple configured)
- `start_time`: ISO-8601 datetime (timezone recommended)
- `end_time`: ISO-8601 datetime (defaults to now)
- `hours`: used only when `start_time` is omitted

## Dashboard ideas

Recommended cards for a first dashboard view:

1. Gauge card for battery SoC
2. Entities card for key current values (battery, solar, grid, house, spot price)
3. History graph for power trends
4. Statistics graph for cumulative energy counters

Complete example view: [docs/dashboard-example.yaml](docs/dashboard-example.yaml)

## Automation examples

### Low battery SoC notification

```yaml
automation:
  - alias: Elisa Kotiakku low SoC
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elisa_kotiakku_battery_state_of_charge
        below: 20
    actions:
      - action: persistent_notification.create
        data:
          title: Kotiakku
          message: Battery state of charge is below 20%.
```

### High spot price + high grid import alert

```yaml
automation:
  - alias: Elisa Kotiakku expensive import
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elisa_kotiakku_spot_price
        above: 15
    conditions:
      - condition: numeric_state
        entity_id: sensor.elisa_kotiakku_grid_power
        above: 3
    actions:
      - action: persistent_notification.create
        data:
          title: Kotiakku
          message: Spot price is high and grid import is above 3 kW.
```

More examples: [docs/automation-examples.yaml](docs/automation-examples.yaml)

## Data updates

- Polling interval: every 5 minutes
- Source: Gridle 5-minute averaged windows
- Default polling fetches latest completed window
- Backfill uses same endpoint with `start_time`/`end_time`

## Known limitations

- Cloud dependency: unavailable when Gridle API is down or unreachable
- Read-only integration (no control actions)
- Data granularity limited to 5-minute averages
- API time-range requests limited to max 31 days per request

## Troubleshooting

- `Invalid API key`: generate a new key in app and run reauthentication
- Sensors show `unavailable`: verify internet/API availability
- Backfill imports 0 windows: range likely already processed
- Slow updates after throttling: temporary rate-limit backoff is active

## Removal instructions

1. Open **Settings -> Devices & Services**.
2. Open **Elisa Kotiakku**.
3. Select **Delete**.
4. If manually installed, remove `custom_components/elisa_kotiakku`.
5. Restart Home Assistant.

## Brand assets

- `custom_components/elisa_kotiakku/brand/icon.png`
- `custom_components/elisa_kotiakku/brand/logo.png`

## API reference

- Endpoint: `GET https://residential.gridle.com/api/public/measurements`
- Auth header: `x-api-key`
- Docs: https://residential.gridle.com/api/public/docs

## License

This repository's source code is licensed under the MIT License. See [LICENSE](LICENSE).

## Legal and Attribution

- This project is not affiliated with or endorsed by Elisa.
- Use of the Elisa/Gridle API is subject to the provider's terms and policies.
- This project includes AI-assisted contributions reviewed by maintainers.
