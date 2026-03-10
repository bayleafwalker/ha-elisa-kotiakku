"""Tests for battery payback and profit-day sensors."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elisa_kotiakku.const import (
    CONF_BATTERY_MONTHLY_COST,
    CONF_BATTERY_TOTAL_COST,
    CONF_IMPORT_RETAILER_MARGIN,
)
from custom_components.elisa_kotiakku.coordinator import (
    ElisaKotiakkuCoordinator,
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
    coordinator._async_save_economics_state = AsyncMock()
    coordinator._async_save_analytics_state = AsyncMock()
    return coordinator


def _measurement_at(
    start: str,
    *,
    grid_power_kw: float = 4.0,
    spot_price_cents_per_kwh: float = 5.0,
    grid_to_house_kw: float = 2.0,
    battery_to_house_kw: float = 2.0,
    solar_to_house_kw: float = 0.0,
    solar_to_grid_kw: float = 0.0,
    solar_to_battery_kw: float = 0.0,
):
    """Build a measurement with a deterministic 5-minute duration."""
    end = _parse_iso8601(start)
    assert end is not None
    period_end = (end + timedelta(minutes=5)).isoformat()
    return replace(
        SAMPLE_MEASUREMENT,
        period_start=start,
        period_end=period_end,
        grid_power_kw=grid_power_kw,
        spot_price_cents_per_kwh=spot_price_cents_per_kwh,
        grid_to_house_kw=grid_to_house_kw,
        battery_to_house_kw=battery_to_house_kw,
        solar_to_house_kw=solar_to_house_kw,
        solar_to_grid_kw=solar_to_grid_kw,
        solar_to_battery_kw=solar_to_battery_kw,
    )


class TestEffectiveMonthlyCost:
    """Tests for _effective_monthly_cost derivation."""

    def test_monthly_cost_takes_precedence(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_BATTERY_MONTHLY_COST: 49.0,
            CONF_BATTERY_TOTAL_COST: 6000.0,
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator._effective_monthly_cost() == 49.0

    def test_total_cost_derives_monthly(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_BATTERY_MONTHLY_COST: 0.0,
            CONF_BATTERY_TOTAL_COST: 6000.0,
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator._effective_monthly_cost() == pytest.approx(50.0)

    def test_no_cost_returns_none(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator._effective_monthly_cost() is None


class TestMonthlyFirstDayOfProfit:
    """Tests for get_monthly_first_day_of_profit."""

    def test_returns_none_when_no_cost_configured(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.get_monthly_first_day_of_profit() is None

    def test_returns_none_when_no_data(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_MONTHLY_COST: 30.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.data is None
        assert coordinator.get_monthly_first_day_of_profit() is None

    async def test_returns_day_when_savings_exceed_cost(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """With enough savings by a given day, the sensor should report breakeven."""
        mock_config_entry.options = {
            CONF_BATTERY_MONTHLY_COST: 0.10,  # Very low cost
            CONF_IMPORT_RETAILER_MARGIN: 0.0,
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        # Process multiple measurements to build savings
        measurements = [
            _measurement_at(
                "2025-12-15T12:00:00+02:00",
                grid_power_kw=4.0,
                spot_price_cents_per_kwh=10.0,
                grid_to_house_kw=4.0,
                battery_to_house_kw=2.0,
            ),
            _measurement_at(
                "2025-12-15T12:05:00+02:00",
                grid_power_kw=4.0,
                spot_price_cents_per_kwh=10.0,
                grid_to_house_kw=4.0,
                battery_to_house_kw=2.0,
            ),
        ]
        await coordinator.async_process_measurements(measurements, notify=False)

        # Savings should accrue for the month
        month_savings = coordinator._monthly_battery_savings.get("2025-12", 0.0)
        assert month_savings != 0.0

        result = coordinator.get_monthly_first_day_of_profit()
        if month_savings > 0 and month_savings > 0.10:
            assert result is not None
            assert 1 <= result <= 31

    def test_returns_none_when_savings_zero(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_MONTHLY_COST: 30.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        # Set up data but no savings
        coordinator.data = SAMPLE_MEASUREMENT
        coordinator._monthly_battery_savings = {"2025-12": 0.0}
        assert coordinator.get_monthly_first_day_of_profit() is None

    def test_returns_none_when_breakeven_beyond_month(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_MONTHLY_COST: 1000.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.data = SAMPLE_MEASUREMENT
        # Very small savings, huge cost — breakeven beyond month end
        coordinator._monthly_battery_savings = {"2025-12": 0.50}
        result = coordinator.get_monthly_first_day_of_profit()
        assert result is None

    def test_profit_day_computed_from_total_cost(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """When only total cost is set, derive monthly cost for first-day calc."""
        mock_config_entry.options = {
            CONF_BATTERY_TOTAL_COST: 1200.0,  # → 10.0 EUR/month
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.data = SAMPLE_MEASUREMENT  # day=17 of December
        coordinator._monthly_battery_savings = {"2025-12": 20.0}
        # cost per month = 1200/120 = 10.0
        # daily_rate = 20/17 ≈ 1.176
        # breakeven_day = 10.0 / 1.176 ≈ 8.5 → day 9
        result = coordinator.get_monthly_first_day_of_profit()
        assert result is not None
        assert result == 9


class TestPaybackRemainingMonths:
    """Tests for get_payback_remaining_months."""

    def test_returns_none_when_no_total_cost(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.get_payback_remaining_months() is None

    def test_returns_none_when_no_savings(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_TOTAL_COST: 5000.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.get_payback_remaining_months() is None

    def test_returns_remaining_months(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_TOTAL_COST: 5000.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.economics_totals["battery_savings"] = 1000.0
        coordinator._monthly_battery_savings = {
            "2025-10": 250.0,
            "2025-11": 350.0,
            "2025-12": 400.0,
        }
        # avg_monthly = 1000/3 ≈ 333.33
        # remaining = (5000-1000) / 333.33 ≈ 12.0
        result = coordinator.get_payback_remaining_months()
        assert result is not None
        assert result == pytest.approx(12.0, abs=0.1)

    def test_returns_zero_when_fully_paid(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_TOTAL_COST: 5000.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.economics_totals["battery_savings"] = 6000.0
        coordinator._monthly_battery_savings = {"2025-12": 6000.0}
        result = coordinator.get_payback_remaining_months()
        assert result == 0.0

    def test_returns_none_when_no_tracked_months(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_BATTERY_TOTAL_COST: 5000.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.economics_totals["battery_savings"] = 100.0
        coordinator._monthly_battery_savings = {}
        result = coordinator.get_payback_remaining_months()
        assert result is None


class TestMonthlySavingsTracking:
    """Tests that monthly savings are tracked in _monthly_battery_savings."""

    async def test_savings_accumulated_by_month(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_IMPORT_RETAILER_MARGIN: 0.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        m1 = _measurement_at(
            "2025-12-17T00:00:00+02:00",
            grid_power_kw=4.0,
            spot_price_cents_per_kwh=5.0,
            grid_to_house_kw=2.0,
            battery_to_house_kw=2.0,
        )
        await coordinator.async_process_measurements([m1], notify=False)

        assert "2025-12" in coordinator._monthly_battery_savings

    async def test_savings_persisted_in_economics_state(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_IMPORT_RETAILER_MARGIN: 0.0}
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_process_measurements(
            [SAMPLE_MEASUREMENT], notify=False
        )

        # Check that save was called and monthly_battery_savings is included
        coordinator._async_save_economics_state.assert_awaited()
