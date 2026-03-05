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
- Automatic 5-minute polling aligned with API measurement windows

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to **Integrations** → three-dot menu → **Custom repositories**.
3. Add repository URL: `https://github.com/your-username/ha-elisa-kotiakku`  
   Category: **Integration**.
4. Search for "Elisa Kotiakku" and install.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/elisa_kotiakku` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Elisa Kotiakku**.
3. Enter your API key (obtain from https://residential.gridle.com).
4. The integration creates a device with all sensor entities.

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

## API reference

- Endpoint: `GET https://residential.gridle.com/api/public/measurements`
- Auth: `x-api-key` header
- Docs: https://residential.gridle.com/api/public/docs

## License

MIT
