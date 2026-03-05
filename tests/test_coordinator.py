"""Tests for the Elisa Kotiakku DataUpdateCoordinator."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    ElisaKotiakkuRateLimitError,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.elisa_kotiakku.const import DEFAULT_WINDOW_HOURS
from custom_components.elisa_kotiakku.coordinator import (
    ElisaKotiakkuCoordinator,
    _measurement_duration_hours,
    _parse_iso8601,
)

from .conftest import SAMPLE_MEASUREMENT


@pytest.fixture(autouse=True)
def _patch_frame_helper():
    """Patch HA frame helper so DataUpdateCoordinator can be instantiated."""
    with patch("homeassistant.helpers.frame.report_usage"):
        yield


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a minimal mock HomeAssistant instance."""
    hass = MagicMock()
    hass.loop = None
    hass.config.path = MagicMock(return_value="/tmp")
    return hass


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Return a mock API client."""
    client = AsyncMock()
    client.async_get_latest.return_value = SAMPLE_MEASUREMENT
    client.async_get_range.return_value = [SAMPLE_MEASUREMENT]
    return client


def _make_coordinator(
    mock_hass: MagicMock,
    mock_api_client: AsyncMock,
    mock_config_entry: MagicMock,
) -> ElisaKotiakkuCoordinator:
    coordinator = ElisaKotiakkuCoordinator(
        mock_hass,
        mock_api_client,
        mock_config_entry,
    )
    coordinator._async_save_energy_state = AsyncMock()
    return coordinator


class TestCoordinatorUpdate:
    """Tests for _async_update_data."""

    async def test_successful_update_returns_measurement(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        result = await coordinator._async_update_data()

        assert result is SAMPLE_MEASUREMENT
        mock_api_client.async_get_latest.assert_awaited_once()

    async def test_successful_update_accumulates_energy_totals(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        await coordinator._async_update_data()

        assert coordinator.get_energy_total("grid_import_energy") == pytest.approx(
            0.367792, rel=0, abs=1e-6
        )
        assert coordinator.get_energy_total("grid_export_energy") == 0.0
        assert coordinator.get_energy_total(
            "house_consumption_energy"
        ) == pytest.approx(
            0.131917,
            rel=0,
            abs=1e-6,
        )
        assert coordinator.get_energy_total("battery_charge_energy") == pytest.approx(
            0.22725, rel=0, abs=1e-6
        )

    async def test_returns_none_when_api_returns_none(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_latest.return_value = None
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        result = await coordinator._async_update_data()
        assert result is None
        assert coordinator.get_energy_total("grid_import_energy") == 0.0

    async def test_auth_error_raises_config_entry_auth_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.exceptions import ConfigEntryAuthFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuAuthError(
            "Auth failed"
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coordinator._async_update_data()

    async def test_api_error_raises_update_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuApiError(
            "Connection lost"
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Error fetching data"):
            await coordinator._async_update_data()

    async def test_rate_limit_raises_update_failed_with_backoff(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuRateLimitError(
            retry_after=900
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coordinator._async_update_data()

        assert coordinator.update_interval == timedelta(seconds=900)

    async def test_rate_limit_without_retry_after_uses_default_interval(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuRateLimitError()
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coordinator._async_update_data()

        assert coordinator.update_interval == timedelta(minutes=5)

    async def test_success_resets_backoff_to_default(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_latest.side_effect = [
            ElisaKotiakkuRateLimitError(retry_after=900),
            SAMPLE_MEASUREMENT,
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coordinator._async_update_data()

        await coordinator._async_update_data()
        assert coordinator.update_interval == timedelta(minutes=5)


class TestBackfill:
    """Tests for coordinator historical backfill."""

    async def test_backfill_fetches_range_and_processes_measurements(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.async_update_listeners = MagicMock()

        processed = await coordinator.async_backfill_energy(
            start_time="2025-12-17T00:00:00+02:00",
            end_time="2025-12-17T01:00:00+02:00",
        )

        assert processed == 1
        coordinator.async_update_listeners.assert_called_once()
        mock_api_client.async_get_range.assert_awaited_once()

    async def test_backfill_processes_older_windows_after_latest_update(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Backfill should still import older periods after latest polling."""
        older = replace(
            SAMPLE_MEASUREMENT,
            period_start="2025-12-16T23:55:00+02:00",
            period_end="2025-12-17T00:00:00+02:00",
        )
        mock_api_client.async_get_range.return_value = [older]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        # First poll latest
        await coordinator._async_update_data()
        before = coordinator.get_energy_total("grid_import_energy")

        # Then backfill older
        processed = await coordinator.async_backfill_energy("a", "b")
        after = coordinator.get_energy_total("grid_import_energy")

        assert processed == 1
        assert after is not None and before is not None
        assert after > before

    async def test_backfill_wraps_api_error_as_update_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_api_client.async_get_range.side_effect = ElisaKotiakkuApiError("boom")
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="historical data"):
            await coordinator.async_backfill_energy("a", "b")


