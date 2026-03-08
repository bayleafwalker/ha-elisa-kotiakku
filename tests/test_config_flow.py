"""Tests for the Elisa Kotiakku config flow."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
)
from custom_components.elisa_kotiakku.config_flow import (
    ElisaKotiakkuConfigFlow,
    ElisaKotiakkuOptionsFlow,
    _unique_id_from_api_key,
)
from custom_components.elisa_kotiakku.const import (
    CONF_API_KEY,
    CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
    CONF_DAY_IMPORT_RETAILER_MARGIN,
    CONF_ELECTRICITY_TAX_FEE,
    CONF_EXPORT_RETAILER_ADJUSTMENT,
    CONF_GRID_EXPORT_TRANSFER_FEE,
    CONF_GRID_IMPORT_TRANSFER_FEE,
    CONF_IMPORT_RETAILER_MARGIN,
    CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    CONF_NIGHT_IMPORT_RETAILER_MARGIN,
    CONF_POWER_FEE_RATE,
    CONF_POWER_FEE_RULE,
    CONF_STARTUP_BACKFILL_HOURS,
    CONF_TARIFF_MODE,
    CONF_TARIFF_PRESET,
    DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH,
    DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_DAY_IMPORT_RETAILER_MARGIN,
    DEFAULT_ELECTRICITY_TAX_FEE,
    DEFAULT_EXPORT_RETAILER_ADJUSTMENT,
    DEFAULT_GRID_EXPORT_TRANSFER_FEE,
    DEFAULT_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_IMPORT_RETAILER_MARGIN,
    DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN,
    DEFAULT_POWER_FEE_RATE,
    DEFAULT_POWER_FEE_RULE,
    DEFAULT_STARTUP_BACKFILL_HOURS,
    DEFAULT_TARIFF_MODE,
    DEFAULT_TARIFF_PRESET,
    MAX_BACKFILL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
    TARIFF_MODE_DAY_NIGHT,
    TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
)


@pytest.fixture
def flow() -> ElisaKotiakkuConfigFlow:
    """Return a config flow instance with mocked HA internals."""
    f = ElisaKotiakkuConfigFlow()
    f.hass = MagicMock()
    f.hass.config_entries = MagicMock()
    f.hass.config_entries.async_update_entry = MagicMock()
    f.async_set_unique_id = AsyncMock()
    f._abort_if_unique_id_configured = MagicMock()
    f.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_abort = MagicMock(return_value={"type": "abort"})
    f._async_current_entries = MagicMock(return_value=[])
    return f


@pytest.fixture
def reauth_flow() -> ElisaKotiakkuConfigFlow:
    """Return a config flow instance pre-configured for reauth testing."""
    f = ElisaKotiakkuConfigFlow()
    f.hass = MagicMock()
    f.hass.config_entries = MagicMock()
    f.hass.config_entries.async_update_entry = MagicMock()
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_abort = MagicMock(return_value={"type": "abort"})
    f.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    reauth_entry = MagicMock()
    reauth_entry.entry_id = "reauth-entry-id"
    reauth_entry.unique_id = _unique_id_from_api_key("old-key")
    reauth_entry.data = {CONF_API_KEY: "old-key"}

    f._get_reauth_entry = MagicMock(return_value=reauth_entry)
    f._async_current_entries = MagicMock(return_value=[reauth_entry])
    return f


@pytest.fixture
def reconfigure_flow() -> ElisaKotiakkuConfigFlow:
    """Return a config flow instance pre-configured for reconfigure tests."""
    f = ElisaKotiakkuConfigFlow()
    f.hass = MagicMock()
    f.hass.config_entries = MagicMock()
    f.hass.config_entries.async_update_entry = MagicMock()
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_abort = MagicMock(return_value={"type": "abort"})
    f.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})

    reconfigure_entry = MagicMock()
    reconfigure_entry.entry_id = "reconfigure-entry-id"
    reconfigure_entry.unique_id = _unique_id_from_api_key("old-key")
    reconfigure_entry.data = {CONF_API_KEY: "old-key"}

    f._get_reconfigure_entry = MagicMock(return_value=reconfigure_entry)
    f._async_current_entries = MagicMock(return_value=[reconfigure_entry])
    return f


def _expected_default_options() -> dict[str, float | int | str]:
    """Return expected normalized default options."""
    return {
        CONF_STARTUP_BACKFILL_HOURS: DEFAULT_STARTUP_BACKFILL_HOURS,
        CONF_TARIFF_PRESET: DEFAULT_TARIFF_PRESET,
        CONF_TARIFF_MODE: DEFAULT_TARIFF_MODE,
        CONF_IMPORT_RETAILER_MARGIN: DEFAULT_IMPORT_RETAILER_MARGIN,
        CONF_EXPORT_RETAILER_ADJUSTMENT: DEFAULT_EXPORT_RETAILER_ADJUSTMENT,
        CONF_GRID_IMPORT_TRANSFER_FEE: DEFAULT_GRID_IMPORT_TRANSFER_FEE,
        CONF_GRID_EXPORT_TRANSFER_FEE: DEFAULT_GRID_EXPORT_TRANSFER_FEE,
        CONF_ELECTRICITY_TAX_FEE: DEFAULT_ELECTRICITY_TAX_FEE,
        CONF_DAY_IMPORT_RETAILER_MARGIN: DEFAULT_DAY_IMPORT_RETAILER_MARGIN,
        CONF_NIGHT_IMPORT_RETAILER_MARGIN: DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN,
        CONF_DAY_GRID_IMPORT_TRANSFER_FEE: (
            DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE
        ),
        CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: (
            DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE
        ),
        CONF_POWER_FEE_RULE: DEFAULT_POWER_FEE_RULE,
        CONF_POWER_FEE_RATE: DEFAULT_POWER_FEE_RATE,
        CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: (
            DEFAULT_BATTERY_EXPECTED_USABLE_CAPACITY_KWH
        ),
    }


class TestUniqueIdDerivation:
    """Tests for unique ID derivation from API keys."""

    def test_unique_id_hash_is_stable(self) -> None:
        """Same key should always produce the same unique ID."""
        key = "test-key"
        assert _unique_id_from_api_key(key) == _unique_id_from_api_key(key)

    def test_unique_id_hash_does_not_contain_plaintext_key(self) -> None:
        """Unique ID should not expose the raw API key value."""
        key = "super-secret-key"
        unique_id = _unique_id_from_api_key(key)
        assert key not in unique_id
        assert unique_id.startswith("api_key_")

    def test_fingerprint_has_expected_prefix(self) -> None:
        """Derived fingerprint should preserve the expected prefix."""
        key = "super-secret-key"
        assert _unique_id_from_api_key(key).startswith("api_key_")

    def test_fingerprint_has_16_hex_char_suffix(self) -> None:
        """Derived fingerprint suffix should be lowercase hexadecimal."""
        unique_id = _unique_id_from_api_key("super-secret-key")
        suffix = unique_id.removeprefix("api_key_")
        assert len(suffix) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", suffix) is not None


class TestValidationHelper:
    """Tests for shared API-key validation helper."""

    @patch("custom_components.elisa_kotiakku.config_flow.async_get_clientsession")
    @patch("custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient")
    async def test_validate_helper_calls_client(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        flow: ElisaKotiakkuConfigFlow,
    ) -> None:
        """Validation helper should create client and await validation."""
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client

        await flow._async_validate_api_key("test-key")

        mock_get_session.assert_called_once_with(flow.hass)
        mock_client_cls.assert_called_once()
        mock_client.async_validate_key.assert_awaited_once()


class TestUserStep:
    """Tests for the initial user config step."""

    async def test_shows_form_without_input(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Without user_input, the form is shown."""
        await flow.async_step_user(user_input=None)

        flow.async_show_form.assert_called_once()
        kwargs = flow.async_show_form.call_args.kwargs
        assert kwargs["step_id"] == "user"
        assert kwargs["errors"] == {}

    async def test_creates_entry_on_valid_key(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Valid API key creates a config entry."""
        flow._async_validate_api_key = AsyncMock(return_value=None)

        await flow.async_step_user(user_input={CONF_API_KEY: "  key-123  "})

        flow.async_set_unique_id.assert_awaited_once_with(
            _unique_id_from_api_key("key-123")
        )
        flow._abort_if_unique_id_configured.assert_called_once()
        flow.async_create_entry.assert_called_once_with(
            title="Elisa Kotiakku",
            data={CONF_API_KEY: "key-123"},
        )

    async def test_aborts_if_api_key_already_exists(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """New setup should detect entries with the same configured API key."""
        existing_entry = MagicMock()
        existing_entry.data = {CONF_API_KEY: "same-key"}
        flow._async_current_entries.return_value = [existing_entry]

        await flow.async_step_user(user_input={CONF_API_KEY: "same-key"})

        flow.async_abort.assert_called_once_with(reason="already_configured")
        flow.async_set_unique_id.assert_not_awaited()
        flow._abort_if_unique_id_configured.assert_not_called()

    async def test_shows_invalid_auth_error(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Auth failures map to invalid_auth."""
        flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuAuthError("bad key")
        )

        await flow.async_step_user(user_input={CONF_API_KEY: "bad-key"})

        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args.kwargs["errors"]["base"] == "invalid_auth"

    async def test_shows_cannot_connect_on_api_error(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """API errors map to cannot_connect."""
        flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuApiError("network down")
        )

        await flow.async_step_user(user_input={CONF_API_KEY: "some-key"})

        flow.async_show_form.assert_called_once()
        assert (
            flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "cannot_connect"
        )


