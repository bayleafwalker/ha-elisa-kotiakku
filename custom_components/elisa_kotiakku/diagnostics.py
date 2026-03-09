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
        "options": dict(entry.options),
        "latest_measurement": measurement,
        "energy_totals": coordinator.energy_totals,
        "energy_last_period_end": coordinator.energy_last_period_end,
        "energy_processed_period_count": coordinator.energy_processed_period_count,
        "economics_totals": coordinator.economics_totals,
        "economics_last_period_end": coordinator.economics_last_period_end,
        "economics_processed_period_count": (
            coordinator.economics_processed_period_count
        ),
        "skipped_savings_window_count": (
            coordinator.skipped_savings_window_count
        ),
        "attribution_skipped_window_counts": (
            coordinator.get_attribution_skipped_window_counts()
        ),
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
