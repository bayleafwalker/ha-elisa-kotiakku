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

from .api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    ElisaKotiakkuRateLimitError,
    MeasurementData,
)
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WINDOW_HOURS,
    DOMAIN,
    ENERGY_TOTAL_KEYS,
)

_LOGGER = logging.getLogger(__name__)

_ENERGY_STORE_VERSION = 1


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
        self.energy_totals: dict[str, float] = {
            key: 0.0 for key in ENERGY_TOTAL_KEYS
        }
        self.energy_last_period_end: str | None = None
        self._energy_store: Store[dict[str, Any]] = Store(
            hass,
            _ENERGY_STORE_VERSION,
            f"{DOMAIN}_{config_entry.entry_id}_energy",
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

    async def _async_update_data(self) -> MeasurementData | None:
        """Fetch the latest measurement from the API."""
        try:
            data = await self.client.async_get_latest()
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuRateLimitError as err:
            # Respect server backoff hints, but never poll faster than default.
            default_seconds = int(self._default_update_interval.total_seconds())
            backoff_seconds = max(err.retry_after or default_seconds, default_seconds)
            self.update_interval = timedelta(seconds=backoff_seconds)
            raise UpdateFailed(
                f"Rate limited by API, retrying in {backoff_seconds} seconds"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        # Restore default interval after a successful request.
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
        """Fetch a historical range and fold it into cumulative energy counters."""
        try:
            measurements = await self.client.async_get_range(start_time, end_time)
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching historical data: {err}") from err

        return await self.async_process_measurements(measurements, notify=True)

    async def async_process_measurements(
        self,
        measurements: list[MeasurementData],
        *,
        notify: bool,
    ) -> int:
        """Process one or more windows into cumulative energy counters."""
        processed = 0
        for measurement in sorted(measurements, key=lambda item: item.period_end):
            if not self._is_new_period(measurement.period_end):
                continue

            for key, delta in self._measurement_energy_deltas(measurement).items():
                self.energy_totals[key] += delta

            self.energy_last_period_end = measurement.period_end
            processed += 1

        if processed:
            await self._async_save_energy_state()
            if notify:
                self.async_update_listeners()

        return processed

    def get_energy_total(self, key: str) -> float | None:
        """Return current cumulative energy total for the given key."""
        value = self.energy_totals.get(key)
        if value is None:
            return None
        return round(value, 6)

    def _is_new_period(self, period_end: str) -> bool:
        """Return True if this period has not yet been included in totals."""
        if self.energy_last_period_end is None:
            return True

        current = _parse_iso8601(period_end)
        previous = _parse_iso8601(self.energy_last_period_end)

        if current is not None and previous is not None:
            return current > previous

        return period_end != self.energy_last_period_end

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

    async def _async_save_energy_state(self) -> None:
        """Persist cumulative energy counters."""
        await self._energy_store.async_save(
            {
                "totals": self.energy_totals,
                "last_period_end": self.energy_last_period_end,
            }
        )


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
