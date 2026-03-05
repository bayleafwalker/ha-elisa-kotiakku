"""Diagnostics support for Elisa Kotiakku."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import ElisaKotiakkuConfigEntry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ElisaKotiakkuConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Redact sensitive fields from config
    config_data = {
        k: "**REDACTED**" if k in TO_REDACT else v
        for k, v in entry.data.items()
    }

    measurement = (
        asdict(coordinator.data) if coordinator.data is not None else None
    )

    return {
        "config": config_data,
        "latest_measurement": measurement,
    }
