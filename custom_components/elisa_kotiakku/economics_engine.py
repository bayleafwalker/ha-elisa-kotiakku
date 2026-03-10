"""Economics state storage and processing helpers."""

from __future__ import annotations

from datetime import datetime

from .api import MeasurementData
from .const import ECONOMICS_ATTRIBUTION_SKIP_KEYS, ECONOMICS_TOTAL_KEYS
from .tariff import ActiveTariffRates, TariffConfig, cents_per_kwh_to_eur
from .util import measurement_duration_hours as _measurement_duration_hours
from .util import parse_iso8601 as _parse_iso8601


class EconomicsEngine:
    """Own economics runtime state and measurement processing."""

    def __init__(self) -> None:
        """Initialise economics runtime state."""
        self.reset_runtime()

    def reset_runtime(self) -> None:
        """Reset all economics state to defaults."""
        self.totals: dict[str, float] = {key: 0.0 for key in ECONOMICS_TOTAL_KEYS}
        self.last_period_end: str | None = None
        self.skipped_savings_window_count = 0
        self.processed_period_ends: set[str] = set()
        self.power_fee_hour_buckets: dict[str, dict[str, dict[str, float]]] = {}
        self.power_fee_monthly_estimates: dict[str, float] = {}
        self.power_fee_monthly_peaks: dict[str, float] = {}
        self.grid_import_monthly_peaks: dict[str, float] = {}
        self.baseline_power_fee_hour_buckets: dict[
            str, dict[str, dict[str, float]]
        ] = {}
        self.baseline_power_fee_monthly_estimates: dict[str, float] = {}
        self.attribution_skipped_window_counts: dict[str, int] = {
            key: 0 for key in ECONOMICS_ATTRIBUTION_SKIP_KEYS
        }
        self.monthly_battery_savings: dict[str, float] = {}

    def restore(self, stored: object, *, expected_tariff_signature: str) -> None:
        """Restore persisted economics values when tariff options still match."""
        self.reset_runtime()
        if not isinstance(stored, dict):
            return

        if stored.get("tariff_signature") != expected_tariff_signature:
            return

        totals = stored.get("totals")
        if isinstance(totals, dict):
            for key in ECONOMICS_TOTAL_KEYS:
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

        skipped = stored.get("skipped_savings_window_count")
        if isinstance(skipped, int):
            self.skipped_savings_window_count = skipped

        self.power_fee_hour_buckets = _load_hour_bucket_store(
            stored.get("power_fee_hour_buckets")
        )
        self.power_fee_monthly_estimates = _load_float_map(
            stored.get("power_fee_monthly_estimates")
        )
        self.power_fee_monthly_peaks = _load_float_map(
            stored.get("power_fee_monthly_peaks")
        )
        self.grid_import_monthly_peaks = _load_float_map(
            stored.get("grid_import_monthly_peaks")
        )
        self.baseline_power_fee_hour_buckets = _load_hour_bucket_store(
            stored.get("baseline_power_fee_hour_buckets")
        )
        self.baseline_power_fee_monthly_estimates = _load_float_map(
            stored.get("baseline_power_fee_monthly_estimates")
        )
        self.attribution_skipped_window_counts = _load_int_map(
            stored.get("attribution_skipped_window_counts"),
            allowed_keys=ECONOMICS_ATTRIBUTION_SKIP_KEYS,
        )
        self.monthly_battery_savings = _load_float_map(
            stored.get("monthly_battery_savings")
        )

    def as_store_payload(self, *, tariff_signature: str) -> dict[str, object]:
        """Return JSON-serializable payload for persistence."""
        return {
            "totals": self.totals,
            "last_period_end": self.last_period_end,
            "processed_period_ends": list(self.processed_period_ends),
            "skipped_savings_window_count": self.skipped_savings_window_count,
            "tariff_signature": tariff_signature,
            "power_fee_hour_buckets": self.power_fee_hour_buckets,
            "power_fee_monthly_estimates": self.power_fee_monthly_estimates,
            "power_fee_monthly_peaks": self.power_fee_monthly_peaks,
            "grid_import_monthly_peaks": self.grid_import_monthly_peaks,
            "baseline_power_fee_hour_buckets": self.baseline_power_fee_hour_buckets,
            "baseline_power_fee_monthly_estimates": (
                self.baseline_power_fee_monthly_estimates
            ),
            "attribution_skipped_window_counts": self.attribution_skipped_window_counts,
            "monthly_battery_savings": self.monthly_battery_savings,
        }

    def is_unprocessed_period(self, period_end: str) -> bool:
        """Return True if this period is not yet included in economics totals."""
        return period_end not in self.processed_period_ends

    def mark_processed(self, period_end: str) -> None:
        """Mark one economics period as processed and update latest marker."""
        self.processed_period_ends.add(period_end)
        self._update_last_period_end(period_end)

    @property
    def processed_period_count(self) -> int:
        """Return number of processed economics periods."""
        return len(self.processed_period_ends)

    def get_total(self, key: str) -> float | None:
        """Return current cumulative economics total for the given key."""
        value = self.totals.get(key)
        if value is None:
            return None
        return round(value, 6)

    def get_debug_value(self, key: str) -> float | int | None:
        """Return one economics debug value exposed as a sensor."""
        if key == "skipped_savings_windows":
            return self.skipped_savings_window_count
        if key == "economics_processed_periods":
            return self.processed_period_count
        return None

    def get_attribution_skipped_window_count(self, key: str) -> int:
        """Return number of skipped windows for one attribution total."""
        return self.attribution_skipped_window_counts.get(key, 0)

    def get_attribution_skipped_window_counts(self) -> dict[str, int]:
        """Return all attribution skip counters."""
        return dict(self.attribution_skipped_window_counts)

    def get_power_fee_monthly_estimates(self) -> dict[str, float]:
        """Return current monthly power-fee estimates."""
        return dict(self.power_fee_monthly_estimates)

    def get_power_fee_monthly_peaks(self) -> dict[str, float]:
        """Return current monthly qualifying peaks."""
        return dict(self.power_fee_monthly_peaks)

    def process_measurement(
        self,
        measurement: MeasurementData,
        *,
        tariff_config: TariffConfig,
    ) -> bool:
        """Process one measurement window into economics totals.

        Returns True when the window was newly processed, otherwise False.
        """
        if not self.is_unprocessed_period(measurement.period_end):
            return False

        timestamp = _measurement_timestamp(measurement)
        if timestamp is None:
            return False

        hours = _measurement_duration_hours(
            measurement.period_start,
            measurement.period_end,
        )
        rates = tariff_config.active_rates(
            timestamp=timestamp,
            spot_price_cents_per_kwh=measurement.spot_price_cents_per_kwh,
        )

        grid_import_kw = max(measurement.grid_power_kw or 0.0, 0.0)
        grid_export_kw = max(-(measurement.grid_power_kw or 0.0), 0.0)
        grid_import_kwh = grid_import_kw * hours
        grid_export_kwh = grid_export_kw * hours

        month_key = timestamp.strftime("%Y-%m")
        if grid_import_kw > self.grid_import_monthly_peaks.get(month_key, 0.0):
            self.grid_import_monthly_peaks[month_key] = grid_import_kw

        purchase_cost = _cost_or_zero(
            rates.import_unit_price_cents_per_kwh, grid_import_kwh
        )
        import_transfer_cost = cents_per_kwh_to_eur(
            rates.import_transfer_fee_cents_per_kwh,
            grid_import_kwh,
        )
        electricity_tax_cost = cents_per_kwh_to_eur(
            rates.electricity_tax_cents_per_kwh,
            grid_import_kwh,
        )
        export_revenue = _cost_or_zero(
            rates.export_unit_price_cents_per_kwh, grid_export_kwh
        )
        export_transfer_cost = cents_per_kwh_to_eur(
            rates.export_transfer_fee_cents_per_kwh,
            grid_export_kwh,
        )
        net_site_cost = (
            purchase_cost
            + import_transfer_cost
            + electricity_tax_cost
            + export_transfer_cost
            - export_revenue
        )

        self.totals["purchase_cost"] += purchase_cost
        self.totals["import_transfer_cost"] += import_transfer_cost
        self.totals["electricity_tax_cost"] += electricity_tax_cost
        self.totals["export_revenue"] += export_revenue
        self.totals["export_transfer_cost"] += export_transfer_cost
        self.totals["net_site_cost"] += net_site_cost

        self._process_measurement_value_attribution(
            measurement=measurement,
            rates=rates,
            hours=hours,
        )

        power_fee_delta = self._update_power_fee_tracking(
            tariff_config=tariff_config,
            timestamp=timestamp,
            import_kw=grid_import_kw,
            hours=hours,
            hour_buckets=self.power_fee_hour_buckets,
            monthly_estimates=self.power_fee_monthly_estimates,
            monthly_peaks=self.power_fee_monthly_peaks,
        )
        self.totals["power_fee_cost"] += power_fee_delta
        self.totals["net_site_cost"] += power_fee_delta

        required_directional_flows = (
            measurement.grid_to_house_kw,
            measurement.battery_to_house_kw,
            measurement.solar_to_grid_kw,
            measurement.solar_to_battery_kw,
        )
        if any(value is None for value in required_directional_flows):
            self.skipped_savings_window_count += 1
            self.mark_processed(measurement.period_end)
            return True

        if (
            rates.import_unit_price_cents_per_kwh is None
            or rates.export_unit_price_cents_per_kwh is None
        ):
            self.mark_processed(measurement.period_end)
            return True

        baseline_import_kw = (
            measurement.grid_to_house_kw or 0.0
        ) + (measurement.battery_to_house_kw or 0.0)
        baseline_export_kw = (
            measurement.solar_to_grid_kw or 0.0
        ) + (measurement.solar_to_battery_kw or 0.0)
        baseline_import_kwh = baseline_import_kw * hours
        baseline_export_kwh = baseline_export_kw * hours
        baseline_net_site_cost = (
            cents_per_kwh_to_eur(
                rates.import_unit_price_cents_per_kwh,
                baseline_import_kwh,
            )
            + cents_per_kwh_to_eur(
                rates.import_transfer_fee_cents_per_kwh,
                baseline_import_kwh,
            )
            + cents_per_kwh_to_eur(
                rates.electricity_tax_cents_per_kwh,
                baseline_import_kwh,
            )
            + cents_per_kwh_to_eur(
                rates.export_transfer_fee_cents_per_kwh,
                baseline_export_kwh,
            )
            - cents_per_kwh_to_eur(
                rates.export_unit_price_cents_per_kwh,
                baseline_export_kwh,
            )
        )
        baseline_power_fee_delta = self._update_power_fee_tracking(
            tariff_config=tariff_config,
            timestamp=timestamp,
            import_kw=baseline_import_kw,
            hours=hours,
            hour_buckets=self.baseline_power_fee_hour_buckets,
            monthly_estimates=self.baseline_power_fee_monthly_estimates,
            monthly_peaks=None,
        )

        savings_delta = (
            baseline_net_site_cost
            + baseline_power_fee_delta
            - net_site_cost
            - power_fee_delta
        )
        self.totals["battery_savings"] += savings_delta
        self.monthly_battery_savings[month_key] = (
            self.monthly_battery_savings.get(month_key, 0.0) + savings_delta
        )
        self.mark_processed(measurement.period_end)
        return True

    def _update_last_period_end(self, period_end: str) -> None:
        """Track latest economics period end marker."""
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

    def _process_measurement_value_attribution(
        self,
        *,
        measurement: MeasurementData,
        rates: ActiveTariffRates,
        hours: float,
    ) -> None:
        """Update solar and battery attribution totals for one window."""
        if measurement.solar_to_house_kw is None:
            self.attribution_skipped_window_counts["solar_used_in_house_value"] += 1
        elif rates.import_unit_price_cents_per_kwh is not None:
            solar_to_house_kwh = max(measurement.solar_to_house_kw, 0.0) * hours
            self.totals["solar_used_in_house_value"] += (
                cents_per_kwh_to_eur(
                    rates.import_unit_price_cents_per_kwh
                    + rates.import_transfer_fee_cents_per_kwh,
                    solar_to_house_kwh,
                )
                + cents_per_kwh_to_eur(
                    rates.electricity_tax_cents_per_kwh,
                    solar_to_house_kwh,
                )
            )

        if measurement.solar_to_grid_kw is None:
            self.attribution_skipped_window_counts["solar_export_net_value"] += 1
        elif rates.export_unit_price_cents_per_kwh is not None:
            solar_to_grid_kwh = max(measurement.solar_to_grid_kw, 0.0) * hours
            self.totals["solar_export_net_value"] += cents_per_kwh_to_eur(
                rates.export_unit_price_cents_per_kwh
                - rates.export_transfer_fee_cents_per_kwh,
                solar_to_grid_kwh,
            )

        if measurement.battery_to_house_kw is None:
            self.attribution_skipped_window_counts["battery_house_supply_value"] += 1
        elif rates.import_unit_price_cents_per_kwh is not None:
            battery_to_house_kwh = max(measurement.battery_to_house_kw, 0.0) * hours
            self.totals["battery_house_supply_value"] += (
                cents_per_kwh_to_eur(
                    rates.import_unit_price_cents_per_kwh
                    + rates.import_transfer_fee_cents_per_kwh,
                    battery_to_house_kwh,
                )
                + cents_per_kwh_to_eur(
                    rates.electricity_tax_cents_per_kwh,
                    battery_to_house_kwh,
                )
            )

    def _update_power_fee_tracking(
        self,
        *,
        tariff_config: TariffConfig,
        timestamp: datetime,
        import_kw: float,
        hours: float,
        hour_buckets: dict[str, dict[str, dict[str, float]]],
        monthly_estimates: dict[str, float],
        monthly_peaks: dict[str, float] | None,
    ) -> float:
        """Update hourly demand buckets and return incremental fee delta."""
        if (
            import_kw <= 0
            or tariff_config.power_fee_rate_eur_per_kw_month <= 0
            or tariff_config.power_fee_rule == "none"
        ):
            return 0.0

        month_key = timestamp.strftime("%Y-%m")
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
        month_buckets = hour_buckets.setdefault(month_key, {})
        hour_bucket = month_buckets.setdefault(
            hour_key,
            {"energy_kwh": 0.0, "duration_hours": 0.0},
        )
        hour_bucket["energy_kwh"] += import_kw * hours
        hour_bucket["duration_hours"] += hours

        hourly_average_demands = {
            key: bucket["energy_kwh"] / bucket["duration_hours"]
            for key, bucket in month_buckets.items()
            if bucket["duration_hours"] > 0
        }
        peak_kw, new_estimate = tariff_config.calculate_monthly_power_fee(
            hourly_average_demands_kw=hourly_average_demands
        )
        previous_estimate = monthly_estimates.get(month_key, 0.0)
        monthly_estimates[month_key] = new_estimate
        if monthly_peaks is not None:
            monthly_peaks[month_key] = peak_kw
        return max(new_estimate - previous_estimate, 0.0)


