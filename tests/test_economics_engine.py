"""Unit tests for EconomicsEngine."""

from __future__ import annotations

from dataclasses import replace

from custom_components.elisa_kotiakku.economics_engine import EconomicsEngine
from custom_components.elisa_kotiakku.tariff import TariffConfig

from .conftest import SAMPLE_MEASUREMENT


def test_restore_respects_tariff_signature_and_roundtrip_payload() -> None:
    """Restore should load matching state and ignore mismatched signatures."""
    engine = EconomicsEngine()
    stored = {
        "totals": {
            "purchase_cost": 1.5,
            "battery_savings": 0.25,
        },
        "last_period_end": "2025-12-17T00:05:00+02:00",
        "processed_period_ends": ["2025-12-17T00:05:00+02:00"],
        "skipped_savings_window_count": 2,
        "tariff_signature": "sig-a",
        "power_fee_hour_buckets": {},
        "power_fee_monthly_estimates": {"2025-12": 1.1},
        "power_fee_monthly_peaks": {"2025-12": 2.2},
        "grid_import_monthly_peaks": {"2025-12": 3.3},
        "baseline_power_fee_hour_buckets": {},
        "baseline_power_fee_monthly_estimates": {"2025-12": 0.9},
        "attribution_skipped_window_counts": {
            "solar_used_in_house_value": 1,
            "solar_export_net_value": 0,
            "battery_house_supply_value": 2,
        },
        "monthly_battery_savings": {"2025-12": 0.25},
        "monthly_processed_window_counts": {"2025-12": 4},
        "monthly_savings_window_counts": {"2025-12": 3},
        "monthly_skipped_savings_window_counts": {"2025-12": 1},
        "monthly_tariff_snapshot_ids": {"2025-12": "snapshot-id"},
        "monthly_tariff_snapshots": {"2025-12": {"tariff_mode": "flat"}},
    }

    engine.restore(stored, expected_tariff_signature="sig-a")
    assert engine.get_total("purchase_cost") == 1.5
    assert engine.get_total("battery_savings") == 0.25
    assert engine.last_period_end == "2025-12-17T00:05:00+02:00"
    assert engine.processed_period_count == 1
    assert engine.get_debug_value("skipped_savings_windows") == 2
    assert engine.monthly_processed_window_counts == {"2025-12": 4}
    assert engine.monthly_savings_window_counts == {"2025-12": 3}
    assert engine.monthly_skipped_savings_window_counts == {"2025-12": 1}
    assert engine.monthly_tariff_snapshot_ids == {"2025-12": "snapshot-id"}
    assert engine.monthly_tariff_snapshots == {
        "2025-12": {"tariff_mode": "flat"}
    }

    payload = engine.as_store_payload(tariff_signature="sig-a")
    assert payload["tariff_signature"] == "sig-a"
    assert payload["totals"]["purchase_cost"] == 1.5
    assert payload["monthly_tariff_snapshot_ids"] == {"2025-12": "snapshot-id"}

    engine.restore(stored, expected_tariff_signature="sig-b")
    assert engine.get_total("purchase_cost") == 0.0
    assert engine.processed_period_count == 0


def test_process_measurement_deduplicates_and_tracks_monthly_savings() -> None:
    """Engine should process one window once and track monthly savings map."""
    engine = EconomicsEngine()
    tariff_config = TariffConfig.from_mapping({})
    measurement = replace(
        SAMPLE_MEASUREMENT,
        period_start="2025-12-17T00:00:00+02:00",
        period_end="2025-12-17T00:05:00+02:00",
        grid_power_kw=4.0,
        grid_to_house_kw=2.0,
        battery_to_house_kw=1.0,
        solar_to_grid_kw=0.5,
        solar_to_battery_kw=0.5,
        spot_price_cents_per_kwh=2.0,
    )

    first = engine.process_measurement(measurement, tariff_config=tariff_config)
    second = engine.process_measurement(measurement, tariff_config=tariff_config)

    assert first is True
    assert second is False
    assert engine.processed_period_count == 1
    assert engine.last_period_end == "2025-12-17T00:05:00+02:00"
    assert "2025-12" in engine.monthly_battery_savings
    assert engine.monthly_processed_window_counts == {"2025-12": 1}
    assert engine.monthly_savings_window_counts == {"2025-12": 1}
    assert engine.monthly_skipped_savings_window_counts == {}


def test_monthly_window_counters_cross_calendar_boundary() -> None:
    engine = EconomicsEngine()
    tariff_config = TariffConfig.from_mapping({})
    for start, end in (
        ("2025-12-31T23:55:00+02:00", "2026-01-01T00:00:00+02:00"),
        ("2026-01-01T00:00:00+02:00", "2026-01-01T00:05:00+02:00"),
    ):
        measurement = replace(
            SAMPLE_MEASUREMENT,
            period_start=start,
            period_end=end,
            grid_to_house_kw=1.0,
            battery_to_house_kw=0.0,
            solar_to_grid_kw=0.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=4.0,
        )
        assert engine.process_measurement(measurement, tariff_config=tariff_config)
    assert engine.monthly_processed_window_counts == {"2025-12": 1, "2026-01": 1}
    assert engine.monthly_savings_window_counts == {"2025-12": 1, "2026-01": 1}
    assert engine.monthly_skipped_savings_window_counts == {}


def test_missing_spot_rate_counts_processed_but_not_savings_window() -> None:
    engine = EconomicsEngine()
    tariff_config = TariffConfig.from_mapping({})
    measurement = replace(
        SAMPLE_MEASUREMENT,
        period_start="2025-12-17T00:00:00+02:00",
        period_end="2025-12-17T00:05:00+02:00",
        grid_to_house_kw=1.0,
        battery_to_house_kw=0.0,
        solar_to_grid_kw=0.0,
        solar_to_battery_kw=0.0,
        spot_price_cents_per_kwh=None,
    )
    assert engine.process_measurement(measurement, tariff_config=tariff_config)
    assert engine.monthly_processed_window_counts == {"2025-12": 1}
    assert engine.monthly_savings_window_counts == {}
    assert engine.monthly_skipped_savings_window_counts == {"2025-12": 1}


def test_monthly_tariff_snapshot_is_unknown_when_signature_changes_midmonth() -> None:
    engine = EconomicsEngine()
    tariff_config = TariffConfig.from_mapping({})
    changed_tariff = replace(
        tariff_config, import_retailer_margin_cents_per_kwh=1.0
    )
    for index, config in enumerate((tariff_config, changed_tariff)):
        start_minute = index * 5
        measurement = replace(
            SAMPLE_MEASUREMENT,
            period_start=f"2025-12-17T00:{start_minute:02d}:00+02:00",
            period_end=f"2025-12-17T00:{start_minute + 5:02d}:00+02:00",
            grid_to_house_kw=1.0,
            battery_to_house_kw=0.0,
            solar_to_grid_kw=0.0,
            solar_to_battery_kw=0.0,
            spot_price_cents_per_kwh=4.0,
        )
        assert engine.process_measurement(measurement, tariff_config=config)
    assert engine.monthly_tariff_snapshot_ids == {"2025-12": None}
    assert engine.monthly_tariff_snapshots == {"2025-12": None}
