"""DataUpdateCoordinator for Elisa Kotiakku."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
    MeasurementData,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElisaKotiakkuCoordinator(DataUpdateCoordinator[MeasurementData | None]):
    """Coordinator to poll the Elisa Kotiakku API every 5 minutes."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ElisaKotiakkuApiClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> MeasurementData | None:
        """Fetch the latest measurement from the API."""
        try:
            return await self.client.async_get_latest()
        except ElisaKotiakkuAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ElisaKotiakkuApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
