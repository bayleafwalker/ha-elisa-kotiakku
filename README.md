# Elisa Kotiakku — Home Assistant Integration

[![CI](https://github.com/bayleafwalker/ha-elisa-kotiakku/actions/workflows/ci.yml/badge.svg)](https://github.com/bayleafwalker/ha-elisa-kotiakku/actions/workflows/ci.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)

> [!IMPORTANT]
> Unofficial custom integration. Not affiliated with or endorsed by Elisa.

Custom Home Assistant integration for [Elisa Kotiakku](https://elisa.fi/kotiakku/) home battery systems. It fetches 5-minute measurement windows from the Gridle public API and exposes battery, solar, grid, house, cumulative energy, tariff, cost, battery-savings, and historical analytics sensors.

## Highlights

- 5-minute polling aligned with source data granularity
- Full UI config flow (API key only)
- Energy Dashboard-ready cumulative `kWh` sensors (`TOTAL_INCREASING`)
- Tariff-aware pricing and battery savings against a no-battery `pörssisähkö` baseline
- Heuristic battery-health and autonomy analytics based on historical performance
- Diagnostic maintenance buttons: backfill energy, rebuild economics, force refresh
- Historical maintenance actions: `elisa_kotiakku.backfill_energy` and `elisa_kotiakku.rebuild_economics`
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

### Upgrading With HACS

- Update the integration in HACS and restart Home Assistant after the download completes.
- Review new options after upgrading. Recent releases added tariff presets, electricity-tax input, power-fee estimation, and battery analytics baseline settings.
- Review newly added entities in the entity registry. Several debug and diagnostic entities are disabled by default.
- If you change tariff inputs after upgrade, run `elisa_kotiakku.rebuild_economics` if you want economics and analytics totals replayed from historical data.
- Bundled tariff presets are dated snapshots, not live tariff feeds. Confirm the preset still matches your contract before relying on it long-term.

### Manual

1. Copy `custom_components/elisa_kotiakku` into `config/custom_components/`.
2. Restart Home Assistant.

### Installation parameters

| Parameter | Required | Description |
|---|---|---|
| Repository URL | HACS only | `https://github.com/bayleafwalker/ha-elisa-kotiakku` |
| Home Assistant version | Yes | `2024.1` or newer |

For normal Home Assistant usage, only the Home Assistant version requirement applies.

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

The options flow uses native Home Assistant selectors (dropdowns, number inputs) with descriptive labels showing preset values where applicable. Fields are grouped by category and ordered so that the most impactful settings (battery capacity, tariff preset) appear first.

- Battery and setup:
  - `startup_backfill_hours`: automatically import historical windows at startup (`0` disables).
- Tariff presets and pricing mode:
  - `tariff_preset`: optional dated transfer-tariff preset.
  - `tariff_mode`: choose `spot_only`, `flat`, `day_night`, or `seasonal_day_night`.
- Retailer and grid pricing:
  - `import_retailer_margin`: retailer import margin in `c/kWh`.
  - `export_retailer_adjustment`: export adjustment in `c/kWh` applied on top of spot.
  - `grid_import_transfer_fee`: import-side transfer fee in `c/kWh`.
  - `grid_export_transfer_fee`: export-side transfer fee in `c/kWh`.
  - `electricity_tax_fee`: import-side electricity tax in `c/kWh`.
  - `day_*` / `night_*`: used for day/night pricing, or winter-day/other-times pricing when using `seasonal_day_night`.
- Power fee estimation:
  - `power_fee_rule`: estimated monthly peak-demand rule.
  - `power_fee_rate`: monthly demand-fee rate in `EUR/kW/month`.
- Analytics baseline:
  - `battery_expected_usable_capacity_kwh`: configured usable capacity baseline for heuristic health, cycle, and backup-runtime estimates.
- Battery cost (payback tracking):
  - `battery_monthly_cost`: monthly instalment or lease cost in `EUR/month`.
  - `battery_total_cost`: total battery system cost in `EUR`.
  - `akkureservihyvitys`: monthly battery reserve compensation in `EUR/month`.

### Configuration parameters

| Category | Parameter | Required | Where set | Sample value | Description |
|---|---|---|---|---|---|
| Setup | `api_key` | Yes | Config flow | `ek_live_abc123...` | API key generated in the Kotiakku app |
| History | `startup_backfill_hours` | No | Options flow | `24` | Hours of history to import on startup |
| Tariff preset | `tariff_preset` | No | Options flow | `caruna_night_2026_01` | Optional dated preset that applies transfer-side defaults |
| Tariff mode | `tariff_mode` | No | Options flow | `day_night` | Pricing mode for import margins and transfer fees |
| Retailer pricing | `import_retailer_margin` | No | Options flow | `0.45` | Retailer import margin in `c/kWh` |
| Retailer pricing | `export_retailer_adjustment` | No | Options flow | `-0.30` | Export price adjustment in `c/kWh` |
| Grid pricing | `grid_import_transfer_fee` | No | Options flow | `5.26` | Flat import transfer fee in `c/kWh` |
| Grid pricing | `grid_export_transfer_fee` | No | Options flow | `0.00` | Export transfer fee in `c/kWh` |
| Taxes | `electricity_tax_fee` | No | Options flow | `2.79` | Import-side electricity tax in `c/kWh` |
| Time-of-use pricing | `day_import_retailer_margin` / `night_import_retailer_margin` | No | Options flow | `0.60` / `0.25` | Day/night import margin in `c/kWh`, or winter-day/other-times margin in seasonal mode |
| Time-of-use pricing | `day_grid_import_transfer_fee` / `night_grid_import_transfer_fee` | No | Options flow | `5.11` / `3.12` | Day/night import transfer fee in `c/kWh`, or winter-day/other-times transfer fee in seasonal mode |
| Power fee | `power_fee_rule` | No | Options flow | `monthly_top3_all_hours` | Estimated monthly power-fee formula |
| Power fee | `power_fee_rate` | No | Options flow | `8.50` | Estimated power-fee rate in `EUR/kW/month` |
| Analytics | `battery_expected_usable_capacity_kwh` | No | Options flow | `10.0` | Configured usable battery capacity baseline for health analytics |
| Battery cost | `battery_monthly_cost` | No | Options flow | `49.00` | Monthly instalment or lease cost in `EUR/month` |
| Battery cost | `battery_total_cost` | No | Options flow | `6000.00` | Total battery system cost in `EUR` |
| Battery cost | `akkureservihyvitys` | No | Options flow | `10.00` | Monthly battery reserve compensation in `EUR/month` |

## Supported devices

- Elisa Kotiakku systems with Gridle public API access
- One config entry per API key / installation
- Not supported: local-only inverter interfaces (for example direct Modbus)

## Pricing model

The integration does not fetch retailer margins, transfer prices, or taxes from the Gridle API. Those are local options that you configure in Home Assistant.

Configured retailer margins, transfer fees, electricity tax, and power-fee rates are treated as household-billing values. Enter them as gross values if you want the published totals to track typical Finnish household billing. The Gridle spot price is used exactly as provided by the API.

Current formulas:

- Import purchase cost = `grid_import_kWh * (spot_price + import_retailer_margin)`
- Import transfer cost = `grid_import_kWh * import_transfer_fee`
- Electricity tax cost = `grid_import_kWh * electricity_tax_fee`
- Export revenue = `grid_export_kWh * (spot_price + export_retailer_adjustment)`
- Export transfer cost = `grid_export_kWh * export_transfer_fee`
- Net site cost = purchase + import transfer + electricity tax + export transfer + power fee - export revenue
- Battery savings = no-battery baseline net cost - actual net cost

`Total battery savings` can be negative if the observed battery behavior underperforms the no-battery baseline for the processed windows.

Asset-attribution helper formulas:

- Solar used in house value = `solar_to_house_kWh * (active import unit price + active import transfer fee + active electricity tax fee)`
- Solar export net value = `solar_to_grid_kWh * (active export unit price - export transfer fee)`
- Battery house supply value = `battery_to_house_kWh * (active import unit price + active import transfer fee + active electricity tax fee)`
- Avoided grid import energy = `solar_to_house_kWh + battery_to_house_kWh`

Battery-savings baseline uses the directional flow fields:

- Baseline import = `grid_to_house + battery_to_house`
- Baseline export = `solar_to_grid + solar_to_battery`

If any required directional field is missing for a window, cost totals still update but battery savings skip that window. The debug sensor `Skipped savings windows` exposes how many windows were skipped in the current economics history.

The attribution value sensors are intentionally narrower than the headline savings sensors:

- `Total battery house supply value` is a gross avoided-import value for battery discharge into the house.
- `Total battery savings` is still the broader battery-versus-no-battery site savings figure and may differ materially because it includes export effects and power-fee effects.
- The integration does not attempt solar-through-battery source tracing in this version.

Default day/night split:

- Day: `07:00-22:00`
- Night: `22:00-07:00`

Seasonal day/night split:

- Winter daytime: `November 1-March 31`, Monday-Saturday, `07:00-22:00`
- Other times: all remaining hours

Current power-fee rules:

- `none`
- `monthly_max_all_hours`
- `monthly_top3_all_hours`
- `monthly_top3_winter_weekday_daytime`

`monthly_top3_winter_weekday_daytime` uses local time, weekdays, and the winter season `November 1-March 31`.

Power-fee totals and the current-month power-fee estimate are monotonic within a live month. If later hourly recalculation would lower the estimate, use `elisa_kotiakku.rebuild_economics` to replay the month from history.

## Battery Health And Autonomy Analytics

The integration now includes a separate historical analytics store built from the same 5-minute measurement windows.

Heuristic battery-health metrics:

- `Estimated usable battery capacity`
- `Estimated battery health`
- `Battery equivalent full cycles`
- `Battery temperature average 30d`
- `Battery high temperature hours 30d`
- `Battery low SoC hours 30d`
- `Battery high SoC hours 30d`

Autonomy and self-sufficiency metrics:

- `Self-sufficiency ratio 30d`
- `Solar self-consumption ratio 30d`
- `Battery house supply ratio 30d`
- `Battery charge from solar ratio 30d`
- `Estimated backup runtime`

Important caveats:

- These health metrics are heuristic estimates, not manufacturer-reported state of health.
- The Gridle API does not expose vendor SOH, cycle counters, or cell-level telemetry.
- `battery_expected_usable_capacity_kwh` is optional. Set it to a realistic usable capacity if you want health percent, equivalent cycles, and backup runtime sensors to report values.
- `Estimated backup runtime` uses the latest instantaneous house load, so it can jump when household demand is very low or spiky.

Capacity estimation method:

- The integration tracks monotonic battery charge/discharge episodes from historical windows.
- A usable-capacity candidate is only accepted when SoC changes by at least `10` percentage points, battery throughput is at least `0.5 kWh`, and the episode remains shorter than `24h`.
- The published capacity estimate is the median of the latest `20` valid candidates.
- Episode energy is measured at the battery terminals, so the heuristic estimate includes conversion and round-trip losses and is not equivalent to manufacturer SOH.

Starter tariff presets bundled in the integration:

- `custom`
- `caruna_general_2026_01`
- `caruna_night_2026_01`
- `caruna_night_seasonal_2026_01`
- `caruna_espoo_general_2026_01`
- `caruna_espoo_night_2026_01`

Preset behavior:

- Presets are versioned snapshots, not live tariff lookups.
- Presets currently apply tariff mode and transfer-side prices when options are saved.
- Retailer margins, export adjustments, and power-fee settings remain user-controlled.
- Switch back to `custom` if you want full manual control of transfer prices.
- The non-Espoo `caruna_*_2026_01` presets are Jan 2026 packaged snapshots backed by the official Caruna Oy residential tariff page effective from `2024-09-01`.

## Battery Payback And Profit Tracking

For batteries purchased with an instalment plan (osamaksu) or lease, the integration can track when monthly savings cover the monthly battery cost, and how long until the total investment is recovered.

The Kotiakku service has a fixed monthly fee that is waived when the user accepts akkureservi (battery reserve for grid balancing). In return, the user receives a fixed monthly compensation (akkureservihyvitys). Since these are mutually exclusive, configuring the akkureservihyvitys amount is sufficient to account for both.

Configuration options (in Options flow):

- `battery_monthly_cost`: monthly instalment or lease cost in EUR. When set, this is treated as the aggregate net monthly cost (user accounts for service fees and compensation). Set to `0` to derive from total cost instead.
- `battery_total_cost`: total battery system cost in EUR. Used for payback estimation. If monthly cost is not set, `total_cost / 120` is used as the monthly cost (10-year assumption), minus akkureservihyvitys.
- `akkureservihyvitys`: monthly compensation for grid reserve participation in EUR. Subtracted from the derived monthly cost (when using total cost), and added to the effective monthly savings rate for payback estimation. Both retroactive (credited for already-tracked months) and forward-looking. Set to `0` if not applicable.

Sensors:

- **Monthly first day of profit**: estimated day-of-month when cumulative battery savings for the current month exceed the effective monthly battery cost. Uses linear interpolation. Returns `1` when the effective monthly cost is zero or negative (already profitable). Returns `None` when cost is not configured or no savings have been recorded.
- **Payback remaining months**: estimated months until cumulative battery savings (including retroactive akkureservi credit) recover the total battery cost. Based on the average monthly energy savings rate plus akkureservihyvitys. Returns `0` when savings already exceed total cost; `None` when total cost is not configured or no savings have been recorded.

## Supported functionality

- Read-only sensors: battery, solar, grid, spot price, cumulative energy, pricing, savings, analytics, and diagnostics
- Diagnostic button entities: `Backfill energy`, `Rebuild economics`, `Force data refresh`
- Maintenance actions: `elisa_kotiakku.backfill_energy`, `elisa_kotiakku.rebuild_economics`
- Display precision configured on all numeric sensors for consistent dashboard rendering
- Reauthentication and reconfiguration via UI

## Sensor entities

### Live measurement sensors

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

### Cumulative energy sensors

| Entity | Unit | Description |
|---|---|---|
| Grid import energy | kWh | Cumulative import (Energy Dashboard) |
| Grid export energy | kWh | Cumulative export (Energy Dashboard) |
| Solar production energy | kWh | Cumulative solar production |
| House consumption energy | kWh | Cumulative house consumption |
| Battery charge energy | kWh | Cumulative battery charging |
| Battery discharge energy | kWh | Cumulative battery discharging |

### Tariff and economics sensors

| Entity | Unit | Description |
|---|---|---|
| Active import unit price | c/kWh | Spot price plus currently active retailer import margin |
| Active export unit price | c/kWh | Spot price plus export adjustment |
| Total purchase cost | EUR | Cumulative grid energy purchase cost |
| Total import transfer cost | EUR | Cumulative import-side transfer cost |
| Total electricity tax cost | EUR | Cumulative import-side electricity tax cost |
| Total export revenue | EUR | Cumulative export compensation |
| Total export transfer cost | EUR | Cumulative export-side transfer cost |
| Total power fee cost | EUR | Cumulative estimated demand-fee cost |
| Total net site electricity cost | EUR | Cumulative net electricity cost |
| Total battery savings | EUR | Cumulative battery savings versus no-battery baseline |
| Total solar used in house value | EUR | Cumulative avoided-import value of direct solar consumption in the house |
| Total solar export net value | EUR | Cumulative net export value of solar sent to grid after export transfer fee |
| Total battery house supply value | EUR | Cumulative gross avoided-import value of battery discharge used in the house |
| Total avoided grid import energy | kWh | Cumulative solar-to-house plus battery-to-house energy |
| Current month power peak | kW | Qualifying monthly peak demand under the chosen rule |
| Current month power fee estimate | EUR | Current month estimated power-fee amount |
| Monthly first day of profit | d | Estimated day of month when savings cover the monthly battery cost |
| Payback remaining months | months | Estimated months until total battery cost is recovered |

### Historical analytics sensors

| Entity | Unit | Description |
|---|---|---|
| Estimated usable battery capacity | kWh | Median heuristic estimate from recent valid charge/discharge episodes |
| Estimated battery health | % | Estimated usable capacity versus configured expected capacity |
| Battery equivalent full cycles | cycles | Lifetime battery throughput divided by configured expected usable capacity |
| Battery temperature average 30d | °C | Weighted battery temperature average across the latest 30 local days |
| Battery high temperature hours 30d | h | Hours at or above the high-temperature threshold during the latest 30 days |
| Battery low SoC hours 30d | h | Hours at or below the low-SoC threshold during the latest 30 days |
| Battery high SoC hours 30d | h | Hours at or above the high-SoC threshold during the latest 30 days |
| Self-sufficiency ratio 30d | % | Share of house consumption not served directly from grid-to-house energy |
| Solar self-consumption ratio 30d | % | Share of solar production consumed locally or stored into the battery |
| Battery house supply ratio 30d | % | Share of house consumption supplied from the battery |
| Battery charge from solar ratio 30d | % | Share of battery charging energy sourced from solar |
| Estimated backup runtime | h | Estimated remaining runtime at current house load and battery SoC |

Disabled by default diagnostic/debug sensors:

- `Configured tariff preset`
- `Active tariff mode`
- `Active tariff period`
- `Configured power fee rule`
- `Active import retailer margin`
- `Active import transfer fee`
- `Active electricity tax fee`
- `Active export retailer adjustment`
- `Active export transfer fee`
- `Usable capacity candidate count`
- `Analytics processed periods`
- `Analytics total day buckets`
- `Analytics rolling day buckets`
- `Skipped savings windows`
- `Economics processed periods`

Most pricing sensors also include helpful attributes such as `last_period_end`, `tariff_mode`, `tariff_period`, and `power_fee_rule`. The new attribution value sensors additionally expose `value_basis`, `includes_power_fee`, `includes_electricity_tax`, and `skipped_directional_windows`.

All numeric sensors declare `suggested_display_precision` so that dashboard cards and history graphs render values with appropriate decimal places without manual template formatting.

### Button entities

| Entity | Category | Description |
|---|---|---|
| Backfill energy | Diagnostic | Import historical measurement windows into cumulative energy, pricing, and analytics counters |
| Rebuild economics | Diagnostic | Recompute pricing, savings, and derived analytics from historical data without touching energy totals |
| Force data refresh | Diagnostic | Trigger an immediate coordinator data refresh outside the normal 5-minute polling cycle |

These buttons provide one-tap access to the same maintenance operations available through actions, useful for quick dashboard controls or when scripting is not needed.

To enable disabled-by-default debug sensors:

1. Open **Settings -> Devices & Services -> Entities**.
2. Filter by `Elisa Kotiakku`.
3. Open the target entity.
4. Enable it from the entity settings.

## Actions

Use `elisa_kotiakku.backfill_energy` to import historical windows into cumulative energy, pricing, and analytics counters.

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

Use `elisa_kotiakku.rebuild_economics` after changing tariff options when you want to recompute pricing, savings, and derived analytics from a known historical range without touching cumulative energy totals.

```yaml
action: elisa_kotiakku.rebuild_economics
data:
  hours: 168
```

## Dashboard ideas

Recommended cards for a first dashboard view:

1. Gauge card for battery SoC
2. Entities card for key current values (battery, solar, grid, house, spot price)
3. Entities or statistic cards for current import/export prices and total battery savings
4. History graph for power trends
5. Statistics graph for cumulative energy counters
6. A dedicated diagnostics card for disabled-by-default tariff debug sensors when tuning formulas

Complete example view: [docs/dashboard-example.yaml](docs/dashboard-example.yaml)
Monthly helper examples: [docs/utility-meter-example.yaml](docs/utility-meter-example.yaml)

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
- Backfill and economics rebuild use the same endpoint with `start_time`/`end_time`

## Known limitations

- Cloud dependency: unavailable when Gridle API is down or unreachable
- Read-only integration (no control actions)
- Data granularity limited to 5-minute averages
- API time-range requests limited to max 31 days per request
- Tariff margins and transfer fees are configured locally; they are not fetched from Gridle
- Power-fee support is an estimate engine, not a guarantee that a DSO invoice will use the same formula

## Troubleshooting

- `Invalid API key`: generate a new key in app and run reauthentication
- Sensors show `unavailable`: verify internet/API availability
- Backfill imports 0 windows: range likely already processed
- Economics look wrong after changing tariff options: run `elisa_kotiakku.rebuild_economics` for the desired history window
- Slow updates after throttling: temporary rate-limit backoff is active

## Development

Developer ergonomics and local contributor workflows are documented in [docs/development.md](docs/development.md).

Release process and pre-release validation are documented in [docs/release-checklist.md](docs/release-checklist.md).

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
