"""Elisa Kotiakku integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ElisaKotiakkuApiClient
from .const import CONF_API_KEY, DOMAIN
from .coordinator import ElisaKotiakkuCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type ElisaKotiakkuConfigEntry = ConfigEntry[ElisaKotiakkuCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: ElisaKotiakkuConfigEntry
) -> bool:
    """Set up Elisa Kotiakku from a config entry."""
    session = async_get_clientsession(hass)
    client = ElisaKotiakkuApiClient(
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    coordinator = ElisaKotiakkuCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ElisaKotiakkuConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
