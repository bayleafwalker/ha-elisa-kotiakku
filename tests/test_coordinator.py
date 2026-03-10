"""Tests for the Elisa Kotiakku DataUpdateCoordinator."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.elisa_kotiakku.analytics import DailyAnalyticsBucket
from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    ElisaKotiakkuRateLimitError,
)
from custom_components.elisa_kotiakku.const import (
    CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
    CONF_DAY_IMPORT_RETAILER_MARGIN,
    CONF_ELECTRICITY_TAX_FEE,
    CONF_EXPORT_RETAILER_ADJUSTMENT,
    CONF_GRID_EXPORT_TRANSFER_FEE,
    CONF_GRID_IMPORT_TRANSFER_FEE,
    CONF_IMPORT_RETAILER_MARGIN,
    CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    CONF_NIGHT_IMPORT_RETAILER_MARGIN,
    CONF_POWER_FEE_RATE,
    CONF_POWER_FEE_RULE,
    CONF_TARIFF_MODE,
    DEFAULT_WINDOW_HOURS,
    POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME,
    TARIFF_MODE_DAY_NIGHT,
)
from custom_components.elisa_kotiakku.coordinator import (
    ElisaKotiakkuCoordinator,
    _measurement_timestamp,
    _parse_iso8601,
)
from custom_components.elisa_kotiakku.economics_engine import (
    _load_float_map,
    _load_hour_bucket_store,
    _load_int_map,
)
from custom_components.elisa_kotiakku.util import (
    measurement_duration_hours as _measurement_duration_hours,
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
    solar_to_house_kw: float = 0.0,
    grid_to_house_kw: float = 2.0,
    battery_to_house_kw: float = 0.0,
    solar_to_grid_kw: float = 0.0,
    solar_to_battery_kw: float = 0.0,
    spot_price_cents_per_kwh: float = 2.0,
) -> type(SAMPLE_MEASUREMENT):
    """Build a measurement with a deterministic 5-minute duration."""
    end = _parse_iso8601(start)
    assert end is not None
    period_end = (end + timedelta(minutes=5)).isoformat()
    return replace(
        SAMPLE_MEASUREMENT,
        period_start=start,
        period_end=period_end,
        grid_power_kw=grid_power_kw,
        solar_to_house_kw=solar_to_house_kw,
        grid_to_house_kw=grid_to_house_kw,
        battery_to_house_kw=battery_to_house_kw,
        solar_to_grid_kw=solar_to_grid_kw,
        solar_to_battery_kw=solar_to_battery_kw,
        spot_price_cents_per_kwh=spot_price_cents_per_kwh,
    )


class TestCoordinatorUpdate:
    """Tests for live updates."""

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

    async def test_successful_update_accumulates_energy_and_economics(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        grid_import_kwh = 4.4135 / 12
        baseline_import_kwh = (1.582 + 0.002) / 12
        expected_purchase_cost = grid_import_kwh * 1.87 / 100
        expected_battery_savings = (
            baseline_import_kwh * 1.87 / 100 - expected_purchase_cost
        )

        assert coordinator.get_energy_total("grid_import_energy") == pytest.approx(
            0.367792, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("purchase_cost") == pytest.approx(
            expected_purchase_cost, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("net_site_cost") == pytest.approx(
            expected_purchase_cost, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("battery_savings") == pytest.approx(
            expected_battery_savings, rel=0, abs=1e-6
        )

    async def test_successful_update_accumulates_analytics(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        assert coordinator.analytics_processed_period_count == 1
        assert coordinator.analytics_last_period_end == SAMPLE_MEASUREMENT.period_end
        assert coordinator.get_analytics_value(
            "battery_temperature_average_30d"
        ) == pytest.approx(24.5, rel=0, abs=1e-6)

    async def test_day_night_tariff_uses_night_values(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_TARIFF_MODE: TARIFF_MODE_DAY_NIGHT,
            CONF_IMPORT_RETAILER_MARGIN: 0.2,
            CONF_GRID_IMPORT_TRANSFER_FEE: 4.0,
            CONF_DAY_IMPORT_RETAILER_MARGIN: 0.9,
            CONF_NIGHT_IMPORT_RETAILER_MARGIN: 0.3,
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 5.0,
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 2.0,
            CONF_EXPORT_RETAILER_ADJUSTMENT: -0.1,
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()
        rates = coordinator.get_active_tariff_rates()

        assert rates is not None
        assert rates.tariff_mode == "day_night"
        assert rates.tariff_period == "night"
        assert rates.import_retailer_margin_cents_per_kwh == 0.3
        assert rates.import_transfer_fee_cents_per_kwh == 2.0
        assert rates.export_retailer_adjustment_cents_per_kwh == -0.1
        assert rates.import_unit_price_cents_per_kwh == pytest.approx(2.17)

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
        mock_api_client.async_get_latest.side_effect = ElisaKotiakkuRateLimitError(
            retry_after=900
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coordinator._async_update_data()

        assert coordinator.update_interval == timedelta(seconds=900)

    async def test_success_resets_backoff_to_default(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
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


class TestBackfillAndPersistence:
    """Tests for historical processing and store handling."""

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
        assert coordinator.economics_processed_period_count == 1
        coordinator.async_update_listeners.assert_called_once()
        mock_api_client.async_get_range.assert_awaited_once()

    async def test_backfill_updates_new_attribution_totals(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_range.return_value = [
            _measurement_at(
                "2026-01-05T08:00:00+02:00",
                solar_to_house_kw=1.5,
                battery_to_house_kw=0.5,
                solar_to_grid_kw=0.25,
                solar_to_battery_kw=0.0,
                spot_price_cents_per_kwh=2.0,
            )
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        processed = await coordinator.async_backfill_energy("a", "b")

        assert processed == 1
        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx((1.5 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "solar_export_net_value"
        ) == pytest.approx((0.25 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx((0.5 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_analytics_value(
            "total_avoided_grid_import_energy"
        ) == pytest.approx((2.0 / 12), rel=0, abs=1e-6)

    async def test_backfill_updates_electricity_tax_cost_and_local_use_values(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {CONF_ELECTRICITY_TAX_FEE: 2.79}
        mock_api_client.async_get_range.return_value = [
            _measurement_at(
                "2026-01-05T08:00:00+02:00",
                solar_to_house_kw=1.5,
                battery_to_house_kw=0.5,
                solar_to_grid_kw=0.25,
                solar_to_battery_kw=0.0,
                spot_price_cents_per_kwh=2.0,
            )
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        processed = await coordinator.async_backfill_energy("a", "b")

        assert processed == 1
        assert coordinator.get_economics_total("electricity_tax_cost") == pytest.approx(
            (4.0 / 12) * 2.79 / 100, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx((1.5 / 12) * 4.79 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx((0.5 / 12) * 4.79 / 100, rel=0, abs=1e-6)

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
        assert (
            coordinator.get_energy_last_period_end()
            == "2025-12-17T01:00:00+02:00"
        )
        assert coordinator.energy_processed_period_count == 1

    async def test_load_state_ignores_non_mapping_payloads(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """State loaders should ignore malformed persisted data."""
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._energy_store = MagicMock()
        coordinator._economics_store = MagicMock()
        coordinator._analytics_store = MagicMock()
        coordinator._energy_store.async_load = AsyncMock(return_value="bad")
        coordinator._economics_store.async_load = AsyncMock(return_value="bad")
        coordinator._analytics_store.async_load = AsyncMock(return_value="bad")

        await coordinator.async_load_energy_state()
        await coordinator.async_load_economics_state()
        await coordinator.async_load_analytics_state()

        assert coordinator.energy_processed_period_count == 0
        assert coordinator.economics_processed_period_count == 0
        assert coordinator.analytics_processed_period_count == 0

    async def test_load_economics_state_restores_matching_signature(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._economics_store = MagicMock()
        coordinator._economics_store.async_load = AsyncMock(
            return_value={
                "totals": {
                    "purchase_cost": 12.5,
                    "electricity_tax_cost": 1.75,
                    "solar_used_in_house_value": 2.25,
                },
                "last_period_end": "2025-12-17T01:00:00+02:00",
                "processed_period_ends": ["2025-12-17T01:00:00+02:00"],
                "skipped_savings_window_count": 2,
                "tariff_signature": coordinator.tariff_config.signature(),
                "attribution_skipped_window_counts": {
                    "solar_used_in_house_value": 3,
                    "solar_export_net_value": 1,
                    "battery_house_supply_value": 0,
                },
                "power_fee_hour_buckets": {
                    "2025-12": {
                        "2025-12-17T00:00:00+02:00": {
                            "energy_kwh": 1.5,
                            "duration_hours": 0.25,
                        }
                    }
                },
                "power_fee_monthly_estimates": {"2025-12": 5.0},
                "power_fee_monthly_peaks": {"2025-12": 6.0},
                "baseline_power_fee_hour_buckets": {},
                "baseline_power_fee_monthly_estimates": {},
            }
        )

        await coordinator.async_load_economics_state()

        assert coordinator.get_economics_total("purchase_cost") == 12.5
        assert coordinator.get_economics_total("electricity_tax_cost") == 1.75
        assert coordinator.get_economics_total("solar_used_in_house_value") == 2.25
        assert (
            coordinator.get_economics_last_period_end()
            == "2025-12-17T01:00:00+02:00"
        )
        assert coordinator.economics_processed_period_count == 1
        assert coordinator.get_skipped_savings_window_count() == 2
        assert (
            coordinator.get_attribution_skipped_window_count(
                "solar_used_in_house_value"
            )
            == 3
        )
        assert coordinator.get_current_month_power_fee_estimate() is None

    async def test_load_economics_state_resets_on_tariff_change(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._economics_store = MagicMock()
        coordinator._economics_store.async_load = AsyncMock(
            return_value={
                "totals": {"purchase_cost": 12.5},
                "tariff_signature": "stale-signature",
            }
        )

        await coordinator.async_load_economics_state()

        assert coordinator.get_economics_total("purchase_cost") == 0.0
        assert coordinator.economics_processed_period_count == 0

    async def test_load_analytics_state_restores_persisted_state(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._analytics_store = MagicMock()
        coordinator._analytics_store.async_load = AsyncMock(
            return_value={
                "last_period_end": "2025-12-17T01:00:00+02:00",
                "processed_period_ends": ["2025-12-17T01:00:00+02:00"],
                "usable_capacity_candidates_kwh": [9.8, 10.0, 10.2],
                "daily_buckets": {
                    "2025-12-17": {
                        "solar_to_house_kwh": 1.5,
                        "battery_to_house_kwh": 0.5,
                        "battery_temperature_weighted_sum": 12.25,
                        "battery_temperature_hours": 0.5,
                    }
                },
            }
        )

        await coordinator.async_load_analytics_state()

        assert coordinator.analytics_last_period_end == "2025-12-17T01:00:00+02:00"
        assert coordinator.analytics_processed_period_count == 1
        assert coordinator.analytics_state.candidate_count == 3
        assert coordinator.get_analytics_value(
            "estimated_usable_battery_capacity"
        ) == 10.0
        assert coordinator.get_analytics_value(
            "total_avoided_grid_import_energy"
        ) == 2.0

    async def test_rebuild_economics_resets_non_energy_state(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        older = _measurement_at("2026-01-05T08:00:00+02:00", grid_power_kw=5.0)
        newer = _measurement_at("2026-01-05T09:00:00+02:00", grid_power_kw=3.0)
        mock_api_client.async_get_range.return_value = [older, newer]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_process_measurements([SAMPLE_MEASUREMENT], notify=False)
        previous_energy = coordinator.get_energy_total("grid_import_energy")

        processed = await coordinator.async_rebuild_economics("a", "b")

        assert processed == 2
        assert coordinator.get_energy_total("grid_import_energy") == previous_energy
        assert coordinator.economics_processed_period_count == 2
        assert coordinator.analytics_processed_period_count == 2
        assert coordinator.get_economics_total("purchase_cost") == pytest.approx(
            ((5.0 / 12) * 2.0 + (3.0 / 12) * 2.0) / 100,
            rel=0,
            abs=1e-6,
        )

    async def test_rebuild_economics_returns_zero_when_history_is_empty(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Rebuild should no-op cleanly when the API returns no windows."""
        mock_api_client.async_get_range.return_value = []
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        assert await coordinator.async_rebuild_economics("a", "b") == 0

    @pytest.mark.parametrize(
        ("side_effect", "expected_exception"),
        [
            (ElisaKotiakkuAuthError("bad key"), ConfigEntryAuthFailed),
            (ElisaKotiakkuApiError("broken"), UpdateFailed),
        ],
    )
    async def test_rebuild_economics_propagates_history_errors(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
        side_effect: Exception,
        expected_exception: type[Exception],
    ) -> None:
        """History rebuild should wrap auth and API failures consistently."""
        mock_api_client.async_get_range.side_effect = side_effect
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(expected_exception):
            await coordinator.async_rebuild_economics("a", "b")


