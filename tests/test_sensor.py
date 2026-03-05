"""Tests for the Elisa Kotiakku sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.elisa_kotiakku.api import MeasurementData
from custom_components.elisa_kotiakku.sensor import (
    PARALLEL_UPDATES,
    SENSOR_DESCRIPTIONS,
    ElisaKotiakkuSensor,
    ElisaKotiakkuSensorDescription,
)

from .conftest import SAMPLE_MEASUREMENT


# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


class TestSensorDescriptions:
    """Tests for sensor description definitions."""

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
        """All 14 sensors from the API are defined."""
        keys = {d.key for d in SENSOR_DESCRIPTIONS}
        assert keys == self.EXPECTED_KEYS

    def test_count(self) -> None:
        """Exactly 14 sensor descriptions."""
        assert len(SENSOR_DESCRIPTIONS) == 14

    def test_all_have_translation_key(self) -> None:
        """Every description has a translation_key matching its key."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.translation_key == desc.key

    def test_all_have_unit(self) -> None:
        """Every description has a unit of measurement."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.native_unit_of_measurement is not None

    def test_all_have_device_class(self) -> None:
        """Every description has a device class."""
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.device_class is not None

    def test_all_have_state_class_measurement(self) -> None:
        """All sensors use MEASUREMENT state class."""
        from homeassistant.components.sensor import SensorStateClass

        for desc in SENSOR_DESCRIPTIONS:
            assert desc.state_class == SensorStateClass.MEASUREMENT


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------


class TestSensorValueExtraction:
    """Tests for value_fn on each sensor description."""

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
        """Each value_fn extracts the right field from MeasurementData."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        assert desc.value_fn(SAMPLE_MEASUREMENT) == expected_value

    def test_value_fn_returns_none_for_null_fields(self) -> None:
        """value_fn returns None when the measurement field is None."""
        minimal = MeasurementData(
            period_start="2025-12-17T00:00:00+02:00",
            period_end="2025-12-17T00:05:00+02:00",
        )
        for desc in SENSOR_DESCRIPTIONS:
            assert desc.value_fn(minimal) is None


# ---------------------------------------------------------------------------
# Sensor entity
# ---------------------------------------------------------------------------


class TestElisaKotiakkuSensor:
    """Tests for the sensor entity class."""

    def _make_sensor(
        self,
        mock_coordinator: MagicMock,
        key: str = "battery_power",
    ) -> ElisaKotiakkuSensor:
        """Create a sensor instance for testing."""
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        return ElisaKotiakkuSensor(mock_coordinator, desc)

    def test_native_value(self, mock_coordinator: MagicMock) -> None:
        """Sensor returns the correct native_value."""
        sensor = self._make_sensor(mock_coordinator, "battery_power")
        assert sensor.native_value == -2.727

    def test_native_value_none_when_no_data(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Sensor returns None when coordinator has no data."""
        mock_coordinator.data = None
        sensor = self._make_sensor(mock_coordinator, "battery_power")
        assert sensor.native_value is None

    def test_extra_state_attributes(self, mock_coordinator: MagicMock) -> None:
        """Extra attributes contain period_start and period_end."""
        sensor = self._make_sensor(mock_coordinator, "solar_power")
        attrs = sensor.extra_state_attributes

        assert attrs is not None
        assert attrs["period_start"] == "2025-12-17T00:00:00+02:00"
        assert attrs["period_end"] == "2025-12-17T00:05:00+02:00"

    def test_extra_state_attributes_none_when_no_data(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Extra attributes return None when coordinator has no data."""
        mock_coordinator.data = None
        sensor = self._make_sensor(mock_coordinator, "solar_power")
        assert sensor.extra_state_attributes is None

    def test_unique_id(self, mock_coordinator: MagicMock) -> None:
        """Unique ID is composed of entry_id and sensor key."""
        sensor = self._make_sensor(mock_coordinator, "grid_power")
        assert sensor.unique_id == "test_entry_id_grid_power"

    def test_entity_description_stored(
        self, mock_coordinator: MagicMock
    ) -> None:
        """Entity description is stored on the sensor."""
        sensor = self._make_sensor(mock_coordinator, "spot_price")
        assert sensor.entity_description.key == "spot_price"


# ---------------------------------------------------------------------------
# Quality scale compliance
# ---------------------------------------------------------------------------


class TestQualityScaleCompliance:
    """Tests for HA Integration Quality Scale requirements."""

    def test_parallel_updates_is_zero(self) -> None:
        """PARALLEL_UPDATES is 0 because coordinator centralises polling."""
        assert PARALLEL_UPDATES == 0

    def test_diagnostic_sensors_have_entity_category(self) -> None:
        """Battery temperature and spot price are EntityCategory.DIAGNOSTIC."""
        from homeassistant.helpers.entity import EntityCategory

        diagnostic_keys = {"battery_temperature", "spot_price"}
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in diagnostic_keys:
                assert desc.entity_category == EntityCategory.DIAGNOSTIC, (
                    f"{desc.key} should have entity_category=DIAGNOSTIC"
                )

    def test_flow_breakdown_sensors_disabled_by_default(self) -> None:
        """Power-flow breakdown sensors are disabled by default."""
        disabled_keys = {
            "solar_to_house",
            "solar_to_battery",
            "solar_to_grid",
            "grid_to_house",
            "grid_to_battery",
            "battery_to_house",
            "battery_to_grid",
        }
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in disabled_keys:
                assert desc.entity_registry_enabled_default is False, (
                    f"{desc.key} should be disabled by default"
                )

    def test_primary_sensors_enabled_by_default(self) -> None:
        """Primary sensors (battery_power, soc, etc.) remain enabled."""
        enabled_keys = {
            "battery_power",
            "state_of_charge",
            "solar_power",
            "grid_power",
            "house_power",
        }
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in enabled_keys:
                assert desc.entity_registry_enabled_default is True, (
                    f"{desc.key} should be enabled by default"
                )

    def test_non_diagnostic_sensors_have_no_entity_category(self) -> None:
        """Primary sensors should not have an entity category set."""
        non_diagnostic_keys = {
            "battery_power",
            "state_of_charge",
            "solar_power",
            "grid_power",
            "house_power",
        }
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in non_diagnostic_keys:
                assert desc.entity_category is None, (
                    f"{desc.key} should not have an entity category"
                )
