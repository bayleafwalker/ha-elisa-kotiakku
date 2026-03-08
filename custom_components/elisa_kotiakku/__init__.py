"""Elisa Kotiakku integration for Home Assistant."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ElisaKotiakkuApiClient
from .const import (
    ATTR_END_TIME,
    ATTR_ENTRY_ID,
    ATTR_HOURS,
    ATTR_START_TIME,
    CONF_API_KEY,
    CONF_STARTUP_BACKFILL_HOURS,
    DEFAULT_BACKFILL_HOURS,
    DEFAULT_STARTUP_BACKFILL_HOURS,
    DOMAIN,
    MAX_BACKFILL_HOURS,
    SERVICE_BACKFILL_ENERGY,
    SERVICE_REBUILD_ECONOMICS,
)
from .coordinator import ElisaKotiakkuCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

BACKFILL_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): str,
        vol.Optional(ATTR_START_TIME): str,
        vol.Optional(ATTR_END_TIME): str,
        vol.Optional(
            ATTR_HOURS,
            default=DEFAULT_BACKFILL_HOURS,
        ): vol.All(int, vol.Range(min=1, max=MAX_BACKFILL_HOURS)),
    }
)

type ElisaKotiakkuConfigEntry = ConfigEntry[ElisaKotiakkuCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Elisa Kotiakku integration."""
    _async_register_backfill_service(hass)
    _async_register_rebuild_economics_service(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ElisaKotiakkuConfigEntry
) -> bool:
    """Set up Elisa Kotiakku from a config entry."""
    session = async_get_clientsession(hass)
    client = ElisaKotiakkuApiClient(
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    coordinator = ElisaKotiakkuCoordinator(hass, client, entry)
    await coordinator.async_load_energy_state()
    await coordinator.async_load_economics_state()
    await coordinator.async_load_analytics_state()
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_run_startup_backfill(entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ElisaKotiakkuConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_register_backfill_service(hass: HomeAssistant) -> None:
    """Register the backfill service once."""
    if hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY):
        return

    async def _async_handle_backfill(call: ServiceCall) -> None:
        """Backfill measurement-derived counters from historical API data."""
        start, end = _resolve_backfill_range(call.data)
        target_entry_id = call.data.get(ATTR_ENTRY_ID)

        entries = _loaded_entries(hass)
        if target_entry_id is not None:
            entries = [
                entry for entry in entries if entry.entry_id == target_entry_id
            ]
            if not entries:
                raise ServiceValidationError(
                    f"Entry '{target_entry_id}' is not loaded for {DOMAIN}",
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"entry_id": target_entry_id},
                )
        elif not entries:
            raise ServiceValidationError(
                "No loaded Elisa Kotiakku config entries found",
                translation_domain=DOMAIN,
                translation_key="no_loaded_entries",
            )

        start_iso = start.isoformat()
        end_iso = end.isoformat()

        total_processed = 0
        for entry in entries:
            coordinator = entry.runtime_data
            try:
                processed = await coordinator.async_backfill_energy(
                    start_time=start_iso,
                    end_time=end_iso,
                )
            except ConfigEntryAuthFailed as err:
                raise ServiceValidationError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="backfill_failed",
                    translation_placeholders={"reason": str(err)},
                ) from err
            except UpdateFailed as err:
                raise ServiceValidationError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="backfill_failed",
                    translation_placeholders={"reason": str(err)},
                ) from err

            _LOGGER.info(
                "Backfilled %s window(s) for entry %s (%s -> %s)",
                processed,
                entry.entry_id,
                start_iso,
                end_iso,
            )
            total_processed += processed

        if total_processed == 0:
            raise ServiceValidationError(
                "No new measurement windows were backfilled. "
                "The requested range may already be imported.",
                translation_domain=DOMAIN,
                translation_key="no_new_windows_backfilled",
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKFILL_ENERGY,
        _async_handle_backfill,
        schema=BACKFILL_SERVICE_SCHEMA,
    )