def _cost_or_zero(unit_price_cents_per_kwh: float | None, energy_kwh: float) -> float:
    """Return EUR cost for a window, defaulting to zero if price is unavailable."""
    if unit_price_cents_per_kwh is None:
        return 0.0
    return cents_per_kwh_to_eur(unit_price_cents_per_kwh, energy_kwh)


def _measurement_timestamp(measurement: MeasurementData) -> datetime | None:
    """Return measurement period start timestamp."""
    return _parse_iso8601(measurement.period_start)


def _load_float_map(raw: object) -> dict[str, float]:
    """Load a flat string->float map from persisted data."""
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): float(value)
        for key, value in raw.items()
        if isinstance(value, int | float)
    }


def _load_int_map(
    raw: object,
    *,
    allowed_keys: tuple[str, ...],
) -> dict[str, int]:
    """Load a flat string->int map from persisted data."""
    loaded = {key: 0 for key in allowed_keys}
    if not isinstance(raw, dict):
        return loaded

    for key, value in raw.items():
        if key in loaded and isinstance(value, int):
            loaded[key] = value
    return loaded


def _load_hour_bucket_store(raw: object) -> dict[str, dict[str, dict[str, float]]]:
    """Load nested hourly bucket data from persisted economics state."""
    if not isinstance(raw, dict):
        return {}

    loaded: dict[str, dict[str, dict[str, float]]] = {}
    for month_key, hours in raw.items():
        if not isinstance(month_key, str) or not isinstance(hours, dict):
            continue

        month_buckets: dict[str, dict[str, float]] = {}
        for hour_key, bucket in hours.items():
            if not isinstance(hour_key, str) or not isinstance(bucket, dict):
                continue
            energy_kwh = bucket.get("energy_kwh")
            duration_hours = bucket.get("duration_hours")
            if isinstance(energy_kwh, int | float) and isinstance(
                duration_hours, int | float
            ):
                month_buckets[hour_key] = {
                    "energy_kwh": float(energy_kwh),
                    "duration_hours": float(duration_hours),
                }
        loaded[month_key] = month_buckets

    return loaded
