"""Energy state storage and measurement processing helpers."""

from __future__ import annotations

from .api import MeasurementData
from .const import ENERGY_TOTAL_KEYS
from .util import measurement_duration_hours as _measurement_duration_hours
from .util import parse_iso8601 as _parse_iso8601


class EnergyStore:
    """Own cumulative energy state and energy-specific processing."""

    def __init__(self) -> None:
        """Initialise runtime energy state."""
        self.totals: dict[str, float] = {key: 0.0 for key in ENERGY_TOTAL_KEYS}
        self.last_period_end: str | None = None
        self.processed_period_ends: set[str] = set()

    def restore(self, stored: object) -> None:
        """Restore persisted cumulative energy values."""
        if not isinstance(stored, dict):
            return

        totals = stored.get("totals")
        if isinstance(totals, dict):
            for key in ENERGY_TOTAL_KEYS:
                value = totals.get(key)
                if isinstance(value, int | float):
                    self.totals[key] = float(value)

        last_period_end = stored.get("last_period_end")
        if isinstance(last_period_end, str):
            self.last_period_end = last_period_end

        processed_periods = stored.get("processed_period_ends")
        if isinstance(processed_periods, list):
            self.processed_period_ends = {
                item for item in processed_periods if isinstance(item, str)
            }

    def as_store_payload(self) -> dict[str, object]:
        """Return JSON-serializable payload for persistence."""
        return {
            "totals": self.totals,
            "last_period_end": self.last_period_end,
            "processed_period_ends": list(self.processed_period_ends),
        }

    def is_unprocessed_period(self, period_end: str) -> bool:
        """Return True if this period is not yet included in energy totals."""
        return period_end not in self.processed_period_ends

    def process_measurement(self, measurement: MeasurementData) -> bool:
        """Apply one measurement window to cumulative energy state.

        Returns True when new state was applied, otherwise False for duplicates.
        """
        if not self.is_unprocessed_period(measurement.period_end):
            return False

        for key, delta in self.measurement_energy_deltas(measurement).items():
            self.totals[key] += delta
        self.processed_period_ends.add(measurement.period_end)
        self.update_last_period_end(measurement.period_end)
        return True

    def get_total(self, key: str) -> float | None:
        """Return current cumulative energy total for the given key."""
        value = self.totals.get(key)
        if value is None:
            return None
        return round(value, 6)

    @property
    def processed_period_count(self) -> int:
        """Return number of period_end markers already processed."""
        return len(self.processed_period_ends)

    def update_last_period_end(self, period_end: str) -> None:
        """Track latest processed energy period end marker."""
        if self.last_period_end is None:
            self.last_period_end = period_end
            return

        current = _parse_iso8601(period_end)
        previous = _parse_iso8601(self.last_period_end)
        if current is not None and previous is not None:
            if current > previous:
                self.last_period_end = period_end
            return

        if period_end > self.last_period_end:
            self.last_period_end = period_end

    def measurement_energy_deltas(
        self, measurement: MeasurementData
    ) -> dict[str, float]:
        """Convert a 5-minute average power sample into energy deltas in kWh."""
        hours = _measurement_duration_hours(
            measurement.period_start,
            measurement.period_end,
        )

        grid_kw = measurement.grid_power_kw or 0.0
        solar_kw = measurement.solar_power_kw or 0.0
        house_kw = measurement.house_power_kw or 0.0
        battery_kw = measurement.battery_power_kw or 0.0

        return {
            "grid_import_energy": max(grid_kw, 0.0) * hours,
            "grid_export_energy": max(-grid_kw, 0.0) * hours,
            "solar_production_energy": max(solar_kw, 0.0) * hours,
            "house_consumption_energy": max(-house_kw, 0.0) * hours,
            "battery_charge_energy": max(-battery_kw, 0.0) * hours,
            "battery_discharge_energy": max(battery_kw, 0.0) * hours,
        }
