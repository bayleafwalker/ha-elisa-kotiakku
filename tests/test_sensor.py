"""Tests for the Elisa Kotiakku sensor platform."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from custom_components.elisa_kotiakku.api import MeasurementData
from custom_components.elisa_kotiakku.sensor import (
    COORDINATOR_SENSOR_DESCRIPTIONS,
    ENERGY_SENSOR_DESCRIPTIONS,
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
    ElisaKotiakkuCoordinatorSensor,
    ElisaKotiakkuEnergySensor,
    ElisaKotiakkuSensor,
    _active_rate_value,
    async_setup_entry,
)
from custom_components.elisa_kotiakku.tariff import ActiveTariffRates

from .conftest import SAMPLE_MEASUREMENT

# Common tariff rates reused across coordinator sensor tests.
_SAMPLE_ACTIVE_RATES = ActiveTariffRates(
    tariff_mode="day_night",
    tariff_period="night",
    import_retailer_margin_cents_per_kwh=1.2,
    import_transfer_fee_cents_per_kwh=4.1,
    electricity_tax_cents_per_kwh=2.79,
    export_retailer_adjustment_cents_per_kwh=-0.2,
    export_transfer_fee_cents_per_kwh=0.0,
    import_unit_price_cents_per_kwh=5.4,
    export_unit_price_cents_per_kwh=1.6,
)


class TestPowerSensorDescriptions:
    """Tests for measurement sensor descriptions."""

    EXPECTED_KEYS = {
        "battery_power",
        "state_of_charge",
        "battery_temperature",
        "solar_power",
        "grid_power",
        "house_power",
        "solar_to_house",
        "solar_to_battery",
        "solar_to_grid",
        "grid_to_house",
        "grid_to_battery",
        "battery_to_house",
        "battery_to_grid",
        "spot_price",
    }

    def test_all_expected_sensors_defined(self) -> None:
        keys = {d.key for d in SENSOR_DESCRIPTIONS}
        assert keys == self.EXPECTED_KEYS

    def test_count(self) -> None:
        assert len(SENSOR_DESCRIPTIONS) == 14

    def test_all_have_translation_key(self) -> None:
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.translation_key == desc.key


class TestEnergySensorDescriptions:
    """Tests for cumulative energy sensor descriptions."""

    EXPECTED_KEYS = {
        "grid_import_energy",
        "grid_export_energy",
        "solar_production_energy",
        "house_consumption_energy",
        "battery_charge_energy",
        "battery_discharge_energy",
    }

    def test_all_expected_energy_sensors_defined(self) -> None:
        keys = {d.key for d in ENERGY_SENSOR_DESCRIPTIONS}
        assert keys == self.EXPECTED_KEYS

    def test_count(self) -> None:
        assert len(ENERGY_SENSOR_DESCRIPTIONS) == 6


class TestCoordinatorSensorDescriptions:
    """Tests for coordinator-derived sensor descriptions."""

    EXPECTED_KEYS = {
        "configured_tariff_preset",
        "active_tariff_mode",
        "active_tariff_period",
        "configured_power_fee_rule",
        "active_import_retailer_margin",
        "active_import_transfer_fee",
        "active_electricity_tax_fee",
        "active_export_retailer_adjustment",
        "active_export_transfer_fee",
        "active_import_unit_price",
        "active_export_unit_price",
        "total_purchase_cost",
        "total_import_transfer_cost",
        "total_electricity_tax_cost",
        "total_export_revenue",
        "total_export_transfer_cost",
        "total_power_fee_cost",
        "total_net_site_electricity_cost",
        "total_battery_savings",
        "total_solar_used_in_house_value",
        "total_solar_export_net_value",
        "total_battery_house_supply_value",
        "total_avoided_grid_import_energy",
        "current_month_power_peak",
        "current_month_power_fee_estimate",
        "monthly_first_day_of_profit",
        "payback_remaining_months",
        "estimated_usable_battery_capacity",
        "estimated_battery_health",
        "battery_equivalent_full_cycles",
        "battery_temperature_average_30d",
        "battery_high_temperature_hours_30d",
        "battery_low_soc_hours_30d",
        "battery_high_soc_hours_30d",
        "self_sufficiency_ratio_30d",
        "solar_self_consumption_ratio_30d",
        "battery_house_supply_ratio_30d",
        "battery_charge_from_solar_ratio_30d",
        "estimated_backup_runtime_hours",
        "usable_capacity_candidate_count",
        "analytics_processed_periods",
        "analytics_total_day_buckets",
        "analytics_rolling_day_buckets",
        "skipped_savings_windows",
        "economics_processed_periods",
    }

    def test_all_expected_coordinator_sensors_defined(self) -> None:
        keys = {d.key for d in COORDINATOR_SENSOR_DESCRIPTIONS}
        assert keys == self.EXPECTED_KEYS

    def test_count(self) -> None:
        assert len(COORDINATOR_SENSOR_DESCRIPTIONS) == 45

    def test_all_have_translation_key(self) -> None:
        for desc in COORDINATOR_SENSOR_DESCRIPTIONS:
            assert desc.translation_key == desc.key


class TestSensorValueExtraction:
    """Tests for value_fn on each measurement sensor description."""

    @pytest.mark.parametrize(
        ("key", "expected_value"),
        [
            ("battery_power", -2.727),
            ("state_of_charge", 21.25),
            ("battery_temperature", 24.5),
            ("solar_power", 0.0),
            ("grid_power", 4.4135),
            ("house_power", -1.583),
            ("solar_to_house", 0.0),
            ("solar_to_battery", 0.0),
            ("solar_to_grid", 0.0),
            ("grid_to_house", 1.582),
            ("grid_to_battery", 2.832),
            ("battery_to_house", 0.002),
            ("battery_to_grid", 0.0),
            ("spot_price", 1.87),
        ],
    )
    def test_value_fn_extracts_correct_field(
        self, key: str, expected_value: float
    ) -> None:
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        assert desc.value_fn(SAMPLE_MEASUREMENT) == expected_value

    def test_value_fn_returns_none_for_null_fields(self) -> None:
        minimal = MeasurementData(
            period_start="2025-12-17T00:00:00+02:00",
            period_end="2025-12-17T00:05:00+02:00",
        )
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.value_fn(minimal) is None


class TestElisaKotiakkuSensor:
    """Tests for measurement sensor entities."""

    def _make_sensor(
        self,
        mock_coordinator: MagicMock,
        key: str = "battery_power",
    ) -> ElisaKotiakkuSensor:
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        return ElisaKotiakkuSensor(mock_coordinator, desc)

    def test_native_value(self, mock_coordinator: MagicMock) -> None:
        sensor = self._make_sensor(mock_coordinator, "battery_power")
        assert sensor.native_value == -2.727

    def test_native_value_none_when_no_data(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.data = None
        sensor = self._make_sensor(mock_coordinator, "battery_power")
        assert sensor.native_value is None

    def test_extra_state_attributes(self, mock_coordinator: MagicMock) -> None:
        sensor = self._make_sensor(mock_coordinator, "solar_power")
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["period_start"] == "2025-12-17T00:00:00+02:00"
        assert attrs["period_end"] == "2025-12-17T00:05:00+02:00"

    def test_extra_state_attributes_none_when_no_data(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.data = None
        sensor = self._make_sensor(mock_coordinator, "solar_power")
        assert sensor.extra_state_attributes is None

    def test_unique_id(self, mock_coordinator: MagicMock) -> None:
        sensor = self._make_sensor(mock_coordinator, "grid_power")
        assert sensor.unique_id == "test_entry_id_grid_power"


class TestElisaKotiakkuEnergySensor:
    """Tests for cumulative energy sensor entities."""

    def _make_sensor(
        self,
        mock_coordinator: MagicMock,
        key: str = "grid_import_energy",
    ) -> ElisaKotiakkuEnergySensor:
        desc = next(d for d in ENERGY_SENSOR_DESCRIPTIONS if d.key == key)
        return ElisaKotiakkuEnergySensor(mock_coordinator, desc)

    def test_native_value_uses_coordinator_total(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_energy_total = MagicMock(return_value=12.34)
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.native_value == 12.34
        mock_coordinator.get_energy_total.assert_called_once_with("grid_import_energy")

    def test_extra_state_attributes(self, mock_coordinator: MagicMock) -> None:
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00"
        }

    def test_extra_state_attributes_none_without_period_end(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.energy_last_period_end = None
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.extra_state_attributes is None


class TestElisaKotiakkuCoordinatorSensor:
    """Tests for coordinator-derived sensor entities."""

    def _make_sensor(
        self,
        mock_coordinator: MagicMock,
        key: str = "total_purchase_cost",
    ) -> ElisaKotiakkuCoordinatorSensor:
        desc = next(d for d in COORDINATOR_SENSOR_DESCRIPTIONS if d.key == key)
        return ElisaKotiakkuCoordinatorSensor(mock_coordinator, desc)

    def test_active_rate_sensor_reads_active_tariff(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_active_tariff_rates.return_value = _SAMPLE_ACTIVE_RATES
        sensor = self._make_sensor(mock_coordinator, "active_import_unit_price")
        assert sensor.native_value == 5.4

    def test_active_electricity_tax_sensor_reads_active_tariff(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_active_tariff_rates.return_value = _SAMPLE_ACTIVE_RATES
        sensor = self._make_sensor(mock_coordinator, "active_electricity_tax_fee")
        assert sensor.native_value == 2.79

    def test_debug_string_sensor_reads_mode(self, mock_coordinator: MagicMock) -> None:
        mock_coordinator.get_active_tariff_rates.return_value = _SAMPLE_ACTIVE_RATES
        sensor = self._make_sensor(mock_coordinator, "active_tariff_period")
        assert sensor.native_value == "night"

    def test_preset_sensor_reads_configured_preset(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.tariff_config.tariff_preset = (
            "caruna_espoo_night_2026_01"
        )
        sensor = self._make_sensor(mock_coordinator, "configured_tariff_preset")
        assert sensor.native_value == "caruna_espoo_night_2026_01"

    def test_total_sensor_uses_economics_total(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_economics_total = MagicMock(return_value=4.56)
        sensor = self._make_sensor(mock_coordinator, "total_purchase_cost")
        assert sensor.native_value == 4.56
        mock_coordinator.get_economics_total.assert_called_once_with("purchase_cost")

    def test_total_electricity_tax_sensor_uses_economics_total(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_economics_total = MagicMock(return_value=1.23)
        sensor = self._make_sensor(mock_coordinator, "total_electricity_tax_cost")
        assert sensor.native_value == 1.23
        mock_coordinator.get_economics_total.assert_called_once_with(
            "electricity_tax_cost"
        )

    def test_new_attribution_value_sensor_uses_economics_total(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_economics_total = MagicMock(return_value=7.89)
        sensor = self._make_sensor(
            mock_coordinator, "total_solar_used_in_house_value"
        )
        assert sensor.native_value == 7.89
        mock_coordinator.get_economics_total.assert_called_once_with(
            "solar_used_in_house_value"
        )

    def test_analytics_sensor_uses_analytics_getter(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.get_analytics_value = MagicMock(return_value=92.1)
        sensor = self._make_sensor(mock_coordinator, "estimated_battery_health")
        assert sensor.native_value == 92.1
        mock_coordinator.get_analytics_value.assert_called_once_with(
            "estimated_battery_health"
        )

    def test_current_month_power_sensors_use_coordinator(
        self, mock_coordinator: MagicMock
    ) -> None:
        peak = self._make_sensor(mock_coordinator, "current_month_power_peak")
        estimate = self._make_sensor(
            mock_coordinator, "current_month_power_fee_estimate"
        )
        assert peak.native_value == 0.0
        assert estimate.native_value == 0.0

    def test_battery_savings_attributes_include_skip_count(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = "2025-12-17T00:05:00+02:00"
        mock_coordinator.skipped_savings_window_count = 3
        mock_coordinator.tariff_config.power_fee_rule = "monthly_max_all_hours"
        mock_coordinator.get_active_tariff_rates.return_value = _SAMPLE_ACTIVE_RATES
        sensor = self._make_sensor(mock_coordinator, "total_battery_savings")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00",
            "power_fee_rule": "monthly_max_all_hours",
            "tariff_mode": "day_night",
            "tariff_period": "night",
            "skipped_windows": 3,
            "may_be_negative_when_battery_strategy_underperforms": True,
        }

    def test_power_fee_estimate_attributes_explain_monotonic_behavior(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = "2025-12-17T00:05:00+02:00"
        sensor = self._make_sensor(mock_coordinator, "current_month_power_fee_estimate")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00",
            "power_fee_rule": "none",
            "estimate_monotonic_within_month": True,
            "decreases_require_rebuild": True,
        }

    def test_battery_health_attributes_include_heuristic_context(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = "2025-12-18T00:05:00+02:00"
        mock_coordinator.expected_usable_capacity_kwh = 10.5
        mock_coordinator.analytics_state.usable_capacity_candidates_kwh = [
            9.8,
            10.0,
            10.2,
            10.4,
        ]
        sensor = self._make_sensor(mock_coordinator, "estimated_battery_health")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-18T00:05:00+02:00",
            "method": "heuristic",
            "usable_capacity_candidate_count": 4,
            "configured_expected_usable_capacity_kwh": 10.5,
        }

    def test_solar_direct_use_value_attributes_include_basis_and_skip_count(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = "2025-12-17T00:05:00+02:00"
        mock_coordinator.tariff_config.power_fee_rule = "monthly_max_all_hours"
        mock_coordinator.get_attribution_skipped_window_count = MagicMock(
            return_value=2
        )
        mock_coordinator.get_active_tariff_rates.return_value = replace(
            _SAMPLE_ACTIVE_RATES, export_transfer_fee_cents_per_kwh=0.3
        )
        sensor = self._make_sensor(
            mock_coordinator, "total_solar_used_in_house_value"
        )
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00",
            "power_fee_rule": "monthly_max_all_hours",
            "tariff_mode": "day_night",
            "tariff_period": "night",
            "value_basis": "full_avoided_import",
            "includes_power_fee": False,
            "includes_electricity_tax": True,
            "skipped_directional_windows": 2,
        }

    def test_battery_house_supply_value_attributes_explain_interpretation(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = "2025-12-17T00:05:00+02:00"
        mock_coordinator.get_attribution_skipped_window_count = MagicMock(
            return_value=1
        )
        sensor = self._make_sensor(
            mock_coordinator, "total_battery_house_supply_value"
        )
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00",
            "power_fee_rule": "none",
            "value_basis": "full_avoided_import",
            "includes_power_fee": False,
            "includes_electricity_tax": True,
            "skipped_directional_windows": 1,
            "interpretation": "gross_avoided_import_not_net_savings",
        }

    def test_solar_export_value_attributes_exclude_electricity_tax(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = "2025-12-17T00:05:00+02:00"
        mock_coordinator.get_attribution_skipped_window_count = MagicMock(
            return_value=4
        )
        sensor = self._make_sensor(mock_coordinator, "total_solar_export_net_value")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00",
            "power_fee_rule": "none",
            "value_basis": "net_export_after_transfer",
            "includes_power_fee": False,
            "includes_electricity_tax": False,
            "skipped_directional_windows": 4,
        }

    def test_backup_runtime_attributes_explain_instantaneous_load_basis(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = "2025-12-18T00:05:00+02:00"
        sensor = self._make_sensor(mock_coordinator, "estimated_backup_runtime_hours")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-18T00:05:00+02:00",
            "basis": "instantaneous_house_load",
            "may_be_spiky_with_low_or_variable_load": True,
        }

    def test_economics_sensor_attributes_none_without_period_end(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.economics_last_period_end = None
        sensor = self._make_sensor(mock_coordinator, "total_purchase_cost")
        assert sensor.extra_state_attributes is None

    def test_analytics_sensor_attributes_none_without_period_end(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = None
        sensor = self._make_sensor(mock_coordinator, "estimated_battery_health")
        assert sensor.extra_state_attributes is None

    def test_estimated_capacity_attributes_include_candidate_count(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = "2025-12-18T00:05:00+02:00"
        mock_coordinator.analytics_state.usable_capacity_candidates_kwh = [9.8, 10.0]
        sensor = self._make_sensor(
            mock_coordinator, "estimated_usable_battery_capacity"
        )
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-18T00:05:00+02:00",
            "usable_capacity_candidate_count": 2,
        }

    def test_rolling_sensor_attributes_include_window_context(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = "2025-12-18T00:05:00+02:00"
        mock_coordinator.analytics_state.rolling_bucket_count = MagicMock(
            return_value=7
        )
        sensor = self._make_sensor(mock_coordinator, "self_sufficiency_ratio_30d")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-18T00:05:00+02:00",
            "rolling_window_days": 30,
            "rolling_bucket_count": 7,
        }

    def test_avoided_grid_import_energy_attributes_explain_interpretation(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.analytics_last_period_end = "2025-12-18T00:05:00+02:00"
        sensor = self._make_sensor(mock_coordinator, "total_avoided_grid_import_energy")
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-18T00:05:00+02:00",
            "interpretation": "solar_to_house_plus_battery_to_house",
        }


def test_active_rate_value_handles_missing_and_unsupported_values() -> None:
    """Active-rate helper should ignore absent rates and unsupported attribute types."""
    coordinator = MagicMock()
    coordinator.get_active_tariff_rates.return_value = None
    assert _active_rate_value(coordinator, "tariff_mode") is None

    coordinator.get_active_tariff_rates.return_value = MagicMock(
        tariff_mode=["not", "supported"]
    )
    assert _active_rate_value(coordinator, "tariff_mode") is None


class TestQualityScaleCompliance:
    """Tests for HA Integration Quality Scale requirements."""

    def test_parallel_updates_is_zero(self) -> None:
        assert PARALLEL_UPDATES == 0

    def test_diagnostic_sensors_have_entity_category(self) -> None:
        from homeassistant.helpers.entity import EntityCategory

        diagnostic_keys = {
            "configured_tariff_preset",
            "battery_temperature",
            "spot_price",
            "active_tariff_mode",
            "active_tariff_period",
            "configured_power_fee_rule",
            "active_import_retailer_margin",
            "active_import_transfer_fee",
            "active_electricity_tax_fee",
            "active_export_retailer_adjustment",
            "active_export_transfer_fee",
            "usable_capacity_candidate_count",
            "analytics_processed_periods",
            "analytics_total_day_buckets",
            "analytics_rolling_day_buckets",
            "skipped_savings_windows",
            "economics_processed_periods",
        }
        for desc in SENSOR_DESCRIPTIONS + COORDINATOR_SENSOR_DESCRIPTIONS:
            if desc.key in diagnostic_keys:
                assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_monetary_sensors_have_no_state_class(self) -> None:
        monetary = [
            desc
            for desc in SENSOR_DESCRIPTIONS + COORDINATOR_SENSOR_DESCRIPTIONS
            if desc.device_class == "monetary"
        ]
        for desc in monetary:
            assert desc.state_class is None


class TestDeviceInfo:
    """Tests for the device_info property on entity base class."""

    def test_device_info_returns_correct_identifiers(
        self, mock_coordinator: MagicMock
    ) -> None:
        from custom_components.elisa_kotiakku.const import DOMAIN, MANUFACTURER, MODEL

        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_power")
        sensor = ElisaKotiakkuSensor(mock_coordinator, desc)

        info = sensor.device_info
        assert (DOMAIN, "test_entry_id") in info["identifiers"]
        assert info["manufacturer"] == MANUFACTURER
        assert info["model"] == MODEL


class TestAsyncSetupEntry:
    """Tests for the async_setup_entry platform entrypoint."""

    async def test_async_setup_entry_adds_all_sensor_entities(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        mock_hass = MagicMock()
        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        sensor_count = (
            len(SENSOR_DESCRIPTIONS)
            + len(ENERGY_SENSOR_DESCRIPTIONS)
            + len(COORDINATOR_SENSOR_DESCRIPTIONS)
        )
        assert len(entities) == sensor_count
        measurement_sensors = [
            e for e in entities if isinstance(e, ElisaKotiakkuSensor)
        ]
        energy_sensors = [
            e for e in entities if isinstance(e, ElisaKotiakkuEnergySensor)
        ]
        coordinator_sensors = [
            e for e in entities if isinstance(e, ElisaKotiakkuCoordinatorSensor)
        ]
        assert len(measurement_sensors) == len(SENSOR_DESCRIPTIONS)
        assert len(energy_sensors) == len(ENERGY_SENSOR_DESCRIPTIONS)
        assert len(coordinator_sensors) == len(COORDINATOR_SENSOR_DESCRIPTIONS)
