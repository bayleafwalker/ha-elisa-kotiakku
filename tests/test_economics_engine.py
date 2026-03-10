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
    }

    engine.restore(stored, expected_tariff_signature="sig-a")
    assert engine.get_total("purchase_cost") == 1.5
    assert engine.get_total("battery_savings") == 0.25
    assert engine.last_period_end == "2025-12-17T00:05:00+02:00"
    assert engine.processed_period_count == 1
    assert engine.get_debug_value("skipped_savings_windows") == 2

    payload = engine.as_store_payload(tariff_signature="sig-a")
    assert payload["tariff_signature"] == "sig-a"
    assert payload["totals"]["purchase_cost"] == 1.5

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
