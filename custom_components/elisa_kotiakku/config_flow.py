"""Config flow for Elisa Kotiakku integration."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ElisaKotiakkuApiClient,
    ElisaKotiakkuApiError,
    ElisaKotiakkuAuthError,
)
from .const import (
    CONF_API_KEY,
    CONF_STARTUP_BACKFILL_HOURS,
    DEFAULT_STARTUP_BACKFILL_HOURS,
    DOMAIN,
    MAX_BACKFILL_HOURS,
)

_LOGGER = logging.getLogger(__name__)

_UNIQUE_ID_PREFIX = "api_key_"
_UNIQUE_ID_KDF_SALT = b"elisa_kotiakku_unique_id_v1"
_UNIQUE_ID_KDF_ITERATIONS = 120_000

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


def _options_data_schema(startup_backfill_hours: int) -> vol.Schema:
    """Return options form schema with current values as defaults."""
    return vol.Schema(
        {
            vol.Required(
                CONF_STARTUP_BACKFILL_HOURS,
                default=startup_backfill_hours,
            ): vol.All(int, vol.Range(min=0, max=MAX_BACKFILL_HOURS)),
        }
    )


class ElisaKotiakkuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elisa Kotiakku."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ElisaKotiakkuOptionsFlow:
        """Create options flow for this config entry."""
        return ElisaKotiakkuOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — user enters their API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()

            if self._is_api_key_already_configured(api_key):
                return self.async_abort(reason="already_configured")

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
                if self._unique_id_taken_by_other_entry(
                    unique_id,
                    api_key,
                    reauth_entry,
                ):
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
                    unique_id,
                    api_key,
                    reconfigure_entry,
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

    def _is_api_key_already_configured(self, api_key: str) -> bool:
        """Return True if any config entry already owns this API key."""
        for entry in self._async_current_entries():
            if self._entry_has_api_key(entry, api_key):
                return True
        return False

    def _unique_id_taken_by_other_entry(
        self,
        unique_id: str,
        api_key: str,
        current_entry: ConfigEntry[Any],
    ) -> bool:
        """Return True if unique ID already belongs to another config entry."""
        for entry in self._async_current_entries():
            if (
                entry.entry_id != current_entry.entry_id
                and (
                    entry.unique_id == unique_id
                    or self._entry_has_api_key(entry, api_key)
                )
            ):
                return True
        return False

    @staticmethod
    def _entry_has_api_key(entry: ConfigEntry[Any], api_key: str) -> bool:
        """Return True if config entry data contains the same API key."""
        stored_key = entry.data.get(CONF_API_KEY)
        if not isinstance(stored_key, str):
            return False
        return stored_key.strip() == api_key


def _unique_id_from_api_key(api_key: str) -> str:
    """Generate a deterministic non-secret unique ID from the API key."""
    api_key_hash = hashlib.pbkdf2_hmac(
        "sha256",
        api_key.encode(),
        _UNIQUE_ID_KDF_SALT,
        _UNIQUE_ID_KDF_ITERATIONS,
    ).hex()[:16]
    return f"{_UNIQUE_ID_PREFIX}{api_key_hash}"


class ElisaKotiakkuOptionsFlow(OptionsFlow):
    """Options flow for Elisa Kotiakku."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_startup_hours = int(
            self._config_entry.options.get(
                CONF_STARTUP_BACKFILL_HOURS,
                DEFAULT_STARTUP_BACKFILL_HOURS,
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_data_schema(current_startup_hours),
        )
