"""Base entity for Elisa Kotiakku."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import ElisaKotiakkuCoordinator


class ElisaKotiakkuEntity(CoordinatorEntity[ElisaKotiakkuCoordinator]):
    """Base class for Elisa Kotiakku entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: ElisaKotiakkuCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        config_entry = coordinator.config_entry
        assert config_entry is not None
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        config_entry = self.coordinator.config_entry
        assert config_entry is not None
        return DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Elisa Kotiakku",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
