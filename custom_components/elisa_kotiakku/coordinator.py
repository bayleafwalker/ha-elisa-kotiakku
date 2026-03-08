"""DataUpdateCoordinator for Elisa Kotiakku."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .analytics import AnalyticsState
from .api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    ElisaKotiakkuRateLimitError,
    MeasurementData,
)
from .const import (
    CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WINDOW_HOURS,
    DOMAIN,
    ECONOMICS_ATTRIBUTION_SKIP_KEYS,
    ECONOMICS_TOTAL_KEYS,
    ENERGY_TOTAL_KEYS,
)
from .tariff import ActiveTariffRates, TariffConfig, cents_per_kwh_to_eur

_LOGGER = logging.getLogger(__name__)

_ENERGY_STORE_VERSION = 1
_ECONOMICS_STORE_VERSION = 1
_ANALYTICS_STORE_VERSION = 1


class ElisaKotiakkuCoordinator(DataUpdateCoordinator[MeasurementData | None]):
    """Coordinator to poll the Elisa Kotiakku API every 5 minutes."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ElisaKotiakkuApiClient,
        config_entry: ConfigEntry[Any],
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._default_update_interval = DEFAULT_SCAN_INTERVAL
        self.tariff_config = TariffConfig.from_mapping(config_entry.options)
        self._tariff_signature = self.tariff_config.signature()
        self.expected_usable_capacity_kwh = float(
            config_entry.options.get(
                CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
                DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
            )
        )

        self.energy_totals: dict[str, float] = {
            key: 0.0 for key in ENERGY_TOTAL_KEYS
        }
        self.energy_last_period_end: str | None = None
        self._processed_energy_period_ends: set[str] = set()
        self._energy_store: Store[dict[str, Any]] = Store(
            hass,
            _ENERGY_STORE_VERSION,
            f"{DOMAIN}_{config_entry.entry_id}_energy",
        )

        self.economics_totals: dict[str, float] = {}
        self.economics_last_period_end: str | None = None
        self.skipped_savings_window_count = 0
        self._processed_economics_period_ends: set[str] = set()
        self._power_fee_hour_buckets: dict[str, dict[str, dict[str, float]]] = {}
        self._power_fee_monthly_estimates: dict[str, float] = {}
        self._power_fee_monthly_peaks: dict[str, float] = {}
        self._baseline_power_fee_hour_buckets: dict[
            str, dict[str, dict[str, float]]
        ] = {}
        self._baseline_power_fee_monthly_estimates: dict[str, float] = {}
        self._attribution_skipped_window_counts: dict[str, int] = {}
        self._reset_economics_runtime()
        self._economics_store: Store[dict[str, Any]] = Store(
            hass,
            _ECONOMICS_STORE_VERSION,
            f"{DOMAIN}_{config_entry.entry_id}_economics",
        )

        self.analytics_state = AnalyticsState()
        self._analytics_store: Store[dict[str, Any]] = Store(
            hass,
            _ANALYTICS_STORE_VERSION,
            f"{DOMAIN}_{config_entry.entry_id}_analytics",
        )

    async def async_load_energy_state(self) -> None:
        """Restore persisted cumulative energy values."""
        stored = await self._energy_store.async_load()
        if not isinstance(stored, dict):
            return

        totals = stored.get("totals")
        if isinstance(totals, dict):
            for key in ENERGY_TOTAL_KEYS:
                value = totals.get(key)
                if isinstance(value, int | float):
                    self.energy_totals[key] = float(value)

        last_period_end = stored.get("last_period_end")
        if isinstance(last_period_end, str):
            self.energy_last_period_end = last_period_end

        processed_periods = stored.get("processed_period_ends")
        if isinstance(processed_periods, list):
            self._processed_energy_period_ends = {
                item for item in processed_periods if isinstance(item, str)
            }

    async def async_load_economics_state(self) -> None:
        """Restore persisted economics values when tariff options still match."""
        self._reset_economics_runtime()
        stored = await self._economics_store.async_load()
        if not isinstance(stored, dict):
            return

        if stored.get("tariff_signature") != self._tariff_signature:
            _LOGGER.debug("Ignoring stale economics state due to tariff change")
            return

        totals = stored.get("totals")
        if isinstance(totals, dict):
            for key in ECONOMICS_TOTAL_KEYS:
                value = totals.get(key)
                if isinstance(value, int | float):
                    self.economics_totals[key] = float(value)

        last_period_end = stored.get("last_period_end")
        if isinstance(last_period_end, str):
            self.economics_last_period_end = last_period_end

        processed_periods = stored.get("processed_period_ends")
        if isinstance(processed_periods, list):
            self._processed_economics_period_ends = {
                item for item in processed_periods if isinstance(item, str)
            }

        skipped = stored.get("skipped_savings_window_count")
        if isinstance(skipped, int):
            self.skipped_savings_window_count = skipped

        self._power_fee_hour_buckets = _load_hour_bucket_store(
            stored.get("power_fee_hour_buckets")
        )
        self._power_fee_monthly_estimates = _load_float_map(
            stored.get("power_fee_monthly_estimates")
        )
        self._power_fee_monthly_peaks = _load_float_map(
            stored.get("power_fee_monthly_peaks")
        )
        self._baseline_power_fee_hour_buckets = _load_hour_bucket_store(
            stored.get("baseline_power_fee_hour_buckets")
        )
        self._baseline_power_fee_monthly_estimates = _load_float_map(
            stored.get("baseline_power_fee_monthly_estimates")
        )
        self._attribution_skipped_window_counts = _load_int_map(
            stored.get("attribution_skipped_window_counts"),
            allowed_keys=ECONOMICS_ATTRIBUTION_SKIP_KEYS,
        )

    async def async_load_analytics_state(self) -> None:
        """Restore persisted long-term analytics state."""
        stored = await self._analytics_store.async_load()
        self.analytics_state.load(stored)

    async def _async_update_data(self) -> MeasurementData | None:
        """Fetch the latest measurement from the API."""
        try:
            data = await self.client.async_get_latest()
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuRateLimitError as err:
            default_seconds = int(self._default_update_interval.total_seconds())
            backoff_seconds = max(err.retry_after or default_seconds, default_seconds)
            self.update_interval = timedelta(seconds=backoff_seconds)
            raise UpdateFailed(
                f"Rate limited by API, retrying in {backoff_seconds} seconds"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        if self.update_interval != self._default_update_interval:
            self.update_interval = self._default_update_interval

        if data is not None:
            await self.async_process_measurements([data], notify=False)

        return data

    async def async_backfill_energy(
        self,
        start_time: str,
        end_time: str,
    ) -> int:
        """Fetch historical data and update energy and economics state."""
        try:
            measurements = await self.client.async_get_range(start_time, end_time)
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching historical data: {err}") from err

        return await self.async_process_measurements(measurements, notify=True)

    async def async_rebuild_economics(
        self,
        start_time: str,
        end_time: str,
    ) -> int:
        """Reset economics and analytics state and rebuild from history."""
        try:
            measurements = await self.client.async_get_range(start_time, end_time)
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching historical data: {err}") from err

        if not measurements:
            return 0

        self._reset_economics_runtime()
        self.analytics_state.reset()
        await self._async_save_economics_state()
        await self._async_save_analytics_state()

        processed = 0
        for measurement in sorted(measurements, key=lambda item: item.period_end):
            self._process_measurement_economics(measurement)
            self._processed_economics_period_ends.add(measurement.period_end)
            self._update_last_period_end("economics", measurement.period_end)
            self.analytics_state.process_measurement(measurement)
            self.analytics_state.mark_processed(measurement.period_end)
            self._maybe_update_live_measurement(measurement)
            processed += 1

        if processed:
            await self._async_save_economics_state()
            await self._async_save_analytics_state()
            self.async_update_listeners()

        return processed

    async def async_process_measurements(
        self,
        measurements: list[MeasurementData],
        *,
        notify: bool,
    ) -> int:
        """Process one or more windows into energy and economics counters."""
        processed = 0
        energy_changed = False
        economics_changed = False
        analytics_changed = False

        for measurement in sorted(measurements, key=lambda item: item.period_end):
            measurement_processed = False

            if self._is_unprocessed_energy_period(measurement.period_end):
                for key, delta in self._measurement_energy_deltas(measurement).items():
                    self.energy_totals[key] += delta
                self._processed_energy_period_ends.add(measurement.period_end)
                self._update_last_period_end("energy", measurement.period_end)
                energy_changed = True
                measurement_processed = True

            if self._is_unprocessed_economics_period(measurement.period_end):
                self._process_measurement_economics(measurement)
                self._processed_economics_period_ends.add(measurement.period_end)
                self._update_last_period_end("economics", measurement.period_end)
                economics_changed = True
                measurement_processed = True

            if self.analytics_state.is_unprocessed_period(measurement.period_end):
                self.analytics_state.process_measurement(measurement)
                self.analytics_state.mark_processed(measurement.period_end)
                analytics_changed = True
                measurement_processed = True

            if measurement_processed:
                self._maybe_update_live_measurement(measurement)
                processed += 1

        if energy_changed:
            await self._async_save_energy_state()
        if economics_changed:
            await self._async_save_economics_state()
        if analytics_changed:
            await self._async_save_analytics_state()
        if processed and notify:
            self.async_update_listeners()

        return processed

    def get_energy_total(self, key: str) -> float | None:
        """Return current cumulative energy total for the given key."""
        value = self.energy_totals.get(key)
        if value is None:
            return None
        return round(value, 6)

    def get_economics_total(self, key: str) -> float | None:
        """Return current cumulative economics total for the given key."""
        value = self.economics_totals.get(key)
        if value is None:
            return None
        return round(value, 6)

    def get_analytics_value(self, key: str) -> float | None:
        """Return one derived analytics metric."""
        if key == "estimated_usable_battery_capacity":
            value = self.analytics_state.estimated_usable_capacity_kwh()
        elif key == "estimated_battery_health":
            value = self.analytics_state.estimated_battery_health_percent(
                expected_usable_capacity_kwh=self.expected_usable_capacity_kwh
            )
        elif key == "battery_equivalent_full_cycles":
            value = self.analytics_state.battery_equivalent_full_cycles(
                expected_usable_capacity_kwh=self.expected_usable_capacity_kwh
            )
        elif key == "battery_temperature_average_30d":
            value = self.analytics_state.battery_temperature_average_30d()
        elif key == "battery_high_temperature_hours_30d":
            value = self.analytics_state.battery_high_temperature_hours_30d()
        elif key == "battery_low_soc_hours_30d":
            value = self.analytics_state.battery_low_soc_hours_30d()
        elif key == "battery_high_soc_hours_30d":
            value = self.analytics_state.battery_high_soc_hours_30d()
        elif key == "self_sufficiency_ratio_30d":
            value = self.analytics_state.self_sufficiency_ratio_30d()
        elif key == "solar_self_consumption_ratio_30d":
            value = self.analytics_state.solar_self_consumption_ratio_30d()
        elif key == "battery_house_supply_ratio_30d":
            value = self.analytics_state.battery_house_supply_ratio_30d()
        elif key == "battery_charge_from_solar_ratio_30d":
            value = self.analytics_state.battery_charge_from_solar_ratio_30d()
        elif key == "estimated_backup_runtime_hours":
            value = self.analytics_state.estimated_backup_runtime_hours(
                measurement=self.data,
                expected_usable_capacity_kwh=self.expected_usable_capacity_kwh,
            )
        elif key == "total_avoided_grid_import_energy":
            value = self.analytics_state.total_avoided_grid_import_energy_kwh()
        else:
            return None

        if value is None:
            return None
        return round(value, 6)

    def get_active_tariff_rates(self) -> ActiveTariffRates | None:
        """Return active tariff rates for the latest measurement window."""
        if self.data is None:
            return None
        timestamp = _measurement_timestamp(self.data)
        if timestamp is None:
            return None
        return self.tariff_config.active_rates(
            timestamp=timestamp,
            spot_price_cents_per_kwh=self.data.spot_price_cents_per_kwh,
        )

    def get_current_month_power_peak(self) -> float | None:
        """Return current month's qualifying power peak in kW."""
        month_key = self._current_measurement_month_key()
        if month_key is None:
            return None
        return round(self._power_fee_monthly_peaks.get(month_key, 0.0), 6)

    def get_current_month_power_fee_estimate(self) -> float | None:
        """Return current month's power fee estimate in EUR."""
        month_key = self._current_measurement_month_key()
        if month_key is None:
            return None
        return round(self._power_fee_monthly_estimates.get(month_key, 0.0), 6)

    def get_economics_debug_value(self, key: str) -> float | int | None:
        """Return a coordinator debug value exposed as a sensor."""
        if key == "skipped_savings_windows":
            return self.skipped_savings_window_count
        if key == "economics_processed_periods":
            return self.economics_processed_period_count
        return None

    def get_analytics_debug_value(self, key: str) -> int | None:
        """Return an analytics debug value exposed as a sensor."""
        if key == "usable_capacity_candidate_count":
            return self.analytics_state.candidate_count
        if key == "analytics_processed_periods":
            return self.analytics_processed_period_count
        if key == "analytics_total_day_buckets":
            return self.analytics_state.total_day_bucket_count
        if key == "analytics_rolling_day_buckets":
            return self.analytics_state.rolling_bucket_count()
        return None

    def get_attribution_skipped_window_count(self, key: str) -> int:
        """Return the number of windows skipped for one attribution total."""
        return self._attribution_skipped_window_counts.get(key, 0)

    @property
    def energy_processed_period_count(self) -> int:
        """Return number of period_end markers already processed for energy."""
        return len(self._processed_energy_period_ends)

    @property
    def economics_processed_period_count(self) -> int:
        """Return number of period_end markers already processed for economics."""
        return len(self._processed_economics_period_ends)

    @property
    def analytics_last_period_end(self) -> str | None:
        """Return latest analytics period marker."""
        return self.analytics_state.last_period_end

    @property
    def analytics_processed_period_count(self) -> int:
        """Return number of analytics-processed period markers."""
        return self.analytics_state.processed_period_count

    def _reset_economics_runtime(self) -> None:
        """Reset all economics state to defaults."""
        self.economics_totals = {key: 0.0 for key in ECONOMICS_TOTAL_KEYS}
        self.economics_last_period_end = None
        self.skipped_savings_window_count = 0
        self._processed_economics_period_ends = set()
        self._power_fee_hour_buckets = {}
        self._power_fee_monthly_estimates = {}
        self._power_fee_monthly_peaks = {}
        self._baseline_power_fee_hour_buckets = {}
        self._baseline_power_fee_monthly_estimates = {}
        self._attribution_skipped_window_counts = {
            key: 0 for key in ECONOMICS_ATTRIBUTION_SKIP_KEYS
        }

    def _is_unprocessed_energy_period(self, period_end: str) -> bool:
        """Return True if this period is not yet included in energy totals."""
        return period_end not in self._processed_energy_period_ends

    def _is_unprocessed_economics_period(self, period_end: str) -> bool:
        """Return True if this period is not yet included in economics totals."""
        return period_end not in self._processed_economics_period_ends

    def _update_last_period_end(self, domain: str, period_end: str) -> None:
        """Update marker of latest processed period for the requested domain."""
        attr_name = f"{domain}_last_period_end"
        current_value = getattr(self, attr_name)
        if current_value is None:
            setattr(self, attr_name, period_end)
            return

        current = _parse_iso8601(period_end)
        previous = _parse_iso8601(current_value)
        if current is not None and previous is not None:
            if current > previous:
                setattr(self, attr_name, period_end)
            return

        if period_end > current_value:
            setattr(self, attr_name, period_end)

    def _measurement_energy_deltas(
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

    def _process_measurement_economics(self, measurement: MeasurementData) -> None:
        """Convert one measurement into economics totals and power-fee state."""
        timestamp = _measurement_timestamp(measurement)
        if timestamp is None:
            return

        hours = _measurement_duration_hours(
            measurement.period_start,
            measurement.period_end,
        )
        rates = self.tariff_config.active_rates(
            timestamp=timestamp,
            spot_price_cents_per_kwh=measurement.spot_price_cents_per_kwh,
        )

        grid_import_kw = max(measurement.grid_power_kw or 0.0, 0.0)
        grid_export_kw = max(-(measurement.grid_power_kw or 0.0), 0.0)
        grid_import_kwh = grid_import_kw * hours
        grid_export_kwh = grid_export_kw * hours

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

        self.economics_totals["purchase_cost"] += purchase_cost
        self.economics_totals["import_transfer_cost"] += import_transfer_cost
        self.economics_totals["electricity_tax_cost"] += electricity_tax_cost
        self.economics_totals["export_revenue"] += export_revenue
        self.economics_totals["export_transfer_cost"] += export_transfer_cost
        self.economics_totals["net_site_cost"] += net_site_cost

        self._process_measurement_value_attribution(
            measurement=measurement,
            rates=rates,
            hours=hours,
        )

        power_fee_delta = self._update_power_fee_tracking(
            timestamp=timestamp,
            import_kw=grid_import_kw,
            hours=hours,
            hour_buckets=self._power_fee_hour_buckets,
            monthly_estimates=self._power_fee_monthly_estimates,
            monthly_peaks=self._power_fee_monthly_peaks,
        )
        self.economics_totals["power_fee_cost"] += power_fee_delta
        self.economics_totals["net_site_cost"] += power_fee_delta

        required_directional_flows = (
            measurement.grid_to_house_kw,
            measurement.battery_to_house_kw,
            measurement.solar_to_grid_kw,
            measurement.solar_to_battery_kw,
        )
        if any(value is None for value in required_directional_flows):
            self.skipped_savings_window_count += 1
            return

        if (
            rates.import_unit_price_cents_per_kwh is None
            or rates.export_unit_price_cents_per_kwh is None
        ):
            return

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
            timestamp=timestamp,
            import_kw=baseline_import_kw,
            hours=hours,
            hour_buckets=self._baseline_power_fee_hour_buckets,
            monthly_estimates=self._baseline_power_fee_monthly_estimates,
            monthly_peaks=None,
        )

        self.economics_totals["battery_savings"] += (
            baseline_net_site_cost
            + baseline_power_fee_delta
            - net_site_cost
            - power_fee_delta
        )

    def _process_measurement_value_attribution(
        self,
        *,
        measurement: MeasurementData,
        rates: ActiveTariffRates,
        hours: float,
    ) -> None:
        """Update solar and battery attribution totals for one window."""
        if measurement.solar_to_house_kw is None:
            self._attribution_skipped_window_counts["solar_used_in_house_value"] += 1
        elif rates.import_unit_price_cents_per_kwh is not None:
            solar_to_house_kwh = max(measurement.solar_to_house_kw, 0.0) * hours
            self.economics_totals["solar_used_in_house_value"] += (
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
            self._attribution_skipped_window_counts["solar_export_net_value"] += 1
        elif rates.export_unit_price_cents_per_kwh is not None:
            solar_to_grid_kwh = max(measurement.solar_to_grid_kw, 0.0) * hours
            self.economics_totals["solar_export_net_value"] += (
                cents_per_kwh_to_eur(
                    rates.export_unit_price_cents_per_kwh
                    - rates.export_transfer_fee_cents_per_kwh,
                    solar_to_grid_kwh,
                )
            )

        if measurement.battery_to_house_kw is None:
            self._attribution_skipped_window_counts[
                "battery_house_supply_value"
            ] += 1
        elif rates.import_unit_price_cents_per_kwh is not None:
            battery_to_house_kwh = max(measurement.battery_to_house_kw, 0.0) * hours
            self.economics_totals["battery_house_supply_value"] += (
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
            or self.tariff_config.power_fee_rate_eur_per_kw_month <= 0
            or self.tariff_config.power_fee_rule == "none"
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
        peak_kw, new_estimate = self.tariff_config.calculate_monthly_power_fee(
            hourly_average_demands_kw=hourly_average_demands
        )
        previous_estimate = monthly_estimates.get(month_key, 0.0)
        monthly_estimates[month_key] = new_estimate
        if monthly_peaks is not None:
            monthly_peaks[month_key] = peak_kw
        return max(new_estimate - previous_estimate, 0.0)

    def _current_measurement_month_key(self) -> str | None:
        """Return month key for the latest measurement."""
        if self.data is None:
            return None
        timestamp = _measurement_timestamp(self.data)
        if timestamp is None:
            return None
        return timestamp.strftime("%Y-%m")

    async def _async_save_energy_state(self) -> None:
        """Persist cumulative energy counters."""
        await self._energy_store.async_save(
            {
                "totals": self.energy_totals,
                "last_period_end": self.energy_last_period_end,
                "processed_period_ends": list(self._processed_energy_period_ends),
            }
        )

    async def _async_save_economics_state(self) -> None:
        """Persist cumulative economics counters."""
        await self._economics_store.async_save(
            {
                "totals": self.economics_totals,
                "last_period_end": self.economics_last_period_end,
                "processed_period_ends": list(
                    self._processed_economics_period_ends
                ),
                "skipped_savings_window_count": self.skipped_savings_window_count,
                "tariff_signature": self._tariff_signature,
                "power_fee_hour_buckets": self._power_fee_hour_buckets,
                "power_fee_monthly_estimates": self._power_fee_monthly_estimates,
                "power_fee_monthly_peaks": self._power_fee_monthly_peaks,
                "baseline_power_fee_hour_buckets": (
                    self._baseline_power_fee_hour_buckets
                ),
                "baseline_power_fee_monthly_estimates": (
                    self._baseline_power_fee_monthly_estimates
                ),
                "attribution_skipped_window_counts": (
                    self._attribution_skipped_window_counts
                ),
            }
        )

    async def _async_save_analytics_state(self) -> None:
        """Persist long-term derived analytics state."""
        await self._analytics_store.async_save(self.analytics_state.as_store_data())

    def _maybe_update_live_measurement(self, measurement: MeasurementData) -> None:
        """Keep coordinator.data pointed at the newest processed window."""
        current = self.data
        if current is None:
            self.data = measurement
            return

        current_end = _parse_iso8601(current.period_end)
        candidate_end = _parse_iso8601(measurement.period_end)
        if current_end is not None and candidate_end is not None:
            if candidate_end >= current_end:
                self.data = measurement
            return

        if measurement.period_end >= current.period_end:
            self.data = measurement


def _cost_or_zero(
    unit_price_cents_per_kwh: float | None, energy_kwh: float
) -> float:
    """Return EUR cost for a window, defaulting to zero if price is unavailable."""
    if unit_price_cents_per_kwh is None:
        return 0.0
    return cents_per_kwh_to_eur(unit_price_cents_per_kwh, energy_kwh)


def _load_float_map(raw: Any) -> dict[str, float]:
    """Load a flat string->float map from persisted data."""
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): float(value)
        for key, value in raw.items()
        if isinstance(value, int | float)
    }


def _load_int_map(
    raw: Any,
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


def _load_hour_bucket_store(raw: Any) -> dict[str, dict[str, dict[str, float]]]:
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


def _measurement_timestamp(measurement: MeasurementData) -> datetime | None:
    """Return measurement period start timestamp."""
    return _parse_iso8601(measurement.period_start)


def _parse_iso8601(value: str) -> datetime | None:
    """Parse ISO 8601 timestamp and return None on malformed input."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _measurement_duration_hours(period_start: str, period_end: str) -> float:
    """Return measurement window duration in hours, fallback to default window."""
    start = _parse_iso8601(period_start)
    end = _parse_iso8601(period_end)

    if start is None or end is None:
        return DEFAULT_WINDOW_HOURS

    delta_hours = (end - start).total_seconds() / 3600
    if delta_hours <= 0:
        return DEFAULT_WINDOW_HOURS

    return delta_hours