class TestEnergyState:
    """Tests for energy state persistence helpers."""

    async def test_process_measurements_skips_duplicate_period(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        processed_first = await coordinator.async_process_measurements(
            [SAMPLE_MEASUREMENT], notify=False
        )
        processed_second = await coordinator.async_process_measurements(
            [SAMPLE_MEASUREMENT], notify=False
        )

        assert processed_first == 1
        assert processed_second == 0

    async def test_load_energy_state_restores_totals(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._energy_store = MagicMock()
        coordinator._energy_store.async_load = AsyncMock(
            return_value={
                "totals": {"grid_import_energy": 12.5},
                "last_period_end": "2025-12-17T01:00:00+02:00",
                "processed_period_ends": ["2025-12-17T01:00:00+02:00"],
            }
        )

        await coordinator.async_load_energy_state()

        assert coordinator.get_energy_total("grid_import_energy") == 12.5
        assert coordinator.energy_last_period_end == "2025-12-17T01:00:00+02:00"
        assert coordinator.energy_processed_period_count == 1

    async def test_load_energy_state_skips_when_store_returns_none(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """async_load_energy_state should be a no-op when stored data is None."""
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._energy_store = MagicMock()
        coordinator._energy_store.async_load = AsyncMock(return_value=None)

        await coordinator.async_load_energy_state()

        assert coordinator.get_energy_total("grid_import_energy") == 0.0
        assert coordinator.energy_last_period_end is None


class TestBackfillEdgeCases:
    """Edge-case tests for async_backfill_energy."""

    async def test_backfill_auth_error_raises_config_entry_auth_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """ElisaKotiakkuAuthError during backfill must raise ConfigEntryAuthFailed."""
        mock_api_client.async_get_range.side_effect = ElisaKotiakkuAuthError(
            "Token revoked"
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coordinator.async_backfill_energy("a", "b")


class TestEnergyHelpers:
    """Unit tests for coordinator helper methods and module-level functions."""

    def test_get_energy_total_returns_none_for_unknown_key(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """get_energy_total must return None for keys not in energy_totals dict."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.get_energy_total("nonexistent_key") is None

    def test_update_last_period_end_ignores_older_period(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """_update_last_period_end must not regress when given an older timestamp."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.energy_last_period_end = "2025-12-17T01:00:00+02:00"

        coordinator._update_last_period_end("2025-12-17T00:00:00+02:00")

        assert coordinator.energy_last_period_end == "2025-12-17T01:00:00+02:00"

    def test_update_last_period_end_falls_back_to_string_compare_for_garbled_dates(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """When both dates are unparseable, string comparison is used as fallback."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.energy_last_period_end = "aaaa"

        coordinator._update_last_period_end("zzzz")
        assert coordinator.energy_last_period_end == "zzzz"

        coordinator._update_last_period_end("aaaa")
        assert coordinator.energy_last_period_end == "zzzz"

    def test_parse_iso8601_returns_none_for_invalid_string(self) -> None:
        """_parse_iso8601 must return None instead of raising on junk input."""
        assert _parse_iso8601("not-a-date") is None


class TestMeasurementDurationHours:
    """Unit tests for the _measurement_duration_hours module function."""

    def test_valid_window_returns_correct_hours(self) -> None:
        assert _measurement_duration_hours(
            "2025-12-17T00:00:00+02:00", "2025-12-17T00:05:00+02:00"
        ) == pytest.approx(1 / 12)

    def test_invalid_period_start_returns_default(self) -> None:
        result = _measurement_duration_hours(
            "bad-date", "2025-12-17T00:05:00+02:00"
        )
        assert result == DEFAULT_WINDOW_HOURS

    def test_invalid_period_end_returns_default(self) -> None:
        result = _measurement_duration_hours(
            "2025-12-17T00:00:00+02:00", "bad-date"
        )
        assert result == DEFAULT_WINDOW_HOURS

    def test_inverted_timestamps_return_default(self) -> None:
        """When end <= start (time runs backwards), fall back to default window."""
        result = _measurement_duration_hours(
            "2025-12-17T00:05:00+02:00", "2025-12-17T00:00:00+02:00"
        )
        assert result == DEFAULT_WINDOW_HOURS
