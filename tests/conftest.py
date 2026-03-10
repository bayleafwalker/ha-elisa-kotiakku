"""Shared test fixtures for Elisa Kotiakku tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from custom_components.elisa_kotiakku.analytics import AnalyticsState
from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiClient,
    MeasurementData,
)

# ---------------------------------------------------------------------------
# Sample API response payloads
# ---------------------------------------------------------------------------

SAMPLE_API_RESPONSE_ITEM: dict = {
    "period_start": "2025-12-17T00:00:00+02:00",
    "period_end": "2025-12-17T00:05:00+02:00",
    "battery_power_kw": -2.727,
    "state_of_charge_percent": 21.25,
    "solar_power_kw": 0.0,
    "grid_power_kw": 4.4135,
    "house_power_kw": -1.583,
    "solar_to_house_kw": 0.0,
    "solar_to_battery_kw": 0.0,
    "solar_to_grid_kw": 0.0,
    "grid_to_house_kw": 1.582,
    "grid_to_battery_kw": 2.832,
    "battery_to_house_kw": 0.002,
    "battery_to_grid_kw": 0.0,
    "spot_price_cents_per_kwh": 1.87,
    "battery_temperature_celsius": 24.5,
}

SAMPLE_API_RESPONSE: list[dict] = [SAMPLE_API_RESPONSE_ITEM]

SAMPLE_MEASUREMENT = MeasurementData(
    period_start="2025-12-17T00:00:00+02:00",
    period_end="2025-12-17T00:05:00+02:00",
    battery_power_kw=-2.727,
    state_of_charge_percent=21.25,
    solar_power_kw=0.0,
    grid_power_kw=4.4135,
    house_power_kw=-1.583,
    solar_to_house_kw=0.0,
    solar_to_battery_kw=0.0,
    solar_to_grid_kw=0.0,
    grid_to_house_kw=1.582,
    grid_to_battery_kw=2.832,
    battery_to_house_kw=0.002,
    battery_to_grid_kw=0.0,
    spot_price_cents_per_kwh=1.87,
    battery_temperature_celsius=24.5,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_aioresponses():
    """Yield an aioresponses context for mocking HTTP calls."""
    with aioresponses() as m:
        yield m


@pytest.fixture
def api_key() -> str:
    """Return a test API key."""
    return "test-api-key-12345"


@pytest.fixture
def api_client(api_key: str) -> ElisaKotiakkuApiClient:
    """Return an API client without a session (session set per-test)."""
    return ElisaKotiakkuApiClient(api_key=api_key)


@pytest.fixture
def mock_config_entry(api_key: str) -> MagicMock:
    """Return a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"api_key": api_key}
    entry.options = {}
    entry.runtime_data = None
    return entry


@pytest.fixture
def mock_coordinator(mock_config_entry: MagicMock) -> MagicMock:
    """Return a mock coordinator pre-loaded with sample data."""
    coordinator = MagicMock()
    coordinator.data = SAMPLE_MEASUREMENT
    coordinator.config_entry = mock_config_entry
    coordinator.energy_last_period_end = SAMPLE_MEASUREMENT.period_end
    coordinator.economics_last_period_end = SAMPLE_MEASUREMENT.period_end
    coordinator.analytics_last_period_end = SAMPLE_MEASUREMENT.period_end
    coordinator.energy_totals = {}
    coordinator.economics_totals = {}
    coordinator.energy_processed_period_count = 0
    coordinator.economics_processed_period_count = 0
    coordinator.analytics_processed_period_count = 0
    coordinator.skipped_savings_window_count = 0
    coordinator.expected_usable_capacity_kwh = 10.0
    coordinator.analytics_state = AnalyticsState()
    coordinator.get_energy_total = MagicMock(return_value=0.0)
    coordinator.get_economics_total = MagicMock(return_value=0.0)
    coordinator.get_analytics_value = MagicMock(return_value=0.0)
    coordinator.get_analytics_debug_value = MagicMock(return_value=0)
    coordinator.get_attribution_skipped_window_count = MagicMock(return_value=0)
    coordinator.get_attribution_skipped_window_counts = MagicMock(return_value={})
    coordinator.get_active_tariff_rates = MagicMock(return_value=None)
    coordinator.get_current_month_power_peak = MagicMock(return_value=0.0)
    coordinator.get_current_month_power_fee_estimate = MagicMock(return_value=0.0)
    coordinator.get_monthly_first_day_of_profit = MagicMock(return_value=None)
    coordinator.get_payback_remaining_months = MagicMock(return_value=None)
    coordinator.get_power_fee_monthly_estimates = MagicMock(return_value={})
    coordinator.get_power_fee_monthly_peaks = MagicMock(return_value={})
    coordinator.tariff_config = MagicMock()
    coordinator.tariff_config.power_fee_rule = "none"
    coordinator._attribution_skipped_window_counts = {}
    coordinator._power_fee_monthly_estimates = {}
    coordinator._power_fee_monthly_peaks = {}
    coordinator._monthly_battery_savings = {}
    coordinator.battery_monthly_cost = 0.0
    coordinator.battery_total_cost = 0.0
    coordinator.akkureservihyvitys = 0.0
    coordinator._effective_monthly_cost = MagicMock(return_value=None)
    return coordinator
