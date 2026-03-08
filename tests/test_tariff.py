"""Tests for tariff presets and day/night time handling."""

from __future__ import annotations

from custom_components.elisa_kotiakku.const import (
    CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
    CONF_ELECTRICITY_TAX_FEE,
    CONF_GRID_IMPORT_TRANSFER_FEE,
    CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    CONF_TARIFF_MODE,
    CONF_TARIFF_PRESET,
    TARIFF_MODE_DAY_NIGHT,
    TARIFF_MODE_SEASONAL_DAY_NIGHT,
    TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
    TARIFF_PRESET_CARUNA_GENERAL_2026_01,
    TARIFF_PRESET_CARUNA_NIGHT_SEASONAL_2026_01,
)
from custom_components.elisa_kotiakku.tariff import (
    TariffConfig,
    get_tariff_preset,
    normalize_tariff_options,
)


def test_preset_lookup_returns_snapshot_metadata() -> None:
    """Preset lookup should expose the bundled tariff snapshot."""
    preset = get_tariff_preset(TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01)

    assert preset is not None
    assert preset.source_name == "Caruna Espoo Oy Yösiirto"
    assert preset.source_effective_date == "2026-01-01"

    non_espoo = get_tariff_preset(TARIFF_PRESET_CARUNA_GENERAL_2026_01)
    assert non_espoo is not None
    assert non_espoo.source_name == "Caruna Oy Yleissiirto"
    assert non_espoo.source_effective_date == "2024-09-01"


def test_normalize_tariff_options_applies_preset_values() -> None:
    """Preset normalization should override transfer-side fields."""
    normalized = normalize_tariff_options(
        {
            CONF_TARIFF_PRESET: TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
            CONF_TARIFF_MODE: "flat",
            CONF_GRID_IMPORT_TRANSFER_FEE: 99.0,
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 99.0,
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 99.0,
        }
    )

    assert normalized[CONF_TARIFF_MODE] == TARIFF_MODE_DAY_NIGHT
    assert normalized[CONF_GRID_IMPORT_TRANSFER_FEE] == 0.0
    assert normalized[CONF_DAY_GRID_IMPORT_TRANSFER_FEE] == 5.11
    assert normalized[CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE] == 3.12


def test_day_night_split_handles_dst_spring_forward() -> None:
    """Day/night resolution should use local wall clock across spring DST."""
    config = TariffConfig(
        tariff_mode=TARIFF_MODE_DAY_NIGHT,
        day_grid_import_transfer_fee_cents_per_kwh=5.11,
        night_grid_import_transfer_fee_cents_per_kwh=3.12,
    )

    before = config.active_rates(
        timestamp=_dt("2026-03-29T06:55:00+03:00"),
        spot_price_cents_per_kwh=2.0,
    )
    after = config.active_rates(
        timestamp=_dt("2026-03-29T07:00:00+03:00"),
        spot_price_cents_per_kwh=2.0,
    )

    assert before.tariff_period == "night"
    assert before.import_transfer_fee_cents_per_kwh == 3.12
    assert after.tariff_period == "day"
    assert after.import_transfer_fee_cents_per_kwh == 5.11


def test_day_night_split_handles_dst_fall_back() -> None:
    """Day/night resolution should use local wall clock across autumn DST."""
    config = TariffConfig(
        tariff_mode=TARIFF_MODE_DAY_NIGHT,
        day_grid_import_transfer_fee_cents_per_kwh=5.11,
        night_grid_import_transfer_fee_cents_per_kwh=3.12,
    )

    night = config.active_rates(
        timestamp=_dt("2026-10-25T06:55:00+02:00"),
        spot_price_cents_per_kwh=2.0,
    )
    day = config.active_rates(
        timestamp=_dt("2026-10-25T07:00:00+02:00"),
        spot_price_cents_per_kwh=2.0,
    )

    assert night.tariff_period == "night"
    assert day.tariff_period == "day"


def test_active_rates_include_electricity_tax() -> None:
    """Resolved rates should expose the configured import-side electricity tax."""
    config = TariffConfig.from_mapping({CONF_ELECTRICITY_TAX_FEE: 2.79})

    rates = config.active_rates(
        timestamp=_dt("2026-01-05T08:00:00+02:00"),
        spot_price_cents_per_kwh=2.0,
    )

    assert rates.electricity_tax_cents_per_kwh == 2.79


def test_normalize_tariff_options_applies_seasonal_preset_values() -> None:
    """Seasonal preset normalization should set the new tariff mode."""
    normalized = normalize_tariff_options(
        {
            CONF_TARIFF_PRESET: TARIFF_PRESET_CARUNA_NIGHT_SEASONAL_2026_01,
            CONF_TARIFF_MODE: "flat",
            CONF_GRID_IMPORT_TRANSFER_FEE: 99.0,
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE: 99.0,
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE: 99.0,
        }
    )

    assert normalized[CONF_TARIFF_MODE] == TARIFF_MODE_SEASONAL_DAY_NIGHT
    assert normalized[CONF_GRID_IMPORT_TRANSFER_FEE] == 0.0
    assert normalized[CONF_DAY_GRID_IMPORT_TRANSFER_FEE] == 6.73
    assert normalized[CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE] == 3.23


def test_seasonal_day_night_split_uses_winter_day_window() -> None:
    """Seasonal mode should only use the higher rate in winter daytime."""
    config = TariffConfig(
        tariff_mode=TARIFF_MODE_SEASONAL_DAY_NIGHT,
        day_grid_import_transfer_fee_cents_per_kwh=6.73,
        night_grid_import_transfer_fee_cents_per_kwh=3.23,
    )

    winter_day = config.active_rates(
        timestamp=_dt("2026-01-05T08:00:00+02:00"),
        spot_price_cents_per_kwh=2.0,
    )
    summer_day = config.active_rates(
        timestamp=_dt("2026-06-05T08:00:00+03:00"),
        spot_price_cents_per_kwh=2.0,
    )
    winter_sunday = config.active_rates(
        timestamp=_dt("2026-01-04T08:00:00+02:00"),
        spot_price_cents_per_kwh=2.0,
    )

    assert winter_day.tariff_period == "winter_day"
    assert winter_day.import_transfer_fee_cents_per_kwh == 6.73
    assert summer_day.tariff_period == "other"
    assert summer_day.import_transfer_fee_cents_per_kwh == 3.23
    assert winter_sunday.tariff_period == "other"
    assert winter_sunday.import_transfer_fee_cents_per_kwh == 3.23


def _dt(value: str):
    """Parse ISO datetime for tariff tests."""
    from datetime import datetime

    return datetime.fromisoformat(value)
