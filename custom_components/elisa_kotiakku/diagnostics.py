"""Diagnostics support for Elisa Kotiakku."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant

from . import ElisaKotiakkuConfigEntry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY}
_MANIFEST_PATH = Path(__file__).with_name("manifest.json")


def _integration_version() -> str | None:
    """Return the installed integration version from manifest.json."""
    try:
        manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version = manifest.get("version")
    if isinstance(version, str):
        return version
    return None


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
        "integration_version": _integration_version(),
        "home_assistant_version": HA_VERSION,
        "config": config_data,
        "options": dict(entry.options),
        "configured_tariff_preset": coordinator.tariff_config.tariff_preset,
        "configured_tariff_mode": coordinator.tariff_config.tariff_mode,
        "latest_measurement": measurement,
        "last_api_error": coordinator.get_last_api_error(),
        "last_apply_window_counts": coordinator.get_last_apply_window_counts(),
        "last_rebuild_window_counts": coordinator.get_last_rebuild_window_counts(),
        "energy_totals": coordinator.get_energy_totals(),
        "energy_last_period_end": coordinator.get_energy_last_period_end(),
        "energy_processed_period_count": coordinator.energy_processed_period_count,
        "economics_totals": coordinator.get_economics_totals(),
        "economics_last_period_end": coordinator.get_economics_last_period_end(),
        "economics_processed_period_count": (
            coordinator.economics_processed_period_count
        ),
        "skipped_savings_window_count": (
            coordinator.get_skipped_savings_window_count()
        ),
        "attribution_skipped_window_counts": (
            coordinator.get_attribution_skipped_window_counts()
        ),
        "monthly_battery_savings": coordinator.get_monthly_battery_savings(),
        "power_fee_monthly_estimates": coordinator.get_power_fee_monthly_estimates(),
        "power_fee_monthly_peaks": coordinator.get_power_fee_monthly_peaks(),
        "analytics_last_period_end": coordinator.analytics_last_period_end,
        "analytics_processed_period_count": (
            coordinator.analytics_processed_period_count
        ),
        "analytics_candidate_count": coordinator.analytics_state.candidate_count,
        "analytics_estimated_usable_capacity_kwh": (
            coordinator.analytics_state.estimated_usable_capacity_kwh()
        ),
        "analytics_total_day_bucket_count": (
            coordinator.analytics_state.total_day_bucket_count
        ),
        "analytics_rolling_bucket_count": (
            coordinator.analytics_state.rolling_bucket_count()
        ),
        "analytics_open_episode": (
            asdict(coordinator.analytics_state.open_episode)
            if coordinator.analytics_state.open_episode is not None
            else None
        ),
    }
