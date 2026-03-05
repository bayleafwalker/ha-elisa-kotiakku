"""Integration lifecycle tests for __init__.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.elisa_kotiakku import (
    _async_register_backfill_service,
    _async_update_listener,
    _ensure_timezone,
    _resolve_backfill_range,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.elisa_kotiakku.const import (
    ATTR_END_TIME,
    ATTR_ENTRY_ID,
    ATTR_HOURS,
    ATTR_START_TIME,
    CONF_API_KEY,
    CONF_STARTUP_BACKFILL_HOURS,
    DOMAIN,
    SERVICE_BACKFILL_ENERGY,
)

MockConfigEntry = pytest.importorskip(
    "pytest_homeassistant_custom_component.common"
).MockConfigEntry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_async_setup_entry_sets_runtime_data_and_forwards_platforms(
    hass,
) -> None:
    """Entry setup should create coordinator, restore state and forward platforms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.async_load_energy_state = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_backfill_energy = AsyncMock(return_value=0)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as mock_forward_setups,
        patch(
            "custom_components.elisa_kotiakku.async_get_clientsession",
            return_value=MagicMock(),
        ) as mock_get_session,
        patch(
            "custom_components.elisa_kotiakku.ElisaKotiakkuApiClient"
        ) as mock_api_client_cls,
        patch(
            "custom_components.elisa_kotiakku.ElisaKotiakkuCoordinator",
            return_value=coordinator,
        ) as mock_coordinator_cls,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    mock_get_session.assert_called_once_with(hass)
    mock_api_client_cls.assert_called_once()
    mock_coordinator_cls.assert_called_once_with(
        hass,
        mock_api_client_cls.return_value,
        entry,
    )
    coordinator.async_load_energy_state.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.async_backfill_energy.assert_not_awaited()
    assert entry.runtime_data is coordinator
    mock_forward_setups.assert_awaited_once_with(entry, [Platform.SENSOR])
    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)


async def test_async_setup_entry_runs_startup_backfill_when_configured(hass) -> None:
    """Startup backfill option should trigger async_backfill_energy call."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        options={CONF_STARTUP_BACKFILL_HOURS: 6},
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.async_load_energy_state = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_backfill_energy = AsyncMock(return_value=3)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.elisa_kotiakku.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.elisa_kotiakku.ElisaKotiakkuApiClient"
        ),
        patch(
            "custom_components.elisa_kotiakku.ElisaKotiakkuCoordinator",
            return_value=coordinator,
        ),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    coordinator.async_backfill_energy.assert_awaited_once()


async def test_async_unload_entry_unloads_platforms_and_removes_service(hass) -> None:
    """Entry unload should remove service when no entries remain loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    entry.add_to_hass(hass)

    _async_register_backfill_service(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)

    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ) as mock_unload_platforms,
        patch(
            "custom_components.elisa_kotiakku._has_loaded_entries",
            return_value=False,
        ),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    mock_unload_platforms.assert_awaited_once_with(entry, [Platform.SENSOR])
    assert not hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)


async def test_backfill_service_calls_coordinator(hass) -> None:
    """Backfill service should call async_backfill_energy on loaded entries."""
    coordinator = MagicMock()
    coordinator.async_backfill_energy = AsyncMock(return_value=2)
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-id-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_BACKFILL_ENERGY,
            {ATTR_HOURS: 2},
            blocking=True,
        )

    coordinator.async_backfill_energy.assert_awaited_once()


async def test_backfill_service_raises_when_no_entries(hass) -> None:
    """Service call should fail clearly when no loaded entries exist."""
    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(HomeAssistantError, match="No loaded"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {},
                blocking=True,
            )


def test_resolve_backfill_range_defaults_hours() -> None:
    """Without explicit start, hours should determine the start timestamp."""
    start, end = _resolve_backfill_range({ATTR_HOURS: 3})
    assert (end - start) == timedelta(hours=3)


def test_resolve_backfill_range_rejects_invalid_order() -> None:
    """Start time must be earlier than end time."""
    start_time = datetime(2026, 3, 4, tzinfo=dt_util.UTC).isoformat()
    with pytest.raises(HomeAssistantError, match=ATTR_START_TIME):
        _resolve_backfill_range(
            {
                ATTR_START_TIME: start_time,
                "end_time": start_time,
                ATTR_HOURS: 1,
            }
        )


