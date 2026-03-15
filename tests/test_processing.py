"""Tests for batch measurement processing helpers."""

from __future__ import annotations

from dataclasses import replace

from custom_components.elisa_kotiakku.analytics import AnalyticsState
from custom_components.elisa_kotiakku.economics_engine import EconomicsEngine
from custom_components.elisa_kotiakku.energy_store import EnergyStore
from custom_components.elisa_kotiakku.processing import (
    apply_measurements,
    rebuild_economics_range,
)
from custom_components.elisa_kotiakku.tariff import TariffConfig

from .conftest import SAMPLE_MEASUREMENT


def test_apply_measurements_tracks_processed_and_deduped_windows() -> None:
    """Duplicates in one batch should be counted without mutating totals twice."""
    measurement = replace(
        SAMPLE_MEASUREMENT,
        period_start="2026-01-05T08:00:00+02:00",
        period_end="2026-01-05T08:05:00+02:00",
        grid_power_kw=6.0,
        house_power_kw=-2.4,
        battery_power_kw=-3.0,
    )

    stats = apply_measurements(
        [measurement, measurement],
        energy_state=EnergyStore(),
        economics_state=EconomicsEngine(),
        analytics_state=AnalyticsState(),
        tariff_config=TariffConfig.from_mapping({}),
    )

    assert stats.processed_count == 1
    assert stats.deduped_count == 1
    assert stats.energy_changed is True
    assert stats.economics_changed is True
    assert stats.analytics_changed is True
    assert stats.latest_processed_measurement == measurement
    assert stats.as_counts() == {"processed": 1, "deduped": 1}


def test_rebuild_economics_range_dedupes_duplicate_history_windows() -> None:
    """Economics rebuild should replay one window once and report duplicates."""
    measurement = replace(
        SAMPLE_MEASUREMENT,
        period_start="2026-01-05T08:00:00+02:00",
        period_end="2026-01-05T08:05:00+02:00",
        grid_power_kw=4.0,
        grid_to_house_kw=2.0,
        battery_to_house_kw=1.0,
        solar_to_grid_kw=0.5,
        solar_to_battery_kw=0.5,
        spot_price_cents_per_kwh=2.0,
    )

    stats = rebuild_economics_range(
        [measurement, measurement],
        economics_state=EconomicsEngine(),
        analytics_state=AnalyticsState(),
        tariff_config=TariffConfig.from_mapping({}),
    )

    assert stats.processed_count == 1
    assert stats.deduped_count == 1
    assert stats.energy_changed is False
    assert stats.economics_changed is True
    assert stats.analytics_changed is True
    assert stats.latest_processed_measurement == measurement
