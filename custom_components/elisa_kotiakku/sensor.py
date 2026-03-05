"""Sensor platform for Elisa Kotiakku."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElisaKotiakkuConfigEntry
from .api import MeasurementData
from .coordinator import ElisaKotiakkuCoordinator
from .entity import ElisaKotiakkuEntity

# Price unit not in homeassistant.const — define locally
UNIT_CENTS_PER_KWH = "c/kWh"

# Coordinator centralises data updates — no per-entity polling needed
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuSensorDescription(SensorEntityDescription):
    """Describe an Elisa Kotiakku sensor."""

    value_fn: Callable[[MeasurementData], float | None]


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuEnergySensorDescription(SensorEntityDescription):
    """Describe a cumulative energy sensor."""


SENSOR_DESCRIPTIONS: tuple[ElisaKotiakkuSensorDescription, ...] = (
    ElisaKotiakkuSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.state_of_charge_percent,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery_temperature_celsius,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.solar_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.grid_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.house_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_house",
        translation_key="solar_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_battery",
        translation_key="solar_to_battery",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_battery_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_grid",
        translation_key="solar_to_grid",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_grid_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_to_house",
        translation_key="grid_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.grid_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_to_battery",
        translation_key="grid_to_battery",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.grid_to_battery_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_to_house",
        translation_key="battery_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.battery_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_to_grid",
        translation_key="battery_to_grid",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.battery_to_grid_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="spot_price",
        translation_key="spot_price",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.spot_price_cents_per_kwh,
    ),
)

ENERGY_SENSOR_DESCRIPTIONS: tuple[ElisaKotiakkuEnergySensorDescription, ...] = (
    ElisaKotiakkuEnergySensorDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="solar_production_energy",
        translation_key="solar_production_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="house_consumption_energy",
        translation_key="house_consumption_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElisaKotiakkuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elisa Kotiakku sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ElisaKotiakkuSensor(coordinator, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        + [
            ElisaKotiakkuEnergySensor(coordinator, description)
            for description in ENERGY_SENSOR_DESCRIPTIONS
        ]
    )


class ElisaKotiakkuSensor(ElisaKotiakkuEntity, SensorEntity):
    """Representation of an Elisa Kotiakku sensor."""

    entity_description: ElisaKotiakkuSensorDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return extra state attributes (measurement period)."""
        if self.coordinator.data is None:
            return None
        return {
            "period_start": self.coordinator.data.period_start,
            "period_end": self.coordinator.data.period_end,
        }


class ElisaKotiakkuEnergySensor(ElisaKotiakkuEntity, SensorEntity):
    """Representation of a cumulative energy sensor."""

    entity_description: ElisaKotiakkuEnergySensorDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuEnergySensorDescription,
    ) -> None:
        """Initialise the energy sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return cumulative energy in kWh."""
        return self.coordinator.get_energy_total(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the latest period included in the cumulative counter."""
        if self.coordinator.energy_last_period_end is None:
            return None
        return {"last_period_end": self.coordinator.energy_last_period_end}
