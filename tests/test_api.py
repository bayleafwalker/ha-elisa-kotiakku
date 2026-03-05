"""Tests for the Elisa Kotiakku API client."""

from __future__ import annotations

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    ElisaKotiakkuRateLimitError,
    MeasurementData,
)
from custom_components.elisa_kotiakku.const import API_MEASUREMENTS_URL

from .conftest import SAMPLE_API_RESPONSE, SAMPLE_API_RESPONSE_ITEM


def _test_client_session() -> aiohttp.ClientSession:
    """Create an aiohttp test session without the pycares async resolver."""
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    return aiohttp.ClientSession(connector=connector)

# ---------------------------------------------------------------------------
# async_get_latest
# ---------------------------------------------------------------------------


class TestAsyncGetLatest:
    """Tests for ElisaKotiakkuApiClient.async_get_latest."""

    async def test_returns_measurement_on_success(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Valid response returns a populated MeasurementData."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL, payload=SAMPLE_API_RESPONSE
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_get_latest()

        assert result is not None
        assert isinstance(result, MeasurementData)
        assert result.battery_power_kw == -2.727
        assert result.state_of_charge_percent == 21.25
        assert result.solar_power_kw == 0.0
        assert result.grid_power_kw == 4.4135
        assert result.spot_price_cents_per_kwh == 1.87
        assert result.battery_temperature_celsius == 24.5
        assert result.period_start == "2025-12-17T00:00:00+02:00"
        assert result.period_end == "2025-12-17T00:05:00+02:00"

    async def test_returns_last_item_when_multiple(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """When API returns multiple items, the last one is used."""
        older = {**SAMPLE_API_RESPONSE_ITEM, "battery_power_kw": -1.0}
        newer = {**SAMPLE_API_RESPONSE_ITEM, "battery_power_kw": -3.0}
        mock_aioresponses.get(
            API_MEASUREMENTS_URL, payload=[older, newer]
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_get_latest()

        assert result is not None
        assert result.battery_power_kw == -3.0

    async def test_returns_none_on_empty_response(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Empty array from API returns None."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, payload=[])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_get_latest()

        assert result is None

    async def test_handles_null_optional_fields(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Fields may be null in the API response."""
        minimal = {
            "period_start": "2025-12-17T00:00:00+02:00",
            "period_end": "2025-12-17T00:05:00+02:00",
        }
        mock_aioresponses.get(API_MEASUREMENTS_URL, payload=[minimal])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_get_latest()

        assert result is not None
        assert result.battery_power_kw is None
        assert result.state_of_charge_percent is None
        assert result.solar_power_kw is None
        assert result.spot_price_cents_per_kwh is None


# ---------------------------------------------------------------------------
# HTTP error handling
# ---------------------------------------------------------------------------


class TestHttpErrors:
    """Tests for HTTP error code handling."""

    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_auth_error(
        self,
        mock_aioresponses: aioresponses,
        api_key: str,
        status_code: int,
    ) -> None:
        """401 and 403 raise ElisaKotiakkuAuthError."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL, status=status_code
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuAuthError):
                await client.async_get_latest()

    async def test_rate_limit_error(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """429 raises ElisaKotiakkuRateLimitError."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, status=429)

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuRateLimitError):
                await client.async_get_latest()

    async def test_rate_limit_error_carries_retry_after_seconds(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """429 should parse Retry-After header when it is an integer value."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL,
            status=429,
            headers={"Retry-After": "120"},
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuRateLimitError) as err:
                await client.async_get_latest()

        assert err.value.retry_after == 120

    async def test_rate_limit_error_ignores_non_numeric_retry_after(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Non-numeric Retry-After header should be ignored safely."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL,
            status=429,
            headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"},
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuRateLimitError) as err:
                await client.async_get_latest()

        assert err.value.retry_after is None

    async def test_validation_error(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """422 raises ElisaKotiakkuApiError with body text."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL, status=422, body="bad params"
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuApiError, match="422"):
                await client.async_get_latest()

    async def test_server_error(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """500 raises ElisaKotiakkuApiError (via raise_for_status)."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, status=500)

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuApiError):
                await client.async_get_latest()

    async def test_connection_error(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Network-level errors raise ElisaKotiakkuApiError."""
        mock_aioresponses.get(
            API_MEASUREMENTS_URL,
            exception=aiohttp.ClientConnectionError("Connection refused"),
        )

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuApiError, match="Communication"):
                await client.async_get_latest()

    async def test_no_session_raises(self, api_key: str) -> None:
        """Calling without a session raises ElisaKotiakkuApiError."""
        client = ElisaKotiakkuApiClient(api_key=api_key)
        with pytest.raises(ElisaKotiakkuApiError, match="No aiohttp session"):
            await client.async_get_latest()


# ---------------------------------------------------------------------------
# async_get_range
# ---------------------------------------------------------------------------


class TestAsyncGetRange:
    """Tests for ElisaKotiakkuApiClient.async_get_range."""

    async def test_returns_list_of_measurements(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Range query returns a list of MeasurementData."""
        item1 = {**SAMPLE_API_RESPONSE_ITEM, "battery_power_kw": -1.0}
        item2 = {**SAMPLE_API_RESPONSE_ITEM, "battery_power_kw": -2.0}
        pattern = re.compile(r"^https://residential\.gridle\.com/api/public/measurements")
        mock_aioresponses.get(pattern, payload=[item1, item2])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_get_range(
                start_time="2025-12-17T00:00:00+02:00",
                end_time="2025-12-17T00:10:00+02:00",
            )

        assert len(result) == 2
        assert result[0].battery_power_kw == -1.0
        assert result[1].battery_power_kw == -2.0

    async def test_passes_query_params(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Verifies start_time and end_time are sent as query parameters."""
        pattern = re.compile(r"^https://residential\.gridle\.com/api/public/measurements")
        mock_aioresponses.get(pattern, payload=[])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            await client.async_get_range(
                start_time="2025-12-17T00:00:00+02:00"
            )

        # aioresponses records the request
        made_requests = []
        for req_key, req_list in mock_aioresponses.requests.items():
            made_requests.extend(req_list)
        assert len(made_requests) == 1


# ---------------------------------------------------------------------------
# async_validate_key
# ---------------------------------------------------------------------------


class TestAsyncValidateKey:
    """Tests for API key validation."""

    async def test_valid_key_returns_true(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Valid key returns True."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, payload=[])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            result = await client.async_validate_key()

        assert result is True

    async def test_invalid_key_raises(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Invalid key raises ElisaKotiakkuAuthError."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, status=401)

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            with pytest.raises(ElisaKotiakkuAuthError):
                await client.async_validate_key()


# ---------------------------------------------------------------------------
# set_session
# ---------------------------------------------------------------------------


class TestSetSession:
    """Tests for session management."""

    async def test_set_session_enables_requests(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """Client created without session works after set_session."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, payload=SAMPLE_API_RESPONSE)

        client = ElisaKotiakkuApiClient(api_key=api_key)
        async with _test_client_session() as session:
            client.set_session(session)
            result = await client.async_get_latest()

        assert result is not None


# ---------------------------------------------------------------------------
# Request headers
# ---------------------------------------------------------------------------


class TestRequestHeaders:
    """Tests that the API key is sent correctly."""

    async def test_api_key_sent_in_header(
        self, mock_aioresponses: aioresponses, api_key: str
    ) -> None:
        """x-api-key header is included in requests."""
        mock_aioresponses.get(API_MEASUREMENTS_URL, payload=[])

        async with _test_client_session() as session:
            client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
            await client.async_validate_key()

        # Check the recorded request headers
        made_requests = []
        for _, req_list in mock_aioresponses.requests.items():
            made_requests.extend(req_list)
        assert len(made_requests) == 1
        assert made_requests[0].kwargs["headers"]["x-api-key"] == api_key
