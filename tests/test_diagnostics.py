"""Tests for Elisa Kotiakku diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.elisa_kotiakku.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.fixture
def mock_entry_with_coordinator(
    mock_config_entry: MagicMock,
    mock_coordinator: MagicMock,
) -> MagicMock:
    """Return a config entry with coordinator attached as runtime_data."""
    mock_config_entry.runtime_data = mock_coordinator
    return mock_config_entry


class TestDiagnostics:
    """Tests for diagnostics output."""

    async def test_api_key_is_redacted(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """API key must be redacted in diagnostics output."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["config"]["api_key"] == "**REDACTED**"

    async def test_measurement_data_included(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Latest measurement is included as a dict."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        measurement = result["latest_measurement"]
        assert measurement is not None
        assert measurement["battery_power_kw"] == -2.727
        assert measurement["period_start"] == "2025-12-17T00:00:00+02:00"
        assert measurement["spot_price_cents_per_kwh"] == 1.87

    async def test_handles_none_measurement(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """None measurement is serialised as None."""
        mock_entry_with_coordinator.runtime_data.data = None
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["latest_measurement"] is None

    async def test_output_structure(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Output has expected top-level keys."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert "config" in result
        assert "options" in result
        assert "latest_measurement" in result
        assert "energy_totals" in result
        assert "energy_last_period_end" in result
        assert "energy_processed_period_count" in result
        assert "economics_totals" in result
        assert "economics_last_period_end" in result
        assert "economics_processed_period_count" in result
        assert "skipped_savings_window_count" in result
        assert "attribution_skipped_window_counts" in result
        assert "power_fee_monthly_estimates" in result
        assert "power_fee_monthly_peaks" in result
        assert "analytics_last_period_end" in result
        assert "analytics_processed_period_count" in result
        assert "analytics_candidate_count" in result
        assert "analytics_estimated_usable_capacity_kwh" in result
        assert "analytics_total_day_bucket_count" in result
        assert "analytics_rolling_bucket_count" in result
        assert "analytics_open_episode" in result
        assert len(result) == 20

    async def test_energy_data_included(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Energy totals and last period should be included."""
        mock_entry_with_coordinator.runtime_data.energy_totals = {
            "grid_import_energy": 1.23
        }
        mock_entry_with_coordinator.runtime_data.energy_last_period_end = (
            "2025-12-17T00:05:00+02:00"
        )

        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["energy_totals"]["grid_import_energy"] == 1.23
        assert result["energy_last_period_end"] == "2025-12-17T00:05:00+02:00"
        assert result["energy_processed_period_count"] == 0

    async def test_economics_data_included(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Economics totals and fee state should be included."""
        mock_entry_with_coordinator.options = {"tariff_mode": "flat"}
        mock_entry_with_coordinator.runtime_data.economics_totals = {
            "purchase_cost": 4.56
        }
        mock_entry_with_coordinator.runtime_data.economics_last_period_end = (
            "2025-12-17T00:05:00+02:00"
        )
        mock_entry_with_coordinator.runtime_data.economics_processed_period_count = 2
        mock_entry_with_coordinator.runtime_data.skipped_savings_window_count = 1
        (
            mock_entry_with_coordinator.runtime_data.get_attribution_skipped_window_counts.return_value
        ) = {
            "solar_used_in_house_value": 2,
            "solar_export_net_value": 0,
            "battery_house_supply_value": 1,
        }
        (
            mock_entry_with_coordinator.runtime_data.get_power_fee_monthly_estimates.return_value
        ) = {"2025-12": 3.21}
        (
            mock_entry_with_coordinator.runtime_data.get_power_fee_monthly_peaks.return_value
        ) = {"2025-12": 4.32}

        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["options"]["tariff_mode"] == "flat"
        assert result["economics_totals"]["purchase_cost"] == 4.56
        assert result["economics_last_period_end"] == "2025-12-17T00:05:00+02:00"
        assert result["economics_processed_period_count"] == 2
        assert result["skipped_savings_window_count"] == 1
        assert result["attribution_skipped_window_counts"] == {
            "solar_used_in_house_value": 2,
            "solar_export_net_value": 0,
            "battery_house_supply_value": 1,
        }
        assert result["power_fee_monthly_estimates"]["2025-12"] == 3.21
        assert result["power_fee_monthly_peaks"]["2025-12"] == 4.32

    async def test_analytics_data_included(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Analytics summary should be included in diagnostics."""
        analytics = mock_entry_with_coordinator.runtime_data.analytics_state
        analytics.last_period_end = "2025-12-18T00:05:00+02:00"
        analytics._processed_period_ends = {
            "2025-12-17T00:05:00+02:00",
            "2025-12-18T00:05:00+02:00",
        }
        analytics.usable_capacity_candidates_kwh = [9.8, 10.0, 10.2]

        mock_entry_with_coordinator.runtime_data.analytics_last_period_end = (
            analytics.last_period_end
        )
        mock_entry_with_coordinator.runtime_data.analytics_processed_period_count = 2

        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["analytics_last_period_end"] == "2025-12-18T00:05:00+02:00"
        assert result["analytics_processed_period_count"] == 2
        assert result["analytics_candidate_count"] == 3
        assert result["analytics_estimated_usable_capacity_kwh"] == 10.0
        assert result["analytics_total_day_bucket_count"] == 0
        assert result["analytics_rolling_bucket_count"] == 0
        assert result["analytics_open_episode"] is None
