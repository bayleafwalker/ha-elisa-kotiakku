"""Integration lifecycle tests for __init__.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.elisa_kotiakku import (
    _async_register_backfill_service,
    _async_register_rebuild_economics_service,
    _async_update_listener,
    _ensure_timezone,
    _loaded_entries,
    _resolve_backfill_range,
    async_setup,
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
    SERVICE_REBUILD_ECONOMICS,
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
    coordinator.async_load_economics_state = AsyncMock()
    coordinator.async_load_analytics_state = AsyncMock()
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
    coordinator.async_load_economics_state.assert_awaited_once()
    coordinator.async_load_analytics_state.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    coordinator.refresh_tariff_preset_issue.assert_called_once()
    coordinator.async_backfill_energy.assert_not_awaited()
    assert entry.runtime_data is coordinator
    mock_forward_setups.assert_awaited_once_with(
        entry, [Platform.BUTTON, Platform.SENSOR]
    )


async def test_async_setup_registers_services(hass) -> None:
    """async_setup must register both maintenance services."""
    result = await async_setup(hass, {})
    assert result is True
    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)
    assert hass.services.has_service(DOMAIN, SERVICE_REBUILD_ECONOMICS)


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
    coordinator.async_load_economics_state = AsyncMock()
    coordinator.async_load_analytics_state = AsyncMock()
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


async def test_async_unload_entry_unloads_platforms(hass) -> None:
    """Entry unload should delegate to async_unload_platforms and return its result."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, entry)

    assert result is True
    entry.runtime_data.clear_tariff_preset_issue.assert_called_once()
    mock_unload_platforms.assert_awaited_once_with(
        entry, [Platform.BUTTON, Platform.SENSOR]
    )


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


async def test_rebuild_economics_service_calls_coordinator(hass) -> None:
    """Economics rebuild service should call async_rebuild_economics."""
    coordinator = MagicMock()
    coordinator.async_rebuild_economics = AsyncMock(return_value=2)
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-id-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_rebuild_economics_service(hass)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REBUILD_ECONOMICS,
            {ATTR_HOURS: 2},
            blocking=True,
        )

    coordinator.async_rebuild_economics.assert_awaited_once()


async def test_register_services_is_idempotent(hass) -> None:
    """Re-registering services should keep a single handler per service."""
    _async_register_backfill_service(hass)
    _async_register_backfill_service(hass)
    _async_register_rebuild_economics_service(hass)
    _async_register_rebuild_economics_service(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)
    assert hass.services.has_service(DOMAIN, SERVICE_REBUILD_ECONOMICS)


async def test_rebuild_service_raises_when_no_entries(hass) -> None:
    """Rebuild service should fail clearly when there are no loaded entries."""
    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[],
    ):
        _async_register_rebuild_economics_service(hass)
        with pytest.raises(ServiceValidationError, match="No loaded"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_REBUILD_ECONOMICS,
                {},
                blocking=True,
            )


async def test_rebuild_service_raises_for_unknown_entry_id(hass) -> None:
    """Rebuild service should reject entry IDs that are not loaded."""
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "real-entry-id"
    loaded_entry.runtime_data = MagicMock()

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_rebuild_economics_service(hass)
        with pytest.raises(ServiceValidationError, match="not loaded"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_REBUILD_ECONOMICS,
                {ATTR_ENTRY_ID: "nonexistent-entry-id", ATTR_HOURS: 1},
                blocking=True,
            )


