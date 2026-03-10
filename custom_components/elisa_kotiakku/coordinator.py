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
    CONF_AKKURESERVIHYVITYS,
    CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    CONF_BATTERY_MONTHLY_COST,
    CONF_BATTERY_TOTAL_COST,
    DEFAULT_AKKURESERVIHYVITYS,
    DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    DEFAULT_BATTERY_MONTHLY_COST,
    DEFAULT_BATTERY_TOTAL_COST,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .economics_engine import EconomicsEngine
from .energy_store import EnergyStore
from .payback import (
    effective_monthly_cost,
    monthly_first_day_of_profit,
    payback_remaining_months,
)
from .tariff import ActiveTariffRates, TariffConfig
from .util import parse_iso8601 as _parse_iso8601

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
        self.battery_monthly_cost = float(
            config_entry.options.get(
                CONF_BATTERY_MONTHLY_COST,
                DEFAULT_BATTERY_MONTHLY_COST,
            )
        )
        self.battery_total_cost = float(
            config_entry.options.get(
                CONF_BATTERY_TOTAL_COST,
                DEFAULT_BATTERY_TOTAL_COST,
            )
        )
        self.akkureservihyvitys = float(
            config_entry.options.get(
                CONF_AKKURESERVIHYVITYS,
                DEFAULT_AKKURESERVIHYVITYS,
            )
        )

        self._energy_state = EnergyStore()
        self._energy_store: Store[dict[str, Any]] = Store(
            hass,
            _ENERGY_STORE_VERSION,
            f"{DOMAIN}_{config_entry.entry_id}_energy",
        )

        self._economics_state = EconomicsEngine()
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
        self._energy_state.restore(stored)

    async def async_load_economics_state(self) -> None:
        """Restore persisted economics values when tariff options still match."""
        stored = await self._economics_store.async_load()
        if (
            isinstance(stored, dict)
            and stored.get("tariff_signature") != self._tariff_signature
        ):
            _LOGGER.debug("Ignoring stale economics state due to tariff change")
        self._economics_state.restore(
            stored,
            expected_tariff_signature=self._tariff_signature,
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
            if not self._economics_state.process_measurement(
                measurement,
                tariff_config=self.tariff_config,
            ):
                continue
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

            if self._energy_state.process_measurement(measurement):
                energy_changed = True
                measurement_processed = True

            if self._economics_state.process_measurement(
                measurement,
                tariff_config=self.tariff_config,
            ):
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
        return self._energy_state.get_total(key)

    def get_economics_total(self, key: str) -> float | None:
        """Return current cumulative economics total for the given key."""
        return self._economics_state.get_total(key)

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
        """Return current month's peak grid import power in kW."""
        month_key = self._current_measurement_month_key()
        if month_key is None:
            return None
        peak = self._economics_state.grid_import_monthly_peaks.get(
            month_key, 0.0
        )
        return round(peak, 6)

    def get_current_month_power_fee_estimate(self) -> float | None:
        """Return current month's power fee estimate in EUR."""
        month_key = self._current_measurement_month_key()
        if month_key is None:
            return None
        estimate = self._economics_state.power_fee_monthly_estimates.get(
            month_key, 0.0
        )
        return round(estimate, 6)

    def get_monthly_first_day_of_profit(self) -> int | None:
        """Return estimated first profitable day of the current month.

        The monthly battery cost is compared against cumulative battery savings
        for the current month.  If no monthly cost is configured but a total
        cost is set, the monthly cost is derived as total_cost / 12 / number
        of payback years (simplified to total_cost / 120 for a 10-year
        horizon — matching a typical osamaksu agreement).

        Returns the day-of-month (1-31) when savings exceed the monthly cost,
        or ``None`` when there is no cost configured, no data yet, or savings
        have not yet exceeded the cost this month.
        """
        monthly_cost = self._effective_monthly_cost()
        month_key = self._current_measurement_month_key()
        if month_key is None:
            return None

        month_savings = self._economics_state.monthly_battery_savings.get(
            month_key, 0.0
        )
        if self.data is None:
            return None
        timestamp = _measurement_timestamp(self.data)
        if timestamp is None:
            return None
        return monthly_first_day_of_profit(
            monthly_cost=monthly_cost,
            month_savings=month_savings,
            timestamp=timestamp,
        )

    def get_payback_remaining_months(self) -> float | None:
        """Return estimated months until battery cost is fully paid off.

        Uses lifetime cumulative battery_savings to project how quickly the
        total battery cost will be recovered.  Returns ``None`` when total
        cost is not configured or no savings have accrued yet.
        """
        total_savings = self._economics_state.totals.get("battery_savings", 0.0)
        tracked_months = len(self._economics_state.monthly_battery_savings)
        return payback_remaining_months(
            battery_total_cost=self.battery_total_cost,
            total_battery_savings=total_savings,
            tracked_months=tracked_months,
            akkureservihyvitys=self.akkureservihyvitys,
        )

    def _effective_monthly_cost(self) -> float | None:
        """Return configured monthly cost, deriving from total if needed.

        When ``battery_monthly_cost`` is set directly it is returned as-is
        (user is expected to have already accounted for service fees and
        akkureservi compensation).

        When deriving from ``battery_total_cost`` (÷ 120 months), the
        akkureservihyvitys is subtracted to reflect the net monthly cost.
        """
        return effective_monthly_cost(
            battery_monthly_cost=self.battery_monthly_cost,
            battery_total_cost=self.battery_total_cost,
            akkureservihyvitys=self.akkureservihyvitys,
        )

    def get_economics_debug_value(self, key: str) -> float | int | None:
        """Return a coordinator debug value exposed as a sensor."""
        return self._economics_state.get_debug_value(key)

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
        return self._economics_state.get_attribution_skipped_window_count(key)

    def get_attribution_skipped_window_counts(self) -> dict[str, int]:
        """Return all attribution skip counters."""
        return self._economics_state.get_attribution_skipped_window_counts()

    def get_power_fee_monthly_estimates(self) -> dict[str, float]:
        """Return current monthly power-fee estimates."""
        return self._economics_state.get_power_fee_monthly_estimates()

    def get_power_fee_monthly_peaks(self) -> dict[str, float]:
        """Return current monthly qualifying peaks."""
        return self._economics_state.get_power_fee_monthly_peaks()

    def get_energy_totals(self) -> dict[str, float]:
        """Return cumulative energy totals snapshot."""
        return dict(self._energy_state.totals)

    def get_economics_totals(self) -> dict[str, float]:
        """Return cumulative economics totals snapshot."""
        return dict(self._economics_state.totals)

    def get_energy_last_period_end(self) -> str | None:
        """Return latest processed energy period end marker."""
        return self._energy_state.last_period_end

    def get_economics_last_period_end(self) -> str | None:
        """Return latest processed economics period end marker."""
        return self._economics_state.last_period_end

    def get_skipped_savings_window_count(self) -> int:
        """Return number of windows skipped for savings calculation."""
        return self._economics_state.skipped_savings_window_count

    def get_monthly_battery_savings(self) -> dict[str, float]:
        """Return monthly battery savings map used for payback context."""
        return dict(self._economics_state.monthly_battery_savings)

    @property
    def energy_processed_period_count(self) -> int:
        """Return number of period_end markers already processed for energy."""
        return self._energy_state.processed_period_count

    @property
    def economics_processed_period_count(self) -> int:
        """Return number of period_end markers already processed for economics."""
        return self._economics_state.processed_period_count

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
        self._economics_state.reset_runtime()

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
        await self._energy_store.async_save(self._energy_state.as_store_payload())

    async def _async_save_economics_state(self) -> None:
        """Persist cumulative economics counters."""
        await self._economics_store.async_save(
            self._economics_state.as_store_payload(
                tariff_signature=self._tariff_signature,
            )
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

def _measurement_timestamp(measurement: MeasurementData) -> datetime | None:
    """Return measurement period start timestamp."""
    return _parse_iso8601(measurement.period_start)
