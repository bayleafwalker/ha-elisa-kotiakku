"""Button platform for Elisa Kotiakku maintenance actions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ElisaKotiakkuConfigEntry
from .const import DEFAULT_BACKFILL_HOURS, DOMAIN
from .coordinator import ElisaKotiakkuCoordinator
from .entity import ElisaKotiakkuEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuButtonDescription(ButtonEntityDescription):
    """Describe an Elisa Kotiakku maintenance button."""


BUTTON_DESCRIPTIONS: tuple[ElisaKotiakkuButtonDescription, ...] = (
    ElisaKotiakkuButtonDescription(
        key="backfill_energy",
        translation_key="backfill_energy",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ElisaKotiakkuButtonDescription(
        key="rebuild_economics",
        translation_key="rebuild_economics",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ElisaKotiakkuButtonDescription(
        key="force_data_refresh",
        translation_key="force_data_refresh",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElisaKotiakkuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elisa Kotiakku button entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ElisaKotiakkuButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    )


class ElisaKotiakkuButton(ElisaKotiakkuEntity, ButtonEntity):
    """Representation of an Elisa Kotiakku maintenance button."""

    entity_description: ElisaKotiakkuButtonDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuButtonDescription,
    ) -> None:
        """Initialise the button entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        key = self.entity_description.key
        coordinator = self.coordinator

        if key == "backfill_energy":
            await self._async_backfill_energy(coordinator)
        elif key == "rebuild_economics":
            await self._async_rebuild_economics(coordinator)
        elif key == "force_data_refresh":
            await self._async_force_refresh(coordinator)

    async def _async_backfill_energy(
        self, coordinator: ElisaKotiakkuCoordinator
    ) -> None:
        """Run a default 24-hour energy backfill."""
        end = dt_util.now()
        start = end - timedelta(hours=DEFAULT_BACKFILL_HOURS)
        try:
            processed = await coordinator.async_backfill_energy(
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Backfill energy failed: {err}",
                translation_domain=DOMAIN,
                translation_key="backfill_failed",
                translation_placeholders={"reason": str(err)},
            ) from err
        _LOGGER.info(
            "Button backfill processed %s window(s) for entry %s",
            processed,
            coordinator.config_entry.entry_id,
        )

    async def _async_rebuild_economics(
        self, coordinator: ElisaKotiakkuCoordinator
    ) -> None:
        """Reset and rebuild economics from the last 24 hours."""
        end = dt_util.now()
        start = end - timedelta(hours=DEFAULT_BACKFILL_HOURS)
        try:
            processed = await coordinator.async_rebuild_economics(
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Rebuild economics failed: {err}",
                translation_domain=DOMAIN,
                translation_key="backfill_failed",
                translation_placeholders={"reason": str(err)},
            ) from err
        _LOGGER.info(
            "Button rebuild economics processed %s window(s) for entry %s",
            processed,
            coordinator.config_entry.entry_id,
        )

    async def _async_force_refresh(
        self, coordinator: ElisaKotiakkuCoordinator
    ) -> None:
        """Force an immediate coordinator data refresh."""
        await coordinator.async_request_refresh()
