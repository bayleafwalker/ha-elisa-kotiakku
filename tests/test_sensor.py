"""Tests for the Elisa Kotiakku sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elisa_kotiakku.api import MeasurementData
from custom_components.elisa_kotiakku.sensor import (
    ENERGY_SENSOR_DESCRIPTIONS,
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
    ElisaKotiakkuEnergySensor,
    ElisaKotiakkuSensor,
    async_setup_entry,
)

from .conftest import SAMPLE_MEASUREMENT


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

    def test_all_total_increasing(self) -> None:
        from homeassistant.components.sensor import SensorStateClass

        for desc in ENERGY_SENSOR_DESCRIPTIONS:
            assert desc.state_class == SensorStateClass.TOTAL_INCREASING


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

    def test_extra_state_attributes_none_when_data_is_none(
        self, mock_coordinator: MagicMock
    ) -> None:
        """extra_state_attributes must return None when coordinator has no data."""
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
        mock_coordinator.energy_last_period_end = "2025-12-17T00:05:00+02:00"
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.extra_state_attributes == {
            "last_period_end": "2025-12-17T00:05:00+02:00"
        }

    def test_extra_state_attributes_none_without_period(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.energy_last_period_end = None
        sensor = self._make_sensor(mock_coordinator)
        assert sensor.extra_state_attributes is None


class TestQualityScaleCompliance:
    """Tests for HA Integration Quality Scale requirements."""

    def test_parallel_updates_is_zero(self) -> None:
        assert PARALLEL_UPDATES == 0

    def test_diagnostic_sensors_have_entity_category(self) -> None:
        from homeassistant.helpers.entity import EntityCategory

        diagnostic_keys = {"battery_temperature", "spot_price"}
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in diagnostic_keys:
                assert desc.entity_category == EntityCategory.DIAGNOSTIC


class TestDeviceInfo:
    """Tests for the device_info property on entity base class."""

    def test_device_info_returns_correct_identifiers(
        self, mock_coordinator: MagicMock
    ) -> None:
        """device_info must return a DeviceInfo with the correct identifiers."""
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
        """async_setup_entry must create and register all sensor entities."""
        mock_entry = MagicMock()
        mock_entry.runtime_data = mock_coordinator
        mock_hass = MagicMock()
        mock_add_entities = MagicMock()

        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        sensor_count = len(SENSOR_DESCRIPTIONS) + len(ENERGY_SENSOR_DESCRIPTIONS)
        assert len(entities) == sensor_count
        power_sensors = [e for e in entities if isinstance(e, ElisaKotiakkuSensor)]
        energy_sensors = [e for e in entities if isinstance(e, ElisaKotiakkuEnergySensor)]
        assert len(power_sensors) == len(SENSOR_DESCRIPTIONS)
        assert len(energy_sensors) == len(ENERGY_SENSOR_DESCRIPTIONS)
