# Elisa Kotiakku 1.1.0

## Upgrade Notes

- New options were added for tariff presets, electricity tax, time-of-use transfer pricing, power-fee estimation, and battery analytics baseline capacity.
- New entities were added for site economics, battery savings, solar value attribution, battery health, autonomy analytics, and debug counters.
- `elisa_kotiakku.rebuild_economics` now rebuilds analytics as well as economics from historical data while leaving cumulative energy totals intact.
- Bundled tariff presets are dated snapshots, not live tariff lookups. Verify they still match your contract before relying on them.
- Several debug and diagnostic entities remain disabled by default. Enable them from the entity registry when needed.

## Included In This Release

- Tariff-aware pricing and savings sensors
- Electricity-tax-inclusive household billing configuration
- Solar and battery value attribution sensors
- Historical analytics and heuristic battery-health sensors
- Caruna and Caruna Espoo starter transfer-tariff presets
- Diagnostic maintenance buttons: backfill energy, rebuild economics, force data refresh
- Display precision on all numeric sensors for consistent dashboard rendering
- Improved options flow with native selectors, reordered fields, and descriptive preset labels
- 250 automated tests with 98% coverage
