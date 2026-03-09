# Changelog

## 1.1.0 - 2026-03-09

- Added tariff-aware pricing sensors for retailer margin, transfer fees, electricity tax, total site cost, battery savings, and power-fee estimates.
- Added solar and battery attribution sensors for direct-use value, export value, battery house-supply value, and avoided grid-import energy.
- Added historical analytics and heuristic battery-health sensors, including self-sufficiency, solar self-consumption, equivalent cycles, temperature exposure, and backup-runtime estimates.
- Added configurable Finnish tariff modes, power-fee estimation rules, and bundled dated Caruna and Caruna Espoo preset snapshots.
- Added maintenance services for historical backfill and rebuilding economics and analytics from stored history.
- Added diagnostic button entities for one-tap maintenance: backfill energy, rebuild economics, and force data refresh.
- Added `suggested_display_precision` on all numeric sensors for consistent dashboard rendering.
- Improved options flow with native Home Assistant selectors (dropdowns for presets/modes/rules, number inputs with units), reordered fields by importance, and descriptive preset labels.
- Clarified tax-inclusive household billing expectations and documented HACS upgrade considerations for new options and entities.