@pytest.mark.parametrize(
    ("side_effect", "expected_message"),
    [
        (ConfigEntryAuthFailed("Bad key"), "Bad key"),
        (UpdateFailed("Connection lost"), "Connection lost"),
    ],
)
async def test_rebuild_service_surfaces_coordinator_errors(
    hass,
    side_effect,
    expected_message,
) -> None:
    """Rebuild service should wrap coordinator failures as validation errors."""
    coordinator = MagicMock()
    coordinator.async_rebuild_economics = AsyncMock(side_effect=side_effect)
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_rebuild_economics_service(hass)
        with pytest.raises(ServiceValidationError, match=expected_message):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_REBUILD_ECONOMICS,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_rebuild_service_raises_when_no_new_windows(hass) -> None:
    """Rebuild service should raise when the requested history yields no windows."""
    coordinator = MagicMock()
    coordinator.async_rebuild_economics = AsyncMock(return_value=0)
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "entry-1"
    loaded_entry.runtime_data = coordinator

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_rebuild_economics_service(hass)
        with pytest.raises(ServiceValidationError, match="already be imported"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_REBUILD_ECONOMICS,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_when_no_entries(hass) -> None:
    """Service call should fail clearly when no loaded entries exist."""
    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(ServiceValidationError, match="No loaded"):
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
    with pytest.raises(ServiceValidationError, match=ATTR_START_TIME):
        _resolve_backfill_range(
            {
                ATTR_START_TIME: start_time,
                "end_time": start_time,
                ATTR_HOURS: 1,
            }
        )


def test_resolve_backfill_range_invalid_end_time_raises() -> None:
    """An unparseable end_time string must raise ServiceValidationError."""
    with pytest.raises(ServiceValidationError, match=ATTR_END_TIME):
        _resolve_backfill_range(
            {
                ATTR_END_TIME: "not-a-date",
                ATTR_HOURS: 1,
            }
        )


def test_resolve_backfill_range_invalid_start_time_raises() -> None:
    """An unparseable start_time string must raise ServiceValidationError."""
    end_time = datetime(2026, 3, 5, tzinfo=dt_util.UTC).isoformat()
    with pytest.raises(ServiceValidationError, match=ATTR_START_TIME):
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
    """Service call with an unknown entry_id must raise ServiceValidationError."""
    loaded_entry = MagicMock()
    loaded_entry.entry_id = "real-entry-id"
    loaded_entry.runtime_data = MagicMock()

    with patch(
        "custom_components.elisa_kotiakku._loaded_entries",
        return_value=[loaded_entry],
    ):
        _async_register_backfill_service(hass)
        with pytest.raises(ServiceValidationError, match="not loaded"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_ENTRY_ID: "nonexistent-entry-id", ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_on_auth_failure(hass) -> None:
    """Auth failures from the coordinator must surface as ServiceValidationError."""
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
        with pytest.raises(ServiceValidationError, match="Bad key"):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_BACKFILL_ENERGY,
                {ATTR_HOURS: 1},
                blocking=True,
            )


async def test_backfill_service_raises_on_api_error(hass) -> None:
    """UpdateFailed from the coordinator must surface as ServiceValidationError."""
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
        with pytest.raises(ServiceValidationError, match="Connection lost"):
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
        with pytest.raises(ServiceValidationError, match="already be imported"):
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
    coordinator.async_load_economics_state = AsyncMock()
    coordinator.async_load_analytics_state = AsyncMock()
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
    """Service stays present when unloading one of multiple integration entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    entry.add_to_hass(hass)

    await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, SERVICE_BACKFILL_ENERGY)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
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


def test_loaded_entries_filters_by_state_and_runtime_data() -> None:
    """Only loaded entries with coordinator runtime data should be returned."""
    hass = MagicMock()
    good_entry = MagicMock()
    good_entry.state = ConfigEntryState.LOADED
    good_entry.runtime_data = MagicMock()
    pending_entry = MagicMock()
    pending_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
    pending_entry.runtime_data = MagicMock()
    no_runtime_entry = MagicMock()
    no_runtime_entry.state = ConfigEntryState.LOADED
    no_runtime_entry.runtime_data = None
    hass.config_entries.async_entries.return_value = [
        good_entry,
        pending_entry,
        no_runtime_entry,
    ]

    assert _loaded_entries(hass) == [good_entry]


def test_loaded_entries_can_be_used_as_presence_check() -> None:
    """Loaded entries list naturally supports bool-style presence checks."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    assert bool(_loaded_entries(hass)) is False

    loaded_entry = MagicMock()
    loaded_entry.state = ConfigEntryState.LOADED
    loaded_entry.runtime_data = MagicMock()
    hass.config_entries.async_entries.return_value = [loaded_entry]
    assert bool(_loaded_entries(hass)) is True
