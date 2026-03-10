"""Unit tests for EnergyStore."""

from __future__ import annotations

from dataclasses import replace

from custom_components.elisa_kotiakku.energy_store import EnergyStore

from .conftest import SAMPLE_MEASUREMENT


def test_restore_and_payload_roundtrip() -> None:
    """EnergyStore should restore persisted values and serialize them back."""
    store = EnergyStore()
    stored = {
        "totals": {
            "grid_import_energy": 1.25,
            "solar_production_energy": 0.5,
        },
        "last_period_end": "2025-12-17T00:05:00+02:00",
        "processed_period_ends": ["2025-12-17T00:05:00+02:00"],
    }

    store.restore(stored)

    assert store.get_total("grid_import_energy") == 1.25
    assert store.get_total("solar_production_energy") == 0.5
    assert store.last_period_end == "2025-12-17T00:05:00+02:00"
    assert store.processed_period_count == 1

    payload = store.as_store_payload()
    assert payload["last_period_end"] == "2025-12-17T00:05:00+02:00"
    assert "2025-12-17T00:05:00+02:00" in payload["processed_period_ends"]


def test_process_measurement_applies_once() -> None:
    """Processing same period twice should deduplicate totals."""
    store = EnergyStore()
    measurement = replace(
        SAMPLE_MEASUREMENT,
        period_start="2025-12-17T00:00:00+02:00",
        period_end="2025-12-17T00:05:00+02:00",
        grid_power_kw=6.0,
        solar_power_kw=1.2,
        house_power_kw=-2.4,
        battery_power_kw=-3.0,
    )

    first = store.process_measurement(measurement)
    second = store.process_measurement(measurement)

    assert first is True
    assert second is False
    assert store.get_total("grid_import_energy") == 0.5
    assert store.get_total("solar_production_energy") == 0.1
    assert store.get_total("house_consumption_energy") == 0.2
    assert store.get_total("battery_charge_energy") == 0.25
    assert store.last_period_end == "2025-12-17T00:05:00+02:00"
