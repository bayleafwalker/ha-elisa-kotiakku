"""Tests for the Elisa Kotiakku config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elisa_kotiakku.api import (
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
)
from custom_components.elisa_kotiakku.config_flow import ElisaKotiakkuConfigFlow
from custom_components.elisa_kotiakku.const import CONF_API_KEY, DOMAIN


@pytest.fixture
def flow() -> ElisaKotiakkuConfigFlow:
    """Return a config flow instance with mocked HA internals."""
    f = ElisaKotiakkuConfigFlow()
    f.hass = MagicMock()
    f.async_set_unique_id = AsyncMock()
    f._abort_if_unique_id_configured = MagicMock()
    f.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    f.async_show_form = MagicMock(return_value={"type": "form"})
    return f


@pytest.fixture
def reauth_flow() -> ElisaKotiakkuConfigFlow:
    """Return a config flow instance pre-configured for reauth testing."""
    f = ElisaKotiakkuConfigFlow()
    f.hass = MagicMock()
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_update_reload_and_abort = MagicMock(return_value={"type": "abort"})
    # Mock the reauth entry
    mock_entry = MagicMock()
    mock_entry.data = {CONF_API_KEY: "old-key"}
    f._get_reauth_entry = MagicMock(return_value=mock_entry)
    return f


class TestUserStep:
    """Tests for the user config step."""

    async def test_shows_form_without_input(self, flow: ElisaKotiakkuConfigFlow) -> None:
        """Without user_input, the form is shown."""
        result = await flow.async_step_user(user_input=None)

        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args
        assert call_kwargs.kwargs["step_id"] == "user"
        assert call_kwargs.kwargs["errors"] == {}

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_creates_entry_on_valid_key(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        flow: ElisaKotiakkuConfigFlow,
        api_key: str,
    ) -> None:
        """Valid API key creates a config entry."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.return_value = True
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={CONF_API_KEY: api_key}
        )

        mock_client.async_validate_key.assert_awaited_once()
        flow.async_create_entry.assert_called_once_with(
            title="Elisa Kotiakku",
            data={CONF_API_KEY: api_key},
        )

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_shows_error_on_invalid_auth(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        flow: ElisaKotiakkuConfigFlow,
        api_key: str,
    ) -> None:
        """Invalid API key shows auth error."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.side_effect = ElisaKotiakkuAuthError(
            "Auth failed"
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={CONF_API_KEY: api_key}
        )

        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()
        errors = flow.async_show_form.call_args.kwargs["errors"]
        assert errors["base"] == "invalid_auth"

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_shows_error_on_connection_failure(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        flow: ElisaKotiakkuConfigFlow,
        api_key: str,
    ) -> None:
        """Connection error shows cannot_connect error."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.side_effect = ElisaKotiakkuApiError(
            "Connection failed"
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={CONF_API_KEY: api_key}
        )

        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()
        errors = flow.async_show_form.call_args.kwargs["errors"]
        assert errors["base"] == "cannot_connect"

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_sets_unique_id_and_checks_duplicates(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        flow: ElisaKotiakkuConfigFlow,
        api_key: str,
    ) -> None:
        """Config flow sets unique_id from API key and checks for duplicates."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.return_value = True
        mock_client_cls.return_value = mock_client

        await flow.async_step_user(user_input={CONF_API_KEY: api_key})

        flow.async_set_unique_id.assert_awaited_once_with(api_key)
        flow._abort_if_unique_id_configured.assert_called_once()


# ---------------------------------------------------------------------------
# Reauthentication flow
# ---------------------------------------------------------------------------


class TestReauthFlow:
    """Tests for the reauthentication config flow."""

    async def test_reauth_delegates_to_confirm(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """async_step_reauth delegates to async_step_reauth_confirm."""
        result = await reauth_flow.async_step_reauth(
            entry_data={CONF_API_KEY: "old-key"}
        )

        reauth_flow.async_show_form.assert_called_once()
        call_kwargs = reauth_flow.async_show_form.call_args.kwargs
        assert call_kwargs["step_id"] == "reauth_confirm"
        assert call_kwargs["errors"] == {}

    async def test_reauth_confirm_shows_form_without_input(
        self, reauth_flow: ElisaKotiakkuConfigFlow
    ) -> None:
        """Without user_input, the reauth form is shown."""
        result = await reauth_flow.async_step_reauth_confirm(user_input=None)

        reauth_flow.async_show_form.assert_called_once()
        call_kwargs = reauth_flow.async_show_form.call_args.kwargs
        assert call_kwargs["step_id"] == "reauth_confirm"
        assert call_kwargs["errors"] == {}

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_reauth_confirm_updates_entry_on_valid_key(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        reauth_flow: ElisaKotiakkuConfigFlow,
    ) -> None:
        """Valid new API key updates config entry and reloads."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.return_value = True
        mock_client_cls.return_value = mock_client

        new_key = "new-api-key-67890"
        result = await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: new_key}
        )

        mock_client.async_validate_key.assert_awaited_once()
        reauth_flow.async_update_reload_and_abort.assert_called_once()
        call_kwargs = reauth_flow.async_update_reload_and_abort.call_args
        assert call_kwargs.kwargs["data_updates"] == {CONF_API_KEY: new_key}

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_reauth_confirm_shows_error_on_invalid_auth(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        reauth_flow: ElisaKotiakkuConfigFlow,
    ) -> None:
        """Invalid API key shows auth error on reauth form."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.side_effect = ElisaKotiakkuAuthError(
            "Auth failed"
        )
        mock_client_cls.return_value = mock_client

        result = await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "bad-key"}
        )

        reauth_flow.async_update_reload_and_abort.assert_not_called()
        reauth_flow.async_show_form.assert_called_once()
        errors = reauth_flow.async_show_form.call_args.kwargs["errors"]
        assert errors["base"] == "invalid_auth"

    @patch(
        "custom_components.elisa_kotiakku.config_flow.async_get_clientsession"
    )
    @patch(
        "custom_components.elisa_kotiakku.config_flow.ElisaKotiakkuApiClient"
    )
    async def test_reauth_confirm_shows_error_on_connection_failure(
        self,
        mock_client_cls: MagicMock,
        mock_get_session: MagicMock,
        reauth_flow: ElisaKotiakkuConfigFlow,
    ) -> None:
        """Connection error shows cannot_connect error on reauth form."""
        mock_client = AsyncMock()
        mock_client.async_validate_key.side_effect = ElisaKotiakkuApiError(
            "Connection failed"
        )
        mock_client_cls.return_value = mock_client

        result = await reauth_flow.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "some-key"}
        )

        reauth_flow.async_update_reload_and_abort.assert_not_called()
        reauth_flow.async_show_form.assert_called_once()
        errors = reauth_flow.async_show_form.call_args.kwargs["errors"]
        assert errors["base"] == "cannot_connect"
