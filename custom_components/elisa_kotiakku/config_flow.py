"""Config flow for Elisa Kotiakku integration."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
)
from .const import CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=1)),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=1)),
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): vol.All(str, vol.Length(min=1)),
    }
)


class ElisaKotiakkuConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Elisa Kotiakku."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — user enters their API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            # Prevent duplicate entries with the same key
            await self.async_set_unique_id(_unique_id_from_api_key(api_key))
            self._abort_if_unique_id_configured()

            try:
                await self._async_validate_api_key(api_key)
            except ElisaKotiakkuAuthError:
                errors["base"] = "invalid_auth"
            except ElisaKotiakkuApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during API validation")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Elisa Kotiakku",
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Reauthentication
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the API key becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new API key."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            unique_id = _unique_id_from_api_key(api_key)

            try:
                await self._async_validate_api_key(api_key)
            except ElisaKotiakkuAuthError:
                errors["base"] = "invalid_auth"
            except ElisaKotiakkuApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "cannot_connect"
            else:
                if self._unique_id_taken_by_other_entry(unique_id, reauth_entry):
                    return self.async_abort(reason="already_configured")

                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    unique_id=unique_id,
                )
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle integration reconfiguration from the UI."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            unique_id = _unique_id_from_api_key(api_key)

            try:
                await self._async_validate_api_key(api_key)
            except ElisaKotiakkuAuthError:
                errors["base"] = "invalid_auth"
            except ElisaKotiakkuApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfiguration")
                errors["base"] = "cannot_connect"
            else:
                if self._unique_id_taken_by_other_entry(
                    unique_id, reconfigure_entry
                ):
                    return self.async_abort(reason="already_configured")

                self.hass.config_entries.async_update_entry(
                    reconfigure_entry,
                    unique_id=unique_id,
                )
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_API_KEY: api_key},
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=STEP_RECONFIGURE_DATA_SCHEMA,
            errors=errors,
        )

    async def _async_validate_api_key(self, api_key: str) -> None:
        """Validate API key against the remote endpoint."""
        session = async_get_clientsession(self.hass)
        client = ElisaKotiakkuApiClient(api_key=api_key, session=session)
        await client.async_validate_key()

    def _unique_id_taken_by_other_entry(
        self,
        unique_id: str,
        current_entry: ConfigEntry[Any],
    ) -> bool:
        """Return True if unique ID already belongs to another config entry."""
        for entry in self._async_current_entries():
            if (
                entry.entry_id != current_entry.entry_id
                and entry.unique_id == unique_id
            ):
                return True
        return False


def _unique_id_from_api_key(api_key: str) -> str:
    """Generate a non-secret unique ID from the API key."""
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return f"api_key_{api_key_hash}"
