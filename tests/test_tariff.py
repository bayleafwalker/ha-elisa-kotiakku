"""Tests for tariff presets and day/night time handling."""

from __future__ import annotations

from datetime import date, datetime

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
    get_tariff_preset_issue,
    normalize_tariff_options,
    tariff_preset_keys,
)


def test_preset_lookup_returns_snapshot_metadata() -> None:
    """Preset lookup should expose the bundled tariff snapshot."""
    preset = get_tariff_preset(TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01)

    assert preset is not None
    assert preset.source_name == "Caruna Espoo Oy Yösiirto"
    assert preset.source_effective_date == "2026-01-01"
    assert preset.valid_from == "2026-01-01"
    assert preset.valid_until == "2026-12-31"

    non_espoo = get_tariff_preset(TARIFF_PRESET_CARUNA_GENERAL_2026_01)
    assert non_espoo is not None
    assert non_espoo.source_name == "Caruna Oy Yleissiirto"
    assert non_espoo.source_effective_date == "2024-09-01"
    assert non_espoo.valid_from == "2026-01-01"
    assert non_espoo.valid_until == "2026-12-31"


def test_tariff_preset_issue_detects_expiring_and_expired_snapshots() -> None:
    """Repair metadata should reflect the preset lifecycle window."""
    expiring = get_tariff_preset_issue(
        TARIFF_PRESET_CARUNA_GENERAL_2026_01,
        current_date=date(2026, 12, 15),
    )
    expired = get_tariff_preset_issue(
        TARIFF_PRESET_CARUNA_GENERAL_2026_01,
        current_date=date(2027, 1, 1),
    )

    assert expiring is not None
    assert expiring.issue_translation_key == "tariff_preset_expiring"
    assert expired is not None
    assert expired.issue_translation_key == "tariff_preset_expired"


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


def test_monthly_power_fee_returns_zero_without_qualifying_hours() -> None:
    """No qualifying hours or no configured rule should produce zero fee."""
    config = TariffConfig()
    assert config.calculate_monthly_power_fee(hourly_average_demands_kw={}) == (
        0.0,
        0.0,
    )

    config = TariffConfig(
        power_fee_rule="unsupported_rule",
        power_fee_rate_eur_per_kw_month=5.0,
    )
    assert config.calculate_monthly_power_fee(
        hourly_average_demands_kw={"2026-06-06T08:00:00+03:00": 8.0}
    ) == (0.0, 0.0)


def test_monthly_power_fee_skips_non_winter_or_weekend_hours() -> None:
    """Winter weekday daytime rule should reject non-qualifying timestamps."""
    config = TariffConfig(
        power_fee_rule="monthly_top3_winter_weekday_daytime",
        power_fee_rate_eur_per_kw_month=5.0,
    )

    assert config.calculate_monthly_power_fee(
        hourly_average_demands_kw={"2026-06-06T08:00:00+03:00": 8.0}
    ) == (0.0, 0.0)
    assert config.calculate_monthly_power_fee(
        hourly_average_demands_kw={"2026-01-04T08:00:00+02:00": 8.0}
    ) == (0.0, 0.0)


def test_tariff_preset_keys_start_with_custom() -> None:
    """Preset key list should keep the custom option first."""
    keys = tariff_preset_keys()
    assert keys[0] == "custom"
    assert TARIFF_PRESET_CARUNA_GENERAL_2026_01 in keys


def test_normalize_tariff_options_keeps_unknown_preset_unchanged() -> None:
    """Unknown preset keys should not override the provided tariff fields."""
    normalized = normalize_tariff_options(
        {
            CONF_TARIFF_PRESET: "unknown_preset",
            CONF_GRID_IMPORT_TRANSFER_FEE: 7.5,
            CONF_TARIFF_MODE: "flat",
        }
    )

    assert normalized[CONF_TARIFF_PRESET] == "unknown_preset"
    assert normalized[CONF_GRID_IMPORT_TRANSFER_FEE] == 7.5


def _dt(value: str) -> datetime:
    """Parse ISO datetime for tariff tests."""
    return datetime.fromisoformat(value)
