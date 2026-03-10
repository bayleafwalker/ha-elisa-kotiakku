"""Cumulative energy sensor definitions for Elisa Kotiakku."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy

from .coordinator import ElisaKotiakkuCoordinator
from .entity import ElisaKotiakkuEntity


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuEnergySensorDescription(SensorEntityDescription):
    """Describe a cumulative energy sensor."""


ENERGY_SENSOR_DESCRIPTIONS: tuple[ElisaKotiakkuEnergySensorDescription, ...] = (
    ElisaKotiakkuEnergySensorDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="solar_production_energy",
        translation_key="solar_production_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="house_consumption_energy",
        translation_key="house_consumption_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        entity_registry_enabled_default=False,
    ),
)


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
        last_period_end = self.coordinator.get_energy_last_period_end()
        if last_period_end is None:
            return None
        return {"last_period_end": last_period_end}
