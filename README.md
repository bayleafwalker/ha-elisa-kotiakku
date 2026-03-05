# Elisa Kotiakku — Home Assistant Integration

WORK IN PROGRESS

All use on your own responsibility. AI generated code.

Custom Home Assistant integration for [Elisa Kotiakku](https://elisa.fi/kotiakku/) home battery systems. Provides real-time sensor data from your inverter, battery, solar panels, and grid connection via the Gridle public API.

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

## Energy backfill service

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

## API reference

- Endpoint: `GET https://residential.gridle.com/api/public/measurements`
- Auth: `x-api-key` header
- Docs: https://residential.gridle.com/api/public/docs

## License

MIT
