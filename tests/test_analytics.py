"""Unit tests for historical analytics helpers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from custom_components.elisa_kotiakku.analytics import (
    MAX_CAPACITY_CANDIDATES,
    AnalyticsEpisodeState,
    AnalyticsState,
    DailyAnalyticsBucket,
    _load_daily_buckets,
    _load_episode,
    _ratio_percent,
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


def test_load_ignores_non_mapping_payload() -> None:
    """Non-dict persisted payloads should reset to an empty analytics state."""
    state = AnalyticsState()
    state.load(["not", "a", "mapping"])

    assert state.candidate_count == 0
    assert state.total_day_bucket_count == 0
    assert state.last_period_end is None


def test_as_store_data_serializes_open_episode() -> None:
    """Open episodes should round-trip through persisted analytics state."""
    state = AnalyticsState()
    state.open_episode = AnalyticsEpisodeState(
        direction="discharge",
        start_soc_percent=60.0,
        last_soc_percent=45.0,
        energy_kwh=1.25,
        duration_hours=0.5,
        last_period_end="2026-01-05T08:30:00+02:00",
    )

    stored = state.as_store_data()

    assert stored["open_episode"] == {
        "direction": "discharge",
        "start_soc_percent": 60.0,
        "last_soc_percent": 45.0,
        "energy_kwh": 1.25,
        "duration_hours": 0.5,
        "last_period_end": "2026-01-05T08:30:00+02:00",
    }


def test_metrics_return_none_without_required_baseline_data() -> None:
    """Capacity, rolling, and runtime metrics should stay unavailable without data."""
    state = AnalyticsState()

    assert state.estimated_battery_health_percent(
        expected_usable_capacity_kwh=10.0
    ) is None
    assert (
        state.battery_equivalent_full_cycles(expected_usable_capacity_kwh=0.0)
        is None
    )
    assert state.battery_temperature_average_30d() is None
    assert state.battery_high_temperature_hours_30d() is None
    assert state.battery_low_soc_hours_30d() is None
    assert state.battery_high_soc_hours_30d() is None
    assert state.self_sufficiency_ratio_30d() is None
    assert state.solar_self_consumption_ratio_30d() is None
    assert state.battery_house_supply_ratio_30d() is None
    assert state.battery_charge_from_solar_ratio_30d() is None
    assert state.estimated_backup_runtime_hours(
        measurement=None,
        expected_usable_capacity_kwh=10.0,
    ) is None


def test_process_measurement_tracks_temperature_and_soc_exposures() -> None:
    """Daily buckets should track threshold-based temperature and SoC exposure hours."""
    state = AnalyticsState()
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:00:00+02:00",
            "2026-01-05T08:05:00+02:00",
            battery_power_kw=-2.0,
            state_of_charge_percent=85.0,
            house_power_kw=-2.0,
            battery_temperature_celsius=31.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:05:00+02:00",
            "2026-01-05T08:10:00+02:00",
            battery_power_kw=2.0,
            state_of_charge_percent=10.0,
            house_power_kw=-2.0,
            battery_temperature_celsius=18.0,
        )
    )

    bucket = state.daily_buckets["2026-01-05"]
    assert bucket.high_temperature_hours == pytest.approx(1 / 12, rel=0, abs=1e-6)
    assert bucket.low_soc_hours == pytest.approx(1 / 12, rel=0, abs=1e-6)
    assert bucket.high_soc_hours == pytest.approx(1 / 12, rel=0, abs=1e-6)


def test_estimated_backup_runtime_returns_none_for_missing_soc_or_zero_load() -> None:
    """Runtime estimate should be unavailable without SoC or active house load."""
    state = AnalyticsState()
    missing_soc = _measurement_at(
        "2026-01-05T08:00:00+02:00",
        "2026-01-05T08:05:00+02:00",
        state_of_charge_percent=None,
    )
    zero_load = _measurement_at(
        "2026-01-05T08:05:00+02:00",
        "2026-01-05T08:10:00+02:00",
        state_of_charge_percent=50.0,
        house_power_kw=0.0,
    )

    assert state.estimated_backup_runtime_hours(
        measurement=missing_soc,
        expected_usable_capacity_kwh=10.0,
    ) is None
    assert state.estimated_backup_runtime_hours(
        measurement=zero_load,
        expected_usable_capacity_kwh=10.0,
    ) is None


def test_update_episode_resets_on_invalid_and_non_monotonic_windows() -> None:
    """Invalid or reversed episodes should finalize and restart."""
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
            battery_power_kw=6.0,
            state_of_charge_percent=50.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:10:00+02:00",
            "2026-01-05T08:15:00+02:00",
            battery_power_kw=-4.0,
            state_of_charge_percent=52.0,
        )
    )
    state.process_measurement(
        _measurement_at(
            "2026-01-05T08:15:00+02:00",
            "2026-01-05T08:20:00+02:00",
            battery_power_kw=0.0,
            state_of_charge_percent=52.0,
        )
    )

    assert state.candidate_count == 1
    assert state.open_episode is None
    assert state.estimated_usable_capacity_kwh() == pytest.approx(
        5.0, rel=0, abs=1e-6
    )


def test_update_last_period_end_falls_back_to_string_comparison() -> None:
    """Unparseable timestamps should still advance lexicographically."""
    state = AnalyticsState()
    state.mark_processed("invalid-a")
    state.mark_processed("invalid-b")

    assert state.last_period_end == "invalid-b"


def test_ratio_and_loader_helpers_handle_invalid_input() -> None:
    """Helper functions should ignore invalid persisted structures and bad ratios."""
    loaded_buckets = _load_daily_buckets(
        {
            "2026-01-05": {
                "battery_charge_kwh": 1.5,
                "battery_discharge_kwh": 0.5,
            },
            123: {"battery_charge_kwh": 9.9},
            "bad-value": "ignore-me",
        }
    )

    assert _ratio_percent(1.0, 0.0) is None
    assert set(loaded_buckets) == {"2026-01-05"}
    assert loaded_buckets["2026-01-05"].battery_charge_kwh == 1.5
    assert _load_episode({"direction": 1, "last_period_end": None}) is None


def test_split_window_by_local_date_uses_fallback_for_invalid_window() -> None:
    """Invalid timestamps should collapse to one fallback segment."""
    assert _split_window_by_local_date(
        "not-a-timestamp",
        "also-not-a-timestamp",
        fallback_hours=0.5,
    ) == [("not-a-timestamp", 0.5)]


def test_rolling_metrics_use_loaded_bucket_values() -> None:
    """Rolling metrics should compute ratios from persisted day buckets."""
    state = AnalyticsState()
    state.last_period_end = "2026-01-05T23:55:00+02:00"
    state.daily_buckets["2026-01-05"] = DailyAnalyticsBucket(
        house_consumption_kwh=10.0,
        grid_to_house_kwh=2.5,
        solar_production_kwh=8.0,
        solar_to_house_kwh=3.0,
        solar_to_battery_kwh=1.0,
        battery_to_house_kwh=2.0,
        battery_charge_kwh=4.0,
        battery_discharge_kwh=3.0,
        battery_temperature_weighted_sum=12.0,
        battery_temperature_hours=0.5,
    )

    assert state.battery_equivalent_full_cycles(
        expected_usable_capacity_kwh=5.0
    ) == pytest.approx(0.7, rel=0, abs=1e-6)
    assert state.self_sufficiency_ratio_30d() == pytest.approx(75.0, rel=0, abs=1e-6)
    assert state.solar_self_consumption_ratio_30d() == pytest.approx(
        50.0, rel=0, abs=1e-6
    )
    assert state.battery_house_supply_ratio_30d() == pytest.approx(
        20.0, rel=0, abs=1e-6
    )
    assert state.battery_charge_from_solar_ratio_30d() == pytest.approx(
        25.0, rel=0, abs=1e-6
    )
