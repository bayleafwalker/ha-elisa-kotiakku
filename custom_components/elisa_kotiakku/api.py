"""API client for Elisa Kotiakku (Gridle) public API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import API_MEASUREMENTS_URL

_LOGGER = logging.getLogger(__name__)

# Timeout for API requests (seconds)
REQUEST_TIMEOUT = 30


class ElisaKotiakkuApiError(Exception):
    """Base exception for API errors."""


class ElisaKotiakkuAuthError(ElisaKotiakkuApiError):
    """Authentication error (401/403)."""


class ElisaKotiakkuRateLimitError(ElisaKotiakkuApiError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        """Initialise with optional Retry-After hint from response headers."""
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class MeasurementData:
    """Represents a single 5-minute measurement data point."""

    period_start: str
    period_end: str
    battery_power_kw: float | None = None
    state_of_charge_percent: float | None = None
    solar_power_kw: float | None = None
    grid_power_kw: float | None = None
    house_power_kw: float | None = None
    solar_to_house_kw: float | None = None
    solar_to_battery_kw: float | None = None
    solar_to_grid_kw: float | None = None
    grid_to_house_kw: float | None = None
    grid_to_battery_kw: float | None = None
    battery_to_house_kw: float | None = None
    battery_to_grid_kw: float | None = None
    spot_price_cents_per_kwh: float | None = None
    battery_temperature_celsius: float | None = None


class ElisaKotiakkuApiClient:
    """Client for the Elisa Kotiakku public API.

    Endpoint: GET /api/public/measurements
    Authentication: x-api-key header.

    Data behaviour:
    - Without time range: returns the previous complete 5-minute window.
    - With start_time only: returns 5-min averaged data from start_time to now.
    - With start_time and end_time: 5-min averaged data (max 31 days).
    """

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialise the API client.

        Args:
            api_key: The x-api-key for authentication.
            session: Optional aiohttp session. If not provided, the caller
                     must supply one via set_session() before making requests.
        """
        self._api_key = api_key
        self._session = session

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """Set or replace the aiohttp session."""
        self._session = session

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def async_get_latest(self) -> MeasurementData | None:
        """Return the latest complete 5-minute measurement window.

        Calls the API *without* time-range parameters so the backend
        returns only the most recent complete window.
        """
        data = await self._async_request()
        if not data:
            return None
        # API returns an array; the last element is the most recent.
        return self._parse_measurement(data[-1])

    async def async_get_range(
        self,
        start_time: str,
        end_time: str | None = None,
    ) -> list[MeasurementData]:
        """Return measurement data for a time range.

        Args:
            start_time: ISO 8601 datetime string.
            end_time: Optional ISO 8601 datetime string (max 31 days span).
        """
        params: dict[str, str] = {"start_time": start_time}
        if end_time:
            params["end_time"] = end_time
        data = await self._async_request(params=params)
        return [self._parse_measurement(item) for item in data]

    async def async_validate_key(self) -> bool:
        """Validate the API key by performing a lightweight request.

        Returns True if the key is valid, raises on auth failure.
        """
        await self._async_request()
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _async_request(
        self,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a GET request against the measurements endpoint."""
        if self._session is None:
            raise ElisaKotiakkuApiError("No aiohttp session configured")

        headers = {"x-api-key": self._api_key}

        try:
            async with self._session.get(
                API_MEASUREMENTS_URL,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status in (401, 403):
                    raise ElisaKotiakkuAuthError(
                        f"Authentication failed (HTTP {resp.status})"
                    )
                if resp.status == 429:
                    raise ElisaKotiakkuRateLimitError(
                        retry_after=self._parse_retry_after(
                            resp.headers.get("Retry-After")
                        )
                    )
                if resp.status == 422:
                    body = await resp.text()
                    raise ElisaKotiakkuApiError(
                        f"Validation error (422): {body}"
                    )
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise ElisaKotiakkuApiError(
                f"Communication error: {err}"
            ) from err

    @staticmethod
    def _parse_retry_after(value: str | None) -> int | None:
        """Parse Retry-After header (seconds form only)."""
        if value is None:
            return None
        value = value.strip()
        if value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _parse_measurement(raw: dict[str, Any]) -> MeasurementData:
        """Parse a raw JSON dict into a MeasurementData dataclass."""
        return MeasurementData(
            period_start=raw["period_start"],
            period_end=raw["period_end"],
            battery_power_kw=raw.get("battery_power_kw"),
            state_of_charge_percent=raw.get("state_of_charge_percent"),
            solar_power_kw=raw.get("solar_power_kw"),
            grid_power_kw=raw.get("grid_power_kw"),
            house_power_kw=raw.get("house_power_kw"),
            solar_to_house_kw=raw.get("solar_to_house_kw"),
            solar_to_battery_kw=raw.get("solar_to_battery_kw"),
            solar_to_grid_kw=raw.get("solar_to_grid_kw"),
            grid_to_house_kw=raw.get("grid_to_house_kw"),
            grid_to_battery_kw=raw.get("grid_to_battery_kw"),
            battery_to_house_kw=raw.get("battery_to_house_kw"),
            battery_to_grid_kw=raw.get("battery_to_grid_kw"),
            spot_price_cents_per_kwh=raw.get("spot_price_cents_per_kwh"),
            battery_temperature_celsius=raw.get("battery_temperature_celsius"),
        )
