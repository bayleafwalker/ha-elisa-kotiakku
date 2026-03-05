"""Tests for the Elisa Kotiakku DataUpdateCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    MeasurementData,
)
from custom_components.elisa_kotiakku.coordinator import ElisaKotiakkuCoordinator

from .conftest import SAMPLE_MEASUREMENT


@pytest.fixture(autouse=True)
def _patch_frame_helper():
    """Patch HA frame helper so DataUpdateCoordinator can be instantiated."""
    with patch(
        "homeassistant.helpers.frame.report_usage",
    ):
        yield


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock()
    hass.loop = None  # DataUpdateCoordinator checks this
    return hass


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Return a mock API client."""
    client = AsyncMock()
    client.async_get_latest.return_value = SAMPLE_MEASUREMENT
    return client


class TestCoordinatorUpdate:
    """Tests for _async_update_data."""

    async def test_successful_update(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """Successful API call returns MeasurementData."""
        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)
        result = await coordinator._async_update_data()

        assert result is not None
        assert isinstance(result, MeasurementData)
        assert result.battery_power_kw == -2.727
        mock_api_client.async_get_latest.assert_awaited_once()

    async def test_returns_none_when_api_returns_none(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """None from API is propagated as coordinator data."""
        mock_api_client.async_get_latest.return_value = None
        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)
        result = await coordinator._async_update_data()

        assert result is None

    async def test_auth_error_raises_config_entry_auth_failed(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """ElisaKotiakkuAuthError is wrapped in ConfigEntryAuthFailed."""
        from homeassistant.exceptions import ConfigEntryAuthFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuAuthError(
            "Auth failed"
        )
        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coordinator._async_update_data()

    async def test_api_error_raises_update_failed(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """ElisaKotiakkuApiError is wrapped in UpdateFailed."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuApiError(
            "Connection lost"
        )
        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)

        with pytest.raises(UpdateFailed, match="Error fetching data"):
            await coordinator._async_update_data()


class TestCoordinatorInit:
    """Tests for coordinator initialisation."""

    async def test_stores_client(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """Client reference is stored on the coordinator."""
        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)
        assert coordinator.client is mock_api_client

    async def test_name_is_domain(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """Coordinator name matches the integration domain."""
        from custom_components.elisa_kotiakku.const import DOMAIN

        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)
        assert coordinator.name == DOMAIN

    async def test_update_interval(
        self, mock_hass: MagicMock, mock_api_client: AsyncMock
    ) -> None:
        """Update interval is 5 minutes."""
        from datetime import timedelta

        coordinator = ElisaKotiakkuCoordinator(mock_hass, mock_api_client)
        assert coordinator.update_interval == timedelta(minutes=5)
