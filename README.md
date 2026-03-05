# Elisa Kotiakku — Home Assistant Integration

WORK IN PROGRESS

All use on your own responsibility. AI generated code.

Unofficial custom Home Assistant integration for [Elisa Kotiakku](https://elisa.fi/kotiakku/) home battery systems. Provides real-time sensor data from your inverter, battery, solar panels, and grid connection via the Gridle public API.

## Features

- Battery: power (kW), state of charge (%), temperature (°C)
- Solar: generation power (kW)
- Grid: net import/export power (kW)
- House: total consumption (kW)
- Power-flow breakdown: solar→house, solar→battery, solar→grid, grid→house, grid→battery, battery→house, battery→grid
- Electricity spot price (c/kWh)
- Energy Dashboard-ready cumulative energy sensors (kWh, `TOTAL_INCREASING`)
- Automatic 5-minute polling with API rate-limit backoff support
- Historical backfill service for energy counters (`elisa_kotiakku.backfill_energy`)
- English and Finnish UI translations

## Use cases

- Monitor battery charging/discharging and state of charge in near real time.
- Track solar production, grid import/export, and household demand from one device.
- Feed Home Assistant Energy Dashboard using cumulative `kWh` sensors.
- Backfill missing energy history after Home Assistant downtime.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → three-dot menu → **Custom repositories**.
3. Add repository URL: `https://github.com/bayleafwalker/ha-elisa-kotiakku`  
   Category: **Integration**.
4. Search for "Elisa Kotiakku" and install.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/elisa_kotiakku` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

### Installation parameters

| Parameter | Required | Description |
|---|---|---|
| Repository URL | HACS only | `https://github.com/bayleafwalker/ha-elisa-kotiakku` |
| Home Assistant version | Yes | `2024.1` or newer |
| Python version | Yes | `3.12` or newer |

## Configuration

### Getting your API key

1. Open the **Elisa Kotiakku** app on your smartphone.
2. Go to **Settings** → **Data**.
3. Under **API**, tap **Create key**.
4. Copy the generated API key.

### Adding the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Elisa Kotiakku**.
3. Paste your API key.
4. The integration creates a device with all sensor entities.

### Options

In **Settings → Devices & Services → Elisa Kotiakku → Configure**, you can set:
- `startup_backfill_hours`: automatically backfill historical energy windows on startup (`0` disables this).

Notes:
- Verbose logging is managed by Home Assistant logger settings (not an integration option).
- Per-entity enable/disable is managed from the Entity Registry (no duplicate integration toggle added).

### Configuration parameters

| Parameter | Required | Where set | Description |
|---|---|---|---|
| `api_key` | Yes | Config flow | API key generated in the Elisa Kotiakku app |
| `startup_backfill_hours` | No | Options flow | Hours of historical windows imported on startup (`0` disables startup backfill) |

## Supported devices

- Elisa Kotiakku systems that expose data through the Gridle public API.
- One integration entry represents one API key / one Kotiakku system.
- Unsupported: non-Kotiakku systems and direct local inverter protocols (for example Modbus/LAN-only APIs).

## Supported functionality

- Read-only sensor entities (power, state of charge, temperature, spot price, and cumulative energy).
- One custom action: `elisa_kotiakku.backfill_energy`.
- Reauthentication and reconfiguration from the Home Assistant UI.

## Sensor entities

| Entity | Unit | Description |
|---|---|---|
| Battery power | kW | Positive = discharging, negative = charging |
| Battery state of charge | % | 0–100 % |
| Battery temperature | °C | Battery temperature |
| Solar power | kW | Solar panel generation |
| Grid power | kW | Positive = importing, negative = exporting |
| House power | kW | Household consumption |
| Solar to house | kW | Solar power consumed directly |
| Solar to battery | kW | Solar power charging battery |
| Solar to grid | kW | Solar power exported |
| Grid to house | kW | Grid power consumed |
| Grid to battery | kW | Grid power charging battery |
| Battery to house | kW | Battery power consumed |
| Battery to grid | kW | Battery power exported |
| Spot price | c/kWh | Electricity spot price |
| Grid import energy | kWh | Cumulative grid import for Energy Dashboard |
| Grid export energy | kWh | Cumulative grid export for Energy Dashboard |
| Solar production energy | kWh | Cumulative solar production |
| House consumption energy | kWh | Cumulative house consumption (derived from house power) |
| Battery charge energy | kWh | Cumulative battery charging energy |
| Battery discharge energy | kWh | Cumulative battery discharging energy |

## Actions

Use the built-in service to backfill historical windows into cumulative energy sensors.

```yaml
service: elisa_kotiakku.backfill_energy
data:
  hours: 48
```

Optional fields:
- `entry_id`: target one config entry if you have multiple.
- `start_time`: ISO-8601 datetime (if omitted, `hours` is used).
- `end_time`: ISO-8601 datetime (defaults to now).

## Data updates

- Polling interval: every 5 minutes.
- Source data: 5-minute averaged windows from Gridle API.
- Normal poll reads the latest complete window.
- Historical imports use the same endpoint with `start_time`/`end_time`.

## Known limitations

- Cloud dependency: data is unavailable if Gridle API is down or unreachable.
- Read-only integration: no remote control actions for the battery/inverter.
- Data granularity is limited to 5-minute averages (no sub-minute values).
- API range requests are limited by provider constraints (maximum 31-day span per request).

## Troubleshooting

- `Invalid API key` during setup: regenerate the key in the Kotiakku app and run reauthentication.
- Sensors are `unavailable`: check Home Assistant internet access and Gridle API availability.
- Backfill reports no new windows: requested range has likely already been processed.
- Slow updates after throttling: API rate limiting temporarily increases polling interval.

## Examples

Example backfill for a fixed range:

```yaml
service: elisa_kotiakku.backfill_energy
data:
  start_time: "2026-03-01T00:00:00+02:00"
  end_time: "2026-03-03T00:00:00+02:00"
```

Example automation trigger when battery state of charge drops below 20%:

```yaml
automation:
  - alias: Elisa Kotiakku low SOC
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elisa_kotiakku_battery_state_of_charge
        below: 20
    actions:
      - action: persistent_notification.create
        data:
          title: "Kotiakku"
          message: "Battery state of charge is below 20%."
```

## Removal instructions

1. In Home Assistant, go to **Settings → Devices & Services**.
2. Open **Elisa Kotiakku** and choose **Delete**.
3. If installed manually, remove `custom_components/elisa_kotiakku`.
4. Restart Home Assistant.

## Brand assets

Custom integration brand files are included in:

- `custom_components/elisa_kotiakku/brand/icon.png`
- `custom_components/elisa_kotiakku/brand/logo.png`

If this integration is ever submitted to Home Assistant Core, the same assets should also be submitted to the `home-assistant/brands` repository.

## API reference

- Endpoint: `GET https://residential.gridle.com/api/public/measurements`
- Auth: `x-api-key` header
- Docs: https://residential.gridle.com/api/public/docs

## License

MIT
