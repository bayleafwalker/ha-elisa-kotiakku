"""Unit tests for historical analytics helpers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.elisa_kotiakku.analytics import (
    MAX_CAPACITY_CANDIDATES,
    AnalyticsState,
    _split_window_by_local_date,
)

from .conftest import SAMPLE_MEASUREMENT


def _measurement_at(
    period_start: str,
    period_end: str,
    *,
    battery_power_kw: float = 0.0,
    state_of_charge_percent: float | None = None,
    house_power_kw: float = -1.0,
    battery_temperature_celsius: float | None = 24.0,
) -> type(SAMPLE_MEASUREMENT):
    """Build a measurement with explicit episode-driving values."""
    return replace(
        SAMPLE_MEASUREMENT,
        period_start=period_start,
        period_end=period_end,
        battery_power_kw=battery_power_kw,
        state_of_charge_percent=state_of_charge_percent,
        house_power_kw=house_power_kw,
        battery_temperature_celsius=battery_temperature_celsius,
    )


def test_valid_discharge_episode_produces_capacity_candidate() -> None:
    """A monotonic episode above the thresholds should create a candidate."""
    state = AnalyticsState()

    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:00:00+02:00",
            "2026-01-05T08:05:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=60.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:05:00+02:00",
            "2026-01-05T08:10:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=55.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:10:00+02:00",
            "2026-01-05T08:15:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=50.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:15:00+02:00",
            "2026-01-05T08:20:00+02:00",
            battery_power_kw=0.0,
            state_of_charge_percent=50.0,
        )
    )

    assert state.candidate_count == 1
    assert state.estimated_usable_capacity_kwh() == pytest.approx(
        6.666667, rel=0, abs=1e-6
    )


def test_missing_or_flat_soc_windows_do_not_produce_candidate() -> None:
    """Noisy or incomplete windows should not create usable-capacity estimates."""
    state = AnalyticsState()

    state.process_measurement(
        _measurement_at(
            "2026-01-05T09:00:00+02:00",
            "2026-01-05T09:05:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=60.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T09:05:00+02:00",
            "2026-01-05T09:10:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=60.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T09:10:00+02:00",
            "2026-01-05T09:15:00+02:00",
            battery_power_kw=4.0,
            state_of_charge_percent=None,
        )
    )

    assert state.candidate_count == 0
    assert state.estimated_usable_capacity_kwh() is None


def test_episodes_below_threshold_do_not_create_candidates() -> None:
    """Short or shallow episodes should be ignored."""
    state = AnalyticsState()

    state.process_measurement(
        _measurement_at(
            "2026-01-05T10:00:00+02:00",
            "2026-01-05T10:05:00+02:00",
            battery_power_kw=1.0,
            state_of_charge_percent=60.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T10:05:00+02:00",
            "2026-01-05T10:10:00+02:00",
            battery_power_kw=1.0,
            state_of_charge_percent=56.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T10:10:00+02:00",
            "2026-01-05T10:15:00+02:00",
            battery_power_kw=0.0,
            state_of_charge_percent=56.0,
        )
    )

    assert state.candidate_count == 0


def test_load_keeps_last_twenty_candidates_and_median() -> None:
    """Persisted candidates should be truncated to the most recent 20 values."""
    state = AnalyticsState()
    state.load(
        {
            "usable_capacity_candidates_kwh": list(
                range(1, MAX_CAPACITY_CANDIDATES + 6)
            )
        }
    )

    assert state.candidate_count == MAX_CAPACITY_CANDIDATES
    assert state.usable_capacity_candidates_kwh == list(range(6, 26))
    assert state.estimated_usable_capacity_kwh() == 15.5


def test_process_measurement_splits_daily_bucket_at_midnight() -> None:
    """Windows crossing local midnight should be apportioned across both dates."""
    state = AnalyticsState()
    state.process_measurement(
        _measurement_at(
            "2026-03-28T23:55:00+02:00",
            "2026-03-29T00:05:00+02:00",
            house_power_kw=-6.0,
            state_of_charge_percent=50.0,
            battery_temperature_celsius=24.0,
        )
    )

    assert state.daily_buckets["2026-03-28"].house_consumption_kwh == pytest.approx(
        0.5, rel=0, abs=1e-6
    )
    assert state.daily_buckets["2026-03-29"].house_consumption_kwh == pytest.approx(
        0.5, rel=0, abs=1e-6
    )


def test_split_window_by_local_date_handles_dst_transition_dates() -> None:
    """Date splitting should preserve duration around Finnish DST dates."""
    segments = _split_window_by_local_date(
        "2026-03-28T23:55:00+02:00",
        "2026-03-29T00:05:00+02:00",
        fallback_hours=1 / 6,
    )

    assert segments == [
        ("2026-03-28", pytest.approx(1 / 12, rel=0, abs=1e-6)),
        ("2026-03-29", pytest.approx(1 / 12, rel=0, abs=1e-6)),
    ]