def _async_register_rebuild_economics_service(hass: HomeAssistant) -> None:
    """Register the economics rebuild service once."""
    if hass.services.has_service(DOMAIN, SERVICE_REBUILD_ECONOMICS):
        return

    async def _async_handle_rebuild(call: ServiceCall) -> None:
        """Rebuild economics and analytics counters from historical API data."""
        start, end = _resolve_backfill_range(call.data)
        target_entry_id = call.data.get(ATTR_ENTRY_ID)

        entries = _loaded_entries(hass)
        if target_entry_id is not None:
            entries = [
                entry for entry in entries if entry.entry_id == target_entry_id
            ]
            if not entries:
                raise ServiceValidationError(
                    f"Entry '{target_entry_id}' is not loaded for {DOMAIN}",
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"entry_id": target_entry_id},
                )
        elif not entries:
            raise ServiceValidationError(
                "No loaded Elisa Kotiakku config entries found",
                translation_domain=DOMAIN,
                translation_key="no_loaded_entries",
            )

        start_iso = start.isoformat()
        end_iso = end.isoformat()

        total_processed = 0
        for entry in entries:
            coordinator = entry.runtime_data
            try:
                processed = await coordinator.async_rebuild_economics(
                    start_time=start_iso,
                    end_time=end_iso,
                )
            except ConfigEntryAuthFailed as err:
                raise ServiceValidationError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="backfill_failed",
                    translation_placeholders={"reason": str(err)},
                ) from err
            except UpdateFailed as err:
                raise ServiceValidationError(
                    str(err),
                    translation_domain=DOMAIN,
                    translation_key="backfill_failed",
                    translation_placeholders={"reason": str(err)},
                ) from err

            _LOGGER.info(
                "Rebuilt economics and analytics from %s window(s) "
                "for entry %s (%s -> %s)",
                processed,
                entry.entry_id,
                start_iso,
                end_iso,
            )
            total_processed += processed

        if total_processed == 0:
            raise ServiceValidationError(
                "No new measurement windows were backfilled. "
                "The requested range may already be imported.",
                translation_domain=DOMAIN,
                translation_key="no_new_windows_backfilled",
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REBUILD_ECONOMICS,
        _async_handle_rebuild,
        schema=BACKFILL_SERVICE_SCHEMA,
    )


async def _async_update_listener(
    hass: HomeAssistant,
    entry: ElisaKotiakkuConfigEntry,
) -> None:
    """Reload integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_run_startup_backfill(entry: ElisaKotiakkuConfigEntry) -> None:
    """Optionally run a startup historical backfill for measurement-derived data."""
    backfill_hours = int(
        entry.options.get(
            CONF_STARTUP_BACKFILL_HOURS,
            DEFAULT_STARTUP_BACKFILL_HOURS,
        )
    )
    if backfill_hours <= 0:
        return

    end = dt_util.now()
    start = end - timedelta(hours=backfill_hours)

    coordinator = entry.runtime_data
    try:
        processed = await coordinator.async_backfill_energy(
            start_time=start.isoformat(),
            end_time=end.isoformat(),
        )
    except (ConfigEntryAuthFailed, UpdateFailed) as err:
        _LOGGER.warning(
            "Startup backfill failed for entry %s: %s",
            entry.entry_id,
            err,
        )
        return

    _LOGGER.info(
        "Startup backfill processed %s window(s) for entry %s (%s hours)",
        processed,
        entry.entry_id,
        backfill_hours,
    )


def _resolve_backfill_range(data: dict[str, Any]) -> tuple[datetime, datetime]:
    """Resolve start/end datetimes from service payload."""
    now = dt_util.now()
    end_raw = data.get(ATTR_END_TIME)
    start_raw = data.get(ATTR_START_TIME)
    hours = data[ATTR_HOURS]

    end = now if end_raw is None else dt_util.parse_datetime(end_raw)
    if end is None:
        raise ServiceValidationError(
            f"Invalid '{ATTR_END_TIME}' value",
            translation_domain=DOMAIN,
            translation_key="invalid_end_time",
        )
    end = _ensure_timezone(end)

    if start_raw is not None:
        start = dt_util.parse_datetime(start_raw)
        if start is None:
            raise ServiceValidationError(
                f"Invalid '{ATTR_START_TIME}' value",
                translation_domain=DOMAIN,
                translation_key="invalid_start_time",
            )
        start = _ensure_timezone(start)
    else:
        start = end - timedelta(hours=hours)

    if start >= end:
        raise ServiceValidationError(
            f"'{ATTR_START_TIME}' must be earlier than '{ATTR_END_TIME}'",
            translation_domain=DOMAIN,
            translation_key="start_must_be_before_end",
        )

    return start, end


def _has_loaded_entries(hass: HomeAssistant) -> bool:
    """Return True if at least one config entry is loaded."""
    return bool(_loaded_entries(hass))


def _ensure_timezone(value: datetime) -> datetime:
    """Ensure datetime has timezone info for reliable ISO serialization."""
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=dt_util.UTC)


def _loaded_entries(hass: HomeAssistant) -> list[ElisaKotiakkuConfigEntry]:
    """Return loaded config entries for this integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    loaded: list[ElisaKotiakkuConfigEntry] = []
    for entry in entries:
        if entry.state is ConfigEntryState.LOADED and entry.runtime_data is not None:
            loaded.append(entry)
    return loaded