def test_resolve_backfill_range_invalid_end_time_raises() -> None:
    """An unparseable end_time string must raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError, match=ATTR_END_TIME):
        _resolve_backfill_range(
            {
                ATTR_END_TIME: "not-a-date",
                ATTR_HOURS: 1,
            }
        )


def test_resolve_backfill_range_invalid_start_time_raises() -> None:
    """An unparseable start_time string must raise HomeAssistantError."""
    end_time = datetime(2026, 3, 5, tzinfo=dt_util.UTC).isoformat()
    with pytest.raises(HomeAssistantError, match=ATTR_START_TIME):
        _resolve_backfill_range(
            {
                ATTR_START_TIME: "not-a-date",
                ATTR_END_TIME: end_time,
                ATTR_HOURS: 1,
            }
        )


def test_resolve_backfill_range_with_explicit_end_time() -> None:
    """Providing an explicit end_time should apply proper timezone handling."""
    start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=dt_util.UTC).isoformat()
    end_time = datetime(2026, 3, 5, 8, 0, 0, tzinfo=dt_util.UTC).isoformat()
    start, end = _resolve_backfill_range(
        {
            ATTR_START_TIME: start_time,
            ATTR_END_TIME: end_time,
            ATTR_HOURS: 1,
        }
    )
    assert (end - start).total_seconds() == 2 * 3600


def test_ensure_timezone_leaves_aware_datetime_unchanged() -> None:
    """An already timezone-aware datetime must be returned as-is."""
    dt = datetime(2026, 3, 5, 12, 0, 0, tzinfo=dt_util.UTC)
    result = _ensure_timezone(dt)
    assert result is dt


def test_ensure_timezone_adds_utc_to_naive_datetime() -> None:
    """A naive datetime must receive UTC as its timezone."""
    naive = datetime(2026, 3, 5, 12, 0, 0)
    result = _ensure_timezone(naive)
    assert result.tzinfo is dt_util.UTC
    assert result.year == 2026


async def test_backfill_service_raises_for_unknown_entry_id(hass) -> None:
    """Service call with an unknown entry_id must raise HomeAssistantError."""
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "real-entry-id"
    loaded_entry.runtime_data = MagicMock()

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(HomeAssistantError, match="not loaded"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_ENTRY_ID: "nonexistent-entry-id", ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_on_auth_failure(hass) -> None:
    """ConfigEntryAuthFailed from the coordinator must surface as HomeAssistantError."""
    coordinator = MagicMock()
    coordinator.async_backfill_energy = AsyncMock(
        side_effect=ConfigEntryAuthFailed("Bad key")
    )
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(HomeAssistantError, match="Bad key"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_on_api_error(hass) -> None:
    """UpdateFailed from the coordinator must surface as HomeAssistantError."""
    coordinator = MagicMock()
    coordinator.async_backfill_energy = AsyncMock(
        side_effect=UpdateFailed("Connection lost")
    )
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(HomeAssistantError, match="Connection lost"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_when_no_new_windows(hass) -> None:
    """Service must raise when all requested periods are already processed."""
    coordinator = MagicMock()
    coordinator.async_backfill_energy = AsyncMock(return_value=0)
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(HomeAssistantError, match="already be imported"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_startup_backfill_fails_gracefully_on_error(hass) -> None:
    """UpdateFailed during startup backfill must not prevent successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        options={CONF_STARTUP_BACKFILL_HOURS: 6},
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.async_load_energy_state = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_backfill_energy = AsyncMock(
        side_effect=UpdateFailed("Timeout")
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.elisa_kotiakku.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.elisa_kotiakku.ElisaKotiakkuApiClient"),
        patch(
            "custom_components.elisa_kotiakku.ElisaKotiakkuCoordinator",
            return_value=coordinator,
        ),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True


async def test_async_unload_keeps_service_when_other_entries_remain(hass) -> None:
    """Service must not be removed when at least one entry is still loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    entry.add_to_hass(hass)

    _async_register_backfill_service(hass)

    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.elisa_kotiakku._has_loaded_entries",
            return_value=True,
        ),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)


async def test_async_update_listener_triggers_reload(hass) -> None:
    """Options update listener must reload the config entry."""
    entry = MagicMock()
    entry.entry_id = "test-entry-id"

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock()
    ) as mock_reload:
        await _async_update_listener(hass, entry)

    mock_reload.assert_awaited_once_with("test-entry-id")