class TestReauthFlow:
    """Tests for the reauthentication config flow."""

    async def test_reauth_delegates_to_confirm(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """async_step_reauth delegates to async_step_reauth_confirm."""
        await reauth_flow.async_step_reauth(entry_data={CONF_API_KEY: "old-key"})

        reauth_flow.async_show_form.assert_called_once()
        kwargs = reauth_flow.async_show_form.call_args.kwargs
        assert kwargs["step_id"] == "reauth_confirm"
        assert kwargs["errors"] == {}

    async def test_reauth_confirm_updates_entry_on_valid_key(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Valid new API key updates unique_id + data and reloads."""
        reauth_flow._async_validate_api_key = AsyncMock(return_value=None)
        reauth_entry = reauth_flow._get_reauth_entry.return_value

        await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "new-key"}
        )

        reauth_flow.hass.config_entries.async_update_entry.assert_called_once_with(
            reauth_entry,
            unique_id=_unique_id_from_api_key("new-key"),
        )
        reauth_flow.async_update_reload_and_abort.assert_called_once_with(
            reauth_entry,
            data_updates={CONF_API_KEY: "new-key"},
        )

    async def test_reauth_shows_invalid_auth_error(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Auth failures in reauth should map to invalid_auth."""
        reauth_flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuAuthError("bad key")
        )

        await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "bad-key"}
        )

        reauth_flow.async_show_form.assert_called_once()
        assert (
            reauth_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "invalid_auth"
        )

    async def test_reauth_shows_cannot_connect_on_api_error(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """API errors in reauth should map to cannot_connect."""
        reauth_flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuApiError("network down")
        )

        await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "bad-key"}
        )

        reauth_flow.async_show_form.assert_called_once()
        assert (
            reauth_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "cannot_connect"
        )

    async def test_reauth_aborts_if_key_used_by_other_entry(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Reauth should abort if another entry already owns the key fingerprint."""
        reauth_flow._async_validate_api_key = AsyncMock(return_value=None)
        reauth_entry = reauth_flow._get_reauth_entry.return_value
        other_entry = MagicMock()
        other_entry.entry_id = "other-entry-id"
        other_entry.unique_id = "api_key_legacy_fingerprint"
        other_entry.data = {CONF_API_KEY: "duplicate-key"}
        reauth_flow._async_current_entries.return_value = [reauth_entry, other_entry]

        await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "duplicate-key"}
        )

        reauth_flow.async_abort.assert_called_once_with(reason="already_configured")
        reauth_flow.async_update_reload_and_abort.assert_not_called()

    async def test_reauth_aborts_if_unique_id_used_by_other_entry(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Reauth should also abort when only unique_id collides."""
        reauth_flow._async_validate_api_key = AsyncMock(return_value=None)
        reauth_entry = reauth_flow._get_reauth_entry.return_value
        other_entry = MagicMock()
        other_entry.entry_id = "other-entry-id"
        other_entry.unique_id = _unique_id_from_api_key("duplicate-key")
        other_entry.data = {CONF_API_KEY: "other-key"}
        reauth_flow._async_current_entries.return_value = [reauth_entry, other_entry]

        await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "duplicate-key"}
        )

        reauth_flow.async_abort.assert_called_once_with(reason="already_configured")
        reauth_flow.async_update_reload_and_abort.assert_not_called()