class TestEconomicsMath:
    """Tests for tariff and savings calculations."""

    async def test_spot_only_asset_attribution_values(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_latest.return_value = _measurement_at(
            "2026-01-05T08:00:00+02:00",
            solar_to_house_kw=1.0,
            battery_to_house_kw=0.5,
            solar_to_grid_kw=0.25,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx((1.0 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx((0.5 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "solar_export_net_value"
        ) == pytest.approx((0.25 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_analytics_value(
            "total_avoided_grid_import_energy"
        ) == pytest.approx((1.5 / 12), rel=0, abs=1e-6)

    async def test_flat_import_transfer_affects_local_use_value(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_GRID_IMPORT_TRANSFER_FEE: 4.0,
        }
        mock_api_client.async_get_latest.return_value = _measurement_at(
            "2026-01-05T08:00:00+02:00",
            solar_to_house_kw=1.0,
            battery_to_house_kw=1.0,
            solar_to_grid_kw=0.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        expected_value = (1.0 / 12) * 6.0 / 100
        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)

    async def test_electricity_tax_affects_site_cost_and_battery_savings(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_ELECTRICITY_TAX_FEE: 2.79,
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        actual_import_kwh = 4.4135 / 12
        baseline_import_kwh = (1.582 + 0.002) / 12
        expected_tax_cost = actual_import_kwh * 2.79 / 100
        expected_net_site_cost = actual_import_kwh * (1.87 + 2.79) / 100
        expected_battery_savings = (
            baseline_import_kwh * (1.87 + 2.79) / 100
            - expected_net_site_cost
        )

        assert coordinator.get_economics_total("electricity_tax_cost") == pytest.approx(
            expected_tax_cost, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("net_site_cost") == pytest.approx(
            expected_net_site_cost, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("battery_savings") == pytest.approx(
            expected_battery_savings, rel=0, abs=1e-6
        )

    async def test_electricity_tax_affects_local_use_value(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_ELECTRICITY_TAX_FEE: 2.79,
        }
        mock_api_client.async_get_latest.return_value = _measurement_at(
            "2026-01-05T08:00:00+02:00",
            solar_to_house_kw=1.0,
            battery_to_house_kw=1.0,
            solar_to_grid_kw=0.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        expected_value = (1.0 / 12) * 4.79 / 100
        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)

    async def test_day_night_import_transfer_affects_local_use_value(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_TARIFF_MODE: TARIFF_MODE_DAY_NIGHT,
            CONF_DAY_IMPORT_RETAILER_MARGIN: 1.0,
            CONF_NIGHT_IMPORT_RETAILER_MARGIN: 0.5,
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 5.0,
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 2.0,
        }
        mock_api_client.async_get_latest.return_value = _measurement_at(
            "2026-01-05T01:00:00+02:00",
            solar_to_house_kw=1.0,
            battery_to_house_kw=1.0,
            solar_to_grid_kw=0.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        expected_value = (1.0 / 12) * 4.5 / 100
        assert coordinator.get_economics_total(
            "solar_used_in_house_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx(expected_value, rel=0, abs=1e-6)

    async def test_export_transfer_fee_affects_solar_export_net_value(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_EXPORT_RETAILER_ADJUSTMENT: -0.5,
            CONF_GRID_EXPORT_TRANSFER_FEE: 1.0,
        }
        mock_api_client.async_get_latest.return_value = _measurement_at(
            "2026-01-05T08:00:00+02:00",
            solar_to_house_kw=0.0,
            battery_to_house_kw=0.0,
            solar_to_grid_kw=3.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        assert coordinator.get_economics_total(
            "solar_export_net_value"
        ) == pytest.approx((3.0 / 12) * 0.5 / 100, rel=0, abs=1e-6)

    async def test_missing_directional_flows_skip_only_battery_savings(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_latest.return_value = replace(
            SAMPLE_MEASUREMENT,
            grid_to_house_kw=None,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        assert coordinator.get_economics_total("purchase_cost") == pytest.approx(
            (4.4135 / 12) * 1.87 / 100, rel=0, abs=1e-6
        )
        assert coordinator.get_economics_total("battery_savings") == 0.0
        assert coordinator.get_skipped_savings_window_count() == 1

    async def test_missing_directional_flow_skips_only_affected_attribution_total(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_latest.return_value = replace(
            SAMPLE_MEASUREMENT,
            solar_to_house_kw=None,
            solar_to_grid_kw=1.0,
            battery_to_house_kw=0.5,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=2.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator._async_update_data()

        assert coordinator.get_economics_total("solar_used_in_house_value") == 0.0
        assert coordinator.get_economics_total(
            "solar_export_net_value"
        ) == pytest.approx((1.0 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert coordinator.get_economics_total(
            "battery_house_supply_value"
        ) == pytest.approx((0.5 / 12) * 2.0 / 100, rel=0, abs=1e-6)
        assert (
            coordinator.get_attribution_skipped_window_count(
                "solar_used_in_house_value"
            )
            == 1
        )
        assert (
            coordinator.get_attribution_skipped_window_count(
                "solar_export_net_value"
            )
            == 0
        )

    async def test_power_peak_tracked_without_fee_config(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Power peak should be reported even when no power fee rule is set."""
        mock_config_entry.options = {}
        mock_api_client.async_get_range.return_value = [
            _measurement_at("2026-01-05T08:00:00+02:00", grid_power_kw=5.0),
            _measurement_at("2026-01-05T09:00:00+02:00", grid_power_kw=8.5),
            _measurement_at("2026-01-05T10:00:00+02:00", grid_power_kw=2.0),
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_backfill_energy("a", "b")

        assert coordinator.get_current_month_power_peak() == 8.5
        assert coordinator.get_current_month_power_fee_estimate() == 0.0

    async def test_monthly_max_power_fee_estimate(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_POWER_FEE_RULE: POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS,
            CONF_POWER_FEE_RATE: 10.0,
        }
        mock_api_client.async_get_range.return_value = [
            _measurement_at(f"2026-01-05T08:{minute:02d}:00+02:00", grid_power_kw=6.0)
            for minute in range(0, 30, 5)
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_backfill_energy("a", "b")

        assert coordinator.get_current_month_power_peak() == 6.0
        assert coordinator.get_current_month_power_fee_estimate() == 60.0
        assert coordinator.get_economics_total("power_fee_cost") == 60.0

    async def test_monthly_top3_power_fee_estimate(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_POWER_FEE_RULE: POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
            CONF_POWER_FEE_RATE: 12.0,
        }
        mock_api_client.async_get_range.return_value = [
            _measurement_at("2026-01-05T08:00:00+02:00", grid_power_kw=9.0),
            _measurement_at("2026-01-05T09:00:00+02:00", grid_power_kw=6.0),
            _measurement_at("2026-01-05T10:00:00+02:00", grid_power_kw=3.0),
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_backfill_energy("a", "b")

        assert coordinator.get_current_month_power_peak() == 9.0
        assert coordinator.get_current_month_power_fee_estimate() == 72.0

    async def test_winter_weekday_daytime_rule_ignores_non_qualifying_hours(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_POWER_FEE_RULE: (
                POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME
            ),
            CONF_POWER_FEE_RATE: 10.0,
        }
        mock_api_client.async_get_range.return_value = [
            _measurement_at("2026-01-05T08:00:00+02:00", grid_power_kw=9.0),
            _measurement_at("2026-01-05T09:00:00+02:00", grid_power_kw=6.0),
            _measurement_at("2026-01-05T10:00:00+02:00", grid_power_kw=3.0),
            _measurement_at("2026-01-05T23:00:00+02:00", grid_power_kw=20.0),
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_backfill_energy("a", "b")

        # Peak reflects actual max grid import (20 kW at 23:00), not just
        # the fee-qualifying hours.  Fee estimate still uses only qualifying.
        assert coordinator.get_current_month_power_peak() == 20.0
        assert coordinator.get_current_month_power_fee_estimate() == 60.0

    async def test_backfill_wraps_api_error_as_update_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_range.side_effect = ElisaKotiakkuApiError("boom")
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(UpdateFailed, match="historical data"):
            await coordinator.async_backfill_energy("a", "b")

    async def test_backfill_auth_error_raises_config_entry_auth_failed(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_range.side_effect = ElisaKotiakkuAuthError(
            "Token revoked"
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coordinator.async_backfill_energy("a", "b")


class TestAnalyticsMath:
    """Tests for coordinator-backed analytics metrics."""

    async def test_rolling_ratios_use_backfilled_directional_flows(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_api_client.async_get_range.return_value = [
            replace(
                SAMPLE_MEASUREMENT,
                period_start="2026-01-05T08:00:00+02:00",
                period_end="2026-01-05T08:05:00+02:00",
                house_power_kw=-12.0,
                grid_power_kw=3.0,
                solar_power_kw=9.0,
                solar_to_house_kw=6.0,
                solar_to_battery_kw=3.0,
                solar_to_grid_kw=0.0,
                grid_to_house_kw=3.0,
                grid_to_battery_kw=0.0,
                battery_to_house_kw=3.0,
                battery_to_grid_kw=0.0,
                battery_power_kw=0.0,
            ),
            replace(
                SAMPLE_MEASUREMENT,
                period_start="2026-01-06T08:00:00+02:00",
                period_end="2026-01-06T08:05:00+02:00",
                house_power_kw=-12.0,
                grid_power_kw=3.0,
                solar_power_kw=9.0,
                solar_to_house_kw=6.0,
                solar_to_battery_kw=3.0,
                solar_to_grid_kw=0.0,
                grid_to_house_kw=3.0,
                grid_to_battery_kw=0.0,
                battery_to_house_kw=3.0,
                battery_to_grid_kw=0.0,
                battery_power_kw=0.0,
            ),
        ]
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )

        await coordinator.async_backfill_energy("a", "b")

        assert coordinator.get_analytics_value(
            "self_sufficiency_ratio_30d"
        ) == pytest.approx(75.0, rel=0, abs=1e-6)
        assert coordinator.get_analytics_value(
            "solar_self_consumption_ratio_30d"
        ) == pytest.approx(100.0, rel=0, abs=1e-6)
        assert coordinator.get_analytics_value(
            "battery_house_supply_ratio_30d"
        ) == pytest.approx(25.0, rel=0, abs=1e-6)
        assert coordinator.get_analytics_value(
            "battery_charge_from_solar_ratio_30d"
        ) is None

    async def test_estimated_backup_runtime_requires_configured_capacity(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        await coordinator._async_update_data()

        assert coordinator.get_analytics_value("estimated_backup_runtime_hours") is None

    async def test_estimated_backup_runtime_uses_capacity_baseline_and_load(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: 10.0
        }
        mock_api_client.async_get_latest.return_value = replace(
            SAMPLE_MEASUREMENT,
            house_power_kw=-2.0,
            state_of_charge_percent=50.0,
        )
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.analytics_state.usable_capacity_candidates_kwh = [8.0, 8.2, 7.8]

        await coordinator._async_update_data()

        assert coordinator.get_analytics_value(
            "estimated_backup_runtime_hours"
        ) == pytest.approx(2.0, rel=0, abs=1e-6)

    async def test_estimated_battery_health_uses_configured_capacity(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        mock_config_entry.options = {
            CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: 10.0
        }
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.analytics_state.usable_capacity_candidates_kwh = [9.0, 9.5, 10.0]

        assert coordinator.get_analytics_value(
            "estimated_usable_battery_capacity"
        ) == 9.5
        assert coordinator.get_analytics_value(
            "estimated_battery_health"
        ) == 95.0


class TestEnergyHelpers:
    """Unit tests for coordinator helper methods and module-level functions."""

    def test_get_total_returns_none_for_unknown_key(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        assert coordinator.get_energy_total("nonexistent_key") is None
        assert coordinator.get_economics_total("nonexistent_key") is None

    def test_energy_store_update_last_period_end_ignores_older_period(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._energy_state.last_period_end = "2025-12-17T01:00:00+02:00"
        coordinator._energy_state.update_last_period_end(
            "2025-12-17T00:00:00+02:00"
        )

        assert (
            coordinator.get_energy_last_period_end()
            == "2025-12-17T01:00:00+02:00"
        )

    def test_parse_iso8601_returns_none_for_invalid_string(self) -> None:
        assert _parse_iso8601("not-a-date") is None

    def test_helper_getters_handle_missing_or_invalid_live_measurement(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Getter methods should handle missing or invalid live measurements."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.data = None

        assert coordinator.get_active_tariff_rates() is None
        assert coordinator.get_current_month_power_peak() is None
        assert coordinator.get_current_month_power_fee_estimate() is None
        assert coordinator.get_economics_debug_value("unknown") is None
        assert coordinator.get_analytics_debug_value("unknown") is None
        assert coordinator.get_analytics_value("unknown") is None
        assert coordinator.get_attribution_skipped_window_counts() == {
            "solar_used_in_house_value": 0,
            "solar_export_net_value": 0,
            "battery_house_supply_value": 0,
        }
        assert coordinator.get_power_fee_monthly_estimates() == {}
        assert coordinator.get_power_fee_monthly_peaks() == {}

        coordinator.data = replace(SAMPLE_MEASUREMENT, period_start="not-a-date")
        assert coordinator.get_active_tariff_rates() is None
        assert coordinator.get_current_month_power_peak() is None
        assert coordinator.get_current_month_power_fee_estimate() is None

    def test_get_analytics_value_routes_supported_metrics(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Coordinator analytics getter should route supported metric keys."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator.expected_usable_capacity_kwh = 10.0
        coordinator.data = replace(
            SAMPLE_MEASUREMENT,
            house_power_kw=-2.0,
            state_of_charge_percent=50.0,
        )
        bucket = coordinator.analytics_state.daily_buckets.setdefault(
            "2025-12-17", DailyAnalyticsBucket()
        )
        bucket.house_consumption_kwh = 10.0
        bucket.grid_to_house_kwh = 3.0
        bucket.solar_production_kwh = 8.0
        bucket.solar_to_house_kwh = 2.0
        bucket.solar_to_battery_kwh = 2.0
        bucket.battery_to_house_kwh = 1.0
        bucket.battery_charge_kwh = 4.0
        bucket.battery_discharge_kwh = 2.0
        bucket.battery_temperature_weighted_sum = 15.0
        bucket.battery_temperature_hours = 0.5
        bucket.high_temperature_hours = 0.25
        bucket.low_soc_hours = 0.5
        bucket.high_soc_hours = 0.75
        coordinator.analytics_state.usable_capacity_candidates_kwh = [8.0, 10.0]
        coordinator.analytics_state.last_period_end = "2025-12-17T00:05:00+02:00"

        assert coordinator.get_analytics_value("battery_equivalent_full_cycles") == 0.3
        assert (
            coordinator.get_analytics_value("battery_temperature_average_30d")
            == 30.0
        )
        assert (
            coordinator.get_analytics_value("battery_high_temperature_hours_30d")
            == 0.25
        )
        assert coordinator.get_analytics_value("battery_low_soc_hours_30d") == 0.5
        assert coordinator.get_analytics_value("battery_high_soc_hours_30d") == 0.75
        assert coordinator.get_analytics_value("self_sufficiency_ratio_30d") == 70.0
        assert (
            coordinator.get_analytics_value("solar_self_consumption_ratio_30d")
            == 50.0
        )
        assert coordinator.get_analytics_value("battery_house_supply_ratio_30d") == 10.0
        assert (
            coordinator.get_analytics_value("battery_charge_from_solar_ratio_30d")
            == 50.0
        )
        assert coordinator.get_analytics_value("estimated_backup_runtime_hours") == 2.25

    def test_economics_mark_processed_and_live_measurement_fallbacks(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """Fallback timestamp comparisons should still keep the newest string value."""
        coordinator = _make_coordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._economics_state.mark_processed("invalid-a")
        coordinator._economics_state.mark_processed("invalid-b")
        coordinator._maybe_update_live_measurement(
            replace(SAMPLE_MEASUREMENT, period_end="invalid-a")
        )
        coordinator._maybe_update_live_measurement(
            replace(SAMPLE_MEASUREMENT, period_end="invalid-b")
        )

        assert coordinator.get_economics_last_period_end() == "invalid-b"
        assert coordinator.data is not None
        assert coordinator.data.period_end == "invalid-b"

    async def test_save_methods_persist_expected_payloads(
        self,
        mock_hass: MagicMock,
        mock_api_client: AsyncMock,
        mock_config_entry: MagicMock,
    ) -> None:
        """State save helpers should serialize energy, economics, and analytics."""
        coordinator = ElisaKotiakkuCoordinator(
            mock_hass, mock_api_client, mock_config_entry
        )
        coordinator._energy_store = MagicMock()
        coordinator._economics_store = MagicMock()
        coordinator._analytics_store = MagicMock()
        coordinator._energy_store.async_save = AsyncMock()
        coordinator._economics_store.async_save = AsyncMock()
        coordinator._analytics_store.async_save = AsyncMock()
        coordinator._energy_state.totals["grid_import_energy"] = 1.5
        coordinator._energy_state.last_period_end = "2025-12-17T00:05:00+02:00"
        coordinator._energy_state.processed_period_ends.add(
            "2025-12-17T00:05:00+02:00"
        )
        coordinator._economics_state.totals["purchase_cost"] = 2.5
        coordinator._economics_state.last_period_end = (
            "2025-12-17T00:05:00+02:00"
        )
        coordinator.analytics_state.mark_processed("2025-12-17T00:05:00+02:00")

        await coordinator._async_save_energy_state()
        await coordinator._async_save_economics_state()
        await coordinator._async_save_analytics_state()

        coordinator._energy_store.async_save.assert_awaited_once()
        coordinator._economics_store.async_save.assert_awaited_once()
        coordinator._analytics_store.async_save.assert_awaited_once()


def test_load_map_helpers_filter_invalid_values() -> None:
    """Persistence helper loaders should ignore malformed nested values."""
    assert _load_float_map("bad") == {}
    assert _load_float_map({"ok": 1, "skip": "bad"}) == {"ok": 1.0}
    assert _load_int_map(
        {"solar_used_in_house_value": 2, "skip": 9},
        allowed_keys=(
            "solar_used_in_house_value",
            "solar_export_net_value",
        ),
    ) == {
        "solar_used_in_house_value": 2,
        "solar_export_net_value": 0,
    }
    assert _load_hour_bucket_store("bad") == {}
    assert _load_hour_bucket_store(
        {
            "2025-12": {
                "2025-12-17T00:00:00+02:00": {
                    "energy_kwh": 1.5,
                    "duration_hours": 0.25,
                },
                "bad-hour": {"energy_kwh": "bad", "duration_hours": 0.25},
            },
            123: {},
        }
    ) == {
        "2025-12": {
            "2025-12-17T00:00:00+02:00": {
                "energy_kwh": 1.5,
                "duration_hours": 0.25,
            }
        }
    }


def test_measurement_timestamp_returns_none_for_invalid_period_start() -> None:
    """Invalid measurement timestamps should not parse."""
    assert (
        _measurement_timestamp(replace(SAMPLE_MEASUREMENT, period_start="bad")) is None
    )


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
        result = _measurement_duration_hours(
            "2025-12-17T00:05:00+02:00", "2025-12-17T00:00:00+02:00"
        )
        assert result == DEFAULT_WINDOW_HOURS
