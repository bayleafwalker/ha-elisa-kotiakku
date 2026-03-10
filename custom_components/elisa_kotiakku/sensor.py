"""Sensor platform for Elisa Kotiakku."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElisaKotiakkuConfigEntry
from .sensor_derived import (
    COORDINATOR_SENSOR_DESCRIPTIONS,
    ElisaKotiakkuCoordinatorSensor,
    ElisaKotiakkuCoordinatorSensorDescription,
    _active_rate_value,  # noqa: F401
)
from .sensor_energy import (
    ENERGY_SENSOR_DESCRIPTIONS,
    ElisaKotiakkuEnergySensor,
    ElisaKotiakkuEnergySensorDescription,
)
from .sensor_measurement import (
    SENSOR_DESCRIPTIONS,
    ElisaKotiakkuSensor,
    ElisaKotiakkuSensorDescription,
)

PARALLEL_UPDATES = 0

__all__ = [
    "PARALLEL_UPDATES",
    "SENSOR_DESCRIPTIONS",
    "ENERGY_SENSOR_DESCRIPTIONS",
    "COORDINATOR_SENSOR_DESCRIPTIONS",
    "ElisaKotiakkuSensor",
    "ElisaKotiakkuEnergySensor",
    "ElisaKotiakkuCoordinatorSensor",
    "ElisaKotiakkuSensorDescription",
    "ElisaKotiakkuEnergySensorDescription",
    "ElisaKotiakkuCoordinatorSensorDescription",
    "_active_rate_value",
    "async_setup_entry",
]


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
        + [
            ElisaKotiakkuCoordinatorSensor(coordinator, description)
            for description in COORDINATOR_SENSOR_DESCRIPTIONS
        ]
    )