class TestReconfigureFlow:
    """Tests for reconfigure flow."""

    async def test_reconfigure_shows_form_without_input(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Without user input, the reconfigure form is shown."""
        await reconfigure_flow.async_step_reconfigure(user_input=None)

        reconfigure_flow.async_show_form.assert_called_once()
        kwargs = reconfigure_flow.async_show_form.call_args.kwargs
        assert kwargs["step_id"] == "reconfigure_confirm"
        assert kwargs["errors"] == {}

    async def test_reconfigure_updates_entry_on_valid_key(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Valid key should update entry data and unique ID."""
        reconfigure_flow._async_validate_api_key = AsyncMock(return_value=None)
        reconfigure_entry = reconfigure_flow._get_reconfigure_entry.return_value

        await reconfigure_flow.async_step_reconfigure(
            user_input={CONF_API_KEY: "updated-key"}
        )

        reconfigure_flow.hass.config_entries.async_update_entry.assert_called_once_with(
            reconfigure_entry,
            unique_id=_unique_id_from_api_key("updated-key"),
        )
        reconfigure_flow.async_update_reload_and_abort.assert_called_once_with(
            reconfigure_entry,
            data_updates={CONF_API_KEY: "updated-key"},
            reason="reconfigure_successful",
        )

    async def test_reconfigure_shows_invalid_auth_error(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Auth failures in reconfigure should map to invalid_auth."""
        reconfigure_flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuAuthError("bad key")
        )

        await reconfigure_flow.async_step_reconfigure(
            user_input={CONF_API_KEY: "bad-key"}
        )

        reconfigure_flow.async_show_form.assert_called_once()
        assert (
            reconfigure_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "invalid_auth"
        )

    async def test_reconfigure_shows_cannot_connect_on_api_error(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """API errors in reconfigure should map to cannot_connect."""
        reconfigure_flow._async_validate_api_key = AsyncMock(
            side_effect=ElisaKotiakkuApiError("network down")
        )

        await reconfigure_flow.async_step_reconfigure(
            user_input={CONF_API_KEY: "bad-key"}
        )

        reconfigure_flow.async_show_form.assert_called_once()
        assert (
            reconfigure_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "cannot_connect"
        )

    async def test_reconfigure_aborts_if_duplicate(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Reconfigure should abort when another entry owns the key fingerprint."""
        reconfigure_flow._async_validate_api_key = AsyncMock(return_value=None)
        reconfigure_entry = reconfigure_flow._get_reconfigure_entry.return_value
        other_entry = MagicMock()
        other_entry.entry_id = "other-entry-id"
        other_entry.unique_id = "api_key_legacy_fingerprint"
        other_entry.data = {CONF_API_KEY: "duplicate-key"}
        reconfigure_flow._async_current_entries.return_value = [
            reconfigure_entry,
            other_entry,
        ]

        await reconfigure_flow.async_step_reconfigure(
            user_input={CONF_API_KEY: "duplicate-key"}
        )

        reconfigure_flow.async_abort.assert_called_once_with(
            reason="already_configured"
        )
        reconfigure_flow.async_update_reload_and_abort.assert_not_called()

    async def test_reconfigure_aborts_if_unique_id_used_by_other_entry(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Reconfigure should also abort when only unique_id collides."""
        reconfigure_flow._async_validate_api_key = AsyncMock(return_value=None)
        reconfigure_entry = reconfigure_flow._get_reconfigure_entry.return_value
        other_entry = MagicMock()
        other_entry.entry_id = "other-entry-id"
        other_entry.unique_id = _unique_id_from_api_key("duplicate-key")
        other_entry.data = {CONF_API_KEY: "other-key"}
        reconfigure_flow._async_current_entries.return_value = [
            reconfigure_entry,
            other_entry,
        ]

        await reconfigure_flow.async_step_reconfigure(
            user_input={CONF_API_KEY: "duplicate-key"}
        )

        reconfigure_flow.async_abort.assert_called_once_with(
            reason="already_configured"
        )
        reconfigure_flow.async_update_reload_and_abort.assert_not_called()


class TestApiKeyMatchingHelpers:
    """Tests for internal API key matching helper logic."""

    def test_entry_has_api_key_false_when_missing(self) -> None:
        """Missing API key in entry data should not match."""
        entry = MagicMock()
        entry.data = {}

        assert (
            ElisaKotiakkuConfigFlow._entry_has_api_key(entry, "test-key")
            is False
        )

    def test_entry_has_api_key_false_when_non_string(self) -> None:
        """Non-string API key values should never match."""
        entry = MagicMock()
        entry.data = {CONF_API_KEY: 1234}

        assert (
            ElisaKotiakkuConfigFlow._entry_has_api_key(entry, "1234")
            is False
        )

    def test_entry_has_api_key_matches_when_stored_has_whitespace(self) -> None:
        """Stored API key should be trimmed before comparison."""
        entry = MagicMock()
        entry.data = {CONF_API_KEY: "  test-key  "}

        assert ElisaKotiakkuConfigFlow._entry_has_api_key(entry, "test-key") is True


class TestGenericExceptionHandling:
    """Tests for the catch-all exception branches in each flow step."""

    async def test_user_step_generic_exception_shows_cannot_connect(
        self, flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Unexpected user-step errors should map to cannot_connect."""
        with patch.object(
            flow,
            "_async_validate_api_key",
            side_effect=RuntimeError("unexpected server error"),
        ):
            await flow.async_step_user(user_input={"api_key": "some-key"})

        flow.async_show_form.assert_called_once()
        errors = flow.async_show_form.call_args.kwargs["errors"]
        assert errors == {"base": "cannot_connect"}

    async def test_reauth_step_generic_exception_shows_cannot_connect(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Unexpected reauth errors should map to cannot_connect."""
        with patch.object(
            reauth_flow,
            "_async_validate_api_key",
            side_effect=RuntimeError("unexpected server error"),
        ):
            await reauth_flow.async_step_reauth_confirm(
                user_input={"api_key": "new-key"}
            )

        reauth_flow.async_show_form.assert_called_once()
        errors = reauth_flow.async_show_form.call_args.kwargs["errors"]
        assert errors == {"base": "cannot_connect"}

    async def test_reconfigure_step_generic_exception_shows_cannot_connect(
        self, reconfigure_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Unexpected reconfigure errors should map to cannot_connect."""
        with patch.object(
            reconfigure_flow,
            "_async_validate_api_key",
            side_effect=RuntimeError("unexpected server error"),
        ):
            await reconfigure_flow.async_step_reconfigure(
                user_input={"api_key": "new-key"}
            )

        reconfigure_flow.async_show_form.assert_called_once()
        errors = reconfigure_flow.async_show_form.call_args.kwargs["errors"]
        assert errors == {"base": "cannot_connect"}


class TestOptionsFlow:
    """Tests for options flow."""

    def test_async_get_options_flow(self) -> None:
        """Config flow should expose options flow handler."""
        entry = MagicMock()
        options_flow = ElisaKotiakkuConfigFlow.async_get_options_flow(entry)
        assert isinstance(options_flow, ElisaKotiakkuOptionsFlow)

    async def test_options_show_form_with_current_value(self) -> None:
        """Options step should show current startup backfill value."""
        entry = MagicMock()
        entry.options = {
            CONF_STARTUP_BACKFILL_HOURS: 12,
            CONF_TARIFF_PRESET: DEFAULT_TARIFF_PRESET,
            CONF_TARIFF_MODE: TARIFF_MODE_DAY_NIGHT,
            CONF_IMPORT_RETAILER_MARGIN: 0.5,
            CONF_EXPORT_RETAILER_ADJUSTMENT: -0.2,
            CONF_GRID_IMPORT_TRANSFER_FEE: 4.1,
            CONF_GRID_EXPORT_TRANSFER_FEE: 0.0,
            CONF_ELECTRICITY_TAX_FEE: 2.79,
            CONF_DAY_IMPORT_RETAILER_MARGIN: 0.6,
            CONF_NIGHT_IMPORT_RETAILER_MARGIN: 0.4,
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 5.1,
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 3.1,
            CONF_POWER_FEE_RULE: POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
            CONF_POWER_FEE_RATE: 8.5,
            CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: 10.2,
        }
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(user_input=None)

        options_flow.async_show_form.assert_called_once()
        kwargs = options_flow.async_show_form.call_args.kwargs
        assert kwargs["step_id"] == "init"
        schema = kwargs["data_schema"]
        validated = schema(entry.options)
        assert validated[CONF_STARTUP_BACKFILL_HOURS] == 12
        assert validated[CONF_TARIFF_MODE] == TARIFF_MODE_DAY_NIGHT
        assert validated[CONF_POWER_FEE_RATE] == 8.5
        assert validated[CONF_ELECTRICITY_TAX_FEE] == 2.79
        assert validated[CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH] == 10.2

    async def test_options_show_form_uses_default_when_missing(self) -> None:
        """Options step should fallback to default when no options are set."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(user_input=None)

        kwargs = options_flow.async_show_form.call_args.kwargs
        schema = kwargs["data_schema"]
        assert schema({}) == _expected_default_options()

    async def test_options_create_entry_on_submit(self) -> None:
        """Submitting options should create options entry."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_create_entry = MagicMock(
            return_value={"type": "create_entry"}
        )

        result = await options_flow.async_step_init(
            user_input={
                CONF_STARTUP_BACKFILL_HOURS: 48,
                CONF_TARIFF_PRESET: DEFAULT_TARIFF_PRESET,
                CONF_TARIFF_MODE: TARIFF_MODE_DAY_NIGHT,
                CONF_IMPORT_RETAILER_MARGIN: 0.5,
                CONF_EXPORT_RETAILER_ADJUSTMENT: -0.2,
                CONF_GRID_IMPORT_TRANSFER_FEE: 4.1,
                CONF_GRID_EXPORT_TRANSFER_FEE: 0.0,
                CONF_ELECTRICITY_TAX_FEE: 2.79,
                CONF_DAY_IMPORT_RETAILER_MARGIN: 0.7,
                CONF_NIGHT_IMPORT_RETAILER_MARGIN: 0.3,
                CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 5.1,
                CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 2.9,
                CONF_POWER_FEE_RULE: POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
                CONF_POWER_FEE_RATE: 9.1,
                CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: 12.5,
            }
        )

        assert result["type"] == "create_entry"
        options_flow.async_create_entry.assert_called_once_with(
            title="",
            data={
                CONF_STARTUP_BACKFILL_HOURS: 48,
                CONF_TARIFF_PRESET: DEFAULT_TARIFF_PRESET,
                CONF_TARIFF_MODE: TARIFF_MODE_DAY_NIGHT,
                CONF_IMPORT_RETAILER_MARGIN: 0.5,
                CONF_EXPORT_RETAILER_ADJUSTMENT: -0.2,
                CONF_GRID_IMPORT_TRANSFER_FEE: 4.1,
                CONF_GRID_EXPORT_TRANSFER_FEE: 0.0,
                CONF_ELECTRICITY_TAX_FEE: 2.79,
                CONF_DAY_IMPORT_RETAILER_MARGIN: 0.7,
                CONF_NIGHT_IMPORT_RETAILER_MARGIN: 0.3,
                CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 5.1,
                CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 2.9,
                CONF_POWER_FEE_RULE: POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
                CONF_POWER_FEE_RATE: 9.1,
                CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: 12.5,
            },
        )

    async def test_options_schema_accepts_min_and_max_bounds(self) -> None:
        """Options schema should accept both boundary values."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(user_input=None)

        schema = options_flow.async_show_form.call_args.kwargs["data_schema"]
        assert schema({CONF_STARTUP_BACKFILL_HOURS: 0}) == {
            **_expected_default_options(),
            CONF_STARTUP_BACKFILL_HOURS: 0,
        }
        assert schema({CONF_STARTUP_BACKFILL_HOURS: MAX_BACKFILL_HOURS}) == {
            **_expected_default_options(),
            CONF_STARTUP_BACKFILL_HOURS: MAX_BACKFILL_HOURS,
        }

    async def test_options_schema_rejects_out_of_range_values(self) -> None:
        """Options schema should reject values outside allowed range."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(user_input=None)

        schema = options_flow.async_show_form.call_args.kwargs["data_schema"]
        with pytest.raises(vol.Invalid):
            schema({CONF_STARTUP_BACKFILL_HOURS: -1})
        with pytest.raises(vol.Invalid):
            schema({CONF_STARTUP_BACKFILL_HOURS: MAX_BACKFILL_HOURS + 1})

    async def test_options_rejects_negative_tariff_values(self) -> None:
        """Tariff values that must be non-negative should be rejected."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(
            user_input={
                **_expected_default_options(),
                CONF_GRID_IMPORT_TRANSFER_FEE: -1,
            }
        )

        options_flow.async_show_form.assert_called_once()
        assert (
            options_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "invalid_tariff_value"
        )

    async def test_options_rejects_negative_expected_capacity(self) -> None:
        """Configured expected capacity must be non-negative."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(
            user_input={
                **_expected_default_options(),
                CONF_BATTERY_EXPECTED_USABLE_CAPACITY_KWH: -0.1,
            }
        )

        options_flow.async_show_form.assert_called_once()
        assert (
            options_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "invalid_tariff_value"
        )

    async def test_options_rejects_negative_electricity_tax(self) -> None:
        """Configured electricity tax must be non-negative."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_show_form = MagicMock(return_value={"type": "form"})

        await options_flow.async_step_init(
            user_input={
                **_expected_default_options(),
                CONF_ELECTRICITY_TAX_FEE: -0.01,
            }
        )

        options_flow.async_show_form.assert_called_once()
        assert (
            options_flow.async_show_form.call_args.kwargs["errors"]["base"]
            == "invalid_tariff_value"
        )

    async def test_options_allows_negative_retailer_margin_and_export_adjustment(
        self,
    ) -> None:
        """Retailer discounts should remain allowed."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_create_entry = MagicMock(
            return_value={"type": "create_entry"}
        )

        result = await options_flow.async_step_init(
            user_input={
                **_expected_default_options(),
                CONF_IMPORT_RETAILER_MARGIN: -0.25,
                CONF_EXPORT_RETAILER_ADJUSTMENT: -0.5,
            }
        )

        assert result["type"] == "create_entry"
        saved = options_flow.async_create_entry.call_args.kwargs["data"]
        assert saved[CONF_IMPORT_RETAILER_MARGIN] == -0.25
        assert saved[CONF_EXPORT_RETAILER_ADJUSTMENT] == -0.5

    async def test_options_apply_tariff_preset_on_submit(self) -> None:
        """Selecting a preset should normalize transfer values on save."""
        entry = MagicMock()
        entry.options = {}
        options_flow = ElisaKotiakkuOptionsFlow(entry)
        options_flow.async_create_entry = MagicMock(
            return_value={"type": "create_entry"}
        )

        await options_flow.async_step_init(
            user_input={
                **_expected_default_options(),
                CONF_TARIFF_PRESET: TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
                CONF_TARIFF_MODE: "flat",
                CONF_GRID_IMPORT_TRANSFER_FEE: 99.0,
                CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 99.0,
                CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 99.0,
            }
        )

        options_flow.async_create_entry.assert_called_once()
        saved = options_flow.async_create_entry.call_args.kwargs["data"]
        assert saved[CONF_TARIFF_PRESET] == (
            TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01
        )
        assert saved[CONF_TARIFF_MODE] == TARIFF_MODE_DAY_NIGHT
        assert saved[CONF_DAY_GRID_IMPORT_TRANSFER_FEE] == 5.11
        assert saved[CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE] == 3.12
