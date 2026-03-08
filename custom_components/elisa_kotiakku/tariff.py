"""Tariff configuration and pricing helpers for Elisa Kotiakku."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .const import (
    CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
    CONF_DAY_IMPORT_RETAILER_MARGIN,
    CONF_ELECTRICITY_TAX_FEE,
    CONF_EXPORT_RETAILER_ADJUSTMENT,
    CONF_GRID_EXPORT_TRANSFER_FEE,
    CONF_GRID_IMPORT_TRANSFER_FEE,
    CONF_IMPORT_RETAILER_MARGIN,
    CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    CONF_NIGHT_IMPORT_RETAILER_MARGIN,
    CONF_POWER_FEE_RATE,
    CONF_POWER_FEE_RULE,
    CONF_TARIFF_MODE,
    CONF_TARIFF_PRESET,
    DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_DAY_IMPORT_RETAILER_MARGIN,
    DEFAULT_ELECTRICITY_TAX_FEE,
    DEFAULT_EXPORT_RETAILER_ADJUSTMENT,
    DEFAULT_GRID_EXPORT_TRANSFER_FEE,
    DEFAULT_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_IMPORT_RETAILER_MARGIN,
    DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE,
    DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN,
    DEFAULT_POWER_FEE_RATE,
    DEFAULT_POWER_FEE_RULE,
    DEFAULT_TARIFF_MODE,
    DEFAULT_TARIFF_PRESET,
    POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
    POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME,
    TARIFF_MODE_DAY_NIGHT,
    TARIFF_MODE_FLAT,
    TARIFF_MODE_SEASONAL_DAY_NIGHT,
    TARIFF_PRESET_CARUNA_ESPOO_GENERAL_2026_01,
    TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
    TARIFF_PRESET_CARUNA_GENERAL_2026_01,
    TARIFF_PRESET_CARUNA_NIGHT_2026_01,
    TARIFF_PRESET_CARUNA_NIGHT_SEASONAL_2026_01,
    TARIFF_PRESET_CUSTOM,
)

_DAY_START_HOUR = 7
_DAY_END_HOUR = 22
_WINTER_MONTHS = {1, 2, 3, 11, 12}


@dataclass(frozen=True, slots=True)
class TariffPreset:
    """A dated tariff preset for transfer-side pricing."""

    key: str
    tariff_mode: str
    grid_import_transfer_fee_cents_per_kwh: float
    day_grid_import_transfer_fee_cents_per_kwh: float
    night_grid_import_transfer_fee_cents_per_kwh: float
    source_name: str
    source_effective_date: str


_TARIFF_PRESETS: dict[str, TariffPreset] = {
    TARIFF_PRESET_CARUNA_GENERAL_2026_01: TariffPreset(
        key=TARIFF_PRESET_CARUNA_GENERAL_2026_01,
        tariff_mode=TARIFF_MODE_FLAT,
        grid_import_transfer_fee_cents_per_kwh=5.26,
        day_grid_import_transfer_fee_cents_per_kwh=5.26,
        night_grid_import_transfer_fee_cents_per_kwh=5.26,
        source_name="Caruna Oy Yleissiirto",
        source_effective_date="2024-09-01",
    ),
    TARIFF_PRESET_CARUNA_NIGHT_2026_01: TariffPreset(
        key=TARIFF_PRESET_CARUNA_NIGHT_2026_01,
        tariff_mode=TARIFF_MODE_DAY_NIGHT,
        grid_import_transfer_fee_cents_per_kwh=0.0,
        day_grid_import_transfer_fee_cents_per_kwh=5.11,
        night_grid_import_transfer_fee_cents_per_kwh=3.12,
        source_name="Caruna Oy Yösiirto",
        source_effective_date="2024-09-01",
    ),
    TARIFF_PRESET_CARUNA_NIGHT_SEASONAL_2026_01: TariffPreset(
        key=TARIFF_PRESET_CARUNA_NIGHT_SEASONAL_2026_01,
        tariff_mode=TARIFF_MODE_SEASONAL_DAY_NIGHT,
        grid_import_transfer_fee_cents_per_kwh=0.0,
        day_grid_import_transfer_fee_cents_per_kwh=6.73,
        night_grid_import_transfer_fee_cents_per_kwh=3.23,
        source_name="Caruna Oy Kausisiirto",
        source_effective_date="2024-09-01",
    ),
    TARIFF_PRESET_CARUNA_ESPOO_GENERAL_2026_01: TariffPreset(
        key=TARIFF_PRESET_CARUNA_ESPOO_GENERAL_2026_01,
        tariff_mode=TARIFF_MODE_FLAT,
        grid_import_transfer_fee_cents_per_kwh=4.87,
        day_grid_import_transfer_fee_cents_per_kwh=4.87,
        night_grid_import_transfer_fee_cents_per_kwh=4.87,
        source_name="Caruna Espoo Oy Yleissiirto",
        source_effective_date="2026-01-01",
    ),
    TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01: TariffPreset(
        key=TARIFF_PRESET_CARUNA_ESPOO_NIGHT_2026_01,
        tariff_mode=TARIFF_MODE_DAY_NIGHT,
        grid_import_transfer_fee_cents_per_kwh=0.0,
        day_grid_import_transfer_fee_cents_per_kwh=5.11,
        night_grid_import_transfer_fee_cents_per_kwh=3.12,
        source_name="Caruna Espoo Oy Yösiirto",
        source_effective_date="2026-01-01",
    ),
}


@dataclass(frozen=True, slots=True)
class ActiveTariffRates:
    """Resolved tariff values for a single measurement window."""

    tariff_mode: str
    tariff_period: str
    import_retailer_margin_cents_per_kwh: float
    import_transfer_fee_cents_per_kwh: float
    electricity_tax_cents_per_kwh: float
    export_retailer_adjustment_cents_per_kwh: float
    export_transfer_fee_cents_per_kwh: float
    import_unit_price_cents_per_kwh: float | None
    export_unit_price_cents_per_kwh: float | None


@dataclass(frozen=True, slots=True)
class TariffConfig:
    """Runtime tariff configuration derived from config entry options."""

    tariff_preset: str = DEFAULT_TARIFF_PRESET
    tariff_mode: str = DEFAULT_TARIFF_MODE
    import_retailer_margin_cents_per_kwh: float = DEFAULT_IMPORT_RETAILER_MARGIN
    export_retailer_adjustment_cents_per_kwh: float = (
        DEFAULT_EXPORT_RETAILER_ADJUSTMENT
    )
    grid_import_transfer_fee_cents_per_kwh: float = (
        DEFAULT_GRID_IMPORT_TRANSFER_FEE
    )
    grid_export_transfer_fee_cents_per_kwh: float = (
        DEFAULT_GRID_EXPORT_TRANSFER_FEE
    )
    electricity_tax_cents_per_kwh: float = DEFAULT_ELECTRICITY_TAX_FEE
    day_import_retailer_margin_cents_per_kwh: float = (
        DEFAULT_DAY_IMPORT_RETAILER_MARGIN
    )
    night_import_retailer_margin_cents_per_kwh: float = (
        DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN
    )
    day_grid_import_transfer_fee_cents_per_kwh: float = (
        DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE
    )
    night_grid_import_transfer_fee_cents_per_kwh: float = (
        DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE
    )
    power_fee_rule: str = DEFAULT_POWER_FEE_RULE
    power_fee_rate_eur_per_kw_month: float = DEFAULT_POWER_FEE_RATE

    @classmethod
    def from_mapping(cls, options: Mapping[str, Any]) -> TariffConfig:
        """Build tariff configuration from config entry options."""
        normalized = normalize_tariff_options(options)
        return cls(
            tariff_preset=str(
                normalized.get(CONF_TARIFF_PRESET, DEFAULT_TARIFF_PRESET)
            ),
            tariff_mode=str(normalized.get(CONF_TARIFF_MODE, DEFAULT_TARIFF_MODE)),
            import_retailer_margin_cents_per_kwh=float(
                normalized.get(
                    CONF_IMPORT_RETAILER_MARGIN,
                    DEFAULT_IMPORT_RETAILER_MARGIN,
                )
            ),
            export_retailer_adjustment_cents_per_kwh=float(
                normalized.get(
                    CONF_EXPORT_RETAILER_ADJUSTMENT,
                    DEFAULT_EXPORT_RETAILER_ADJUSTMENT,
                )
            ),
            grid_import_transfer_fee_cents_per_kwh=float(
                normalized.get(
                    CONF_GRID_IMPORT_TRANSFER_FEE,
                    DEFAULT_GRID_IMPORT_TRANSFER_FEE,
                )
            ),
            grid_export_transfer_fee_cents_per_kwh=float(
                normalized.get(
                    CONF_GRID_EXPORT_TRANSFER_FEE,
                    DEFAULT_GRID_EXPORT_TRANSFER_FEE,
                )
            ),
            electricity_tax_cents_per_kwh=float(
                normalized.get(
                    CONF_ELECTRICITY_TAX_FEE,
                    DEFAULT_ELECTRICITY_TAX_FEE,
                )
            ),
            day_import_retailer_margin_cents_per_kwh=float(
                normalized.get(
                    CONF_DAY_IMPORT_RETAILER_MARGIN,
                    DEFAULT_DAY_IMPORT_RETAILER_MARGIN,
                )
            ),
            night_import_retailer_margin_cents_per_kwh=float(
                normalized.get(
                    CONF_NIGHT_IMPORT_RETAILER_MARGIN,
                    DEFAULT_NIGHT_IMPORT_RETAILER_MARGIN,
                )
            ),
            day_grid_import_transfer_fee_cents_per_kwh=float(
                normalized.get(
                    CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
                    DEFAULT_DAY_GRID_IMPORT_TRANSFER_FEE,
                )
            ),
            night_grid_import_transfer_fee_cents_per_kwh=float(
                normalized.get(
                    CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
                    DEFAULT_NIGHT_GRID_IMPORT_TRANSFER_FEE,
                )
            ),
            power_fee_rule=str(
                normalized.get(CONF_POWER_FEE_RULE, DEFAULT_POWER_FEE_RULE)
            ),
            power_fee_rate_eur_per_kw_month=float(
                normalized.get(CONF_POWER_FEE_RATE, DEFAULT_POWER_FEE_RATE)
            ),
        )

    def signature(self) -> str:
        """Return a stable signature for economics persistence."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def active_rates(
        self,
        *,
        timestamp: datetime,
        spot_price_cents_per_kwh: float | None,
    ) -> ActiveTariffRates:
        """Resolve active tariff values for a single measurement window."""
        import_margin = self.import_retailer_margin_cents_per_kwh
        import_transfer = self.grid_import_transfer_fee_cents_per_kwh
        tariff_period = self.tariff_mode
        if self.tariff_mode == TARIFF_MODE_DAY_NIGHT:
            if _is_day_period(timestamp):
                import_margin = self.day_import_retailer_margin_cents_per_kwh
                import_transfer = self.day_grid_import_transfer_fee_cents_per_kwh
                tariff_period = "day"
            else:
                import_margin = self.night_import_retailer_margin_cents_per_kwh
                import_transfer = self.night_grid_import_transfer_fee_cents_per_kwh
                tariff_period = "night"
        elif self.tariff_mode == TARIFF_MODE_SEASONAL_DAY_NIGHT:
            if _is_seasonal_day_period(timestamp):
                import_margin = self.day_import_retailer_margin_cents_per_kwh
                import_transfer = self.day_grid_import_transfer_fee_cents_per_kwh
                tariff_period = "winter_day"
            else:
                import_margin = self.night_import_retailer_margin_cents_per_kwh
                import_transfer = self.night_grid_import_transfer_fee_cents_per_kwh
                tariff_period = "other"

        import_unit_price = None
        export_unit_price = None
        if spot_price_cents_per_kwh is not None:
            import_unit_price = spot_price_cents_per_kwh + import_margin
            export_unit_price = (
                spot_price_cents_per_kwh
                + self.export_retailer_adjustment_cents_per_kwh
            )

        return ActiveTariffRates(
            tariff_mode=self.tariff_mode,
            tariff_period=tariff_period,
            import_retailer_margin_cents_per_kwh=import_margin,
            import_transfer_fee_cents_per_kwh=import_transfer,
            electricity_tax_cents_per_kwh=self.electricity_tax_cents_per_kwh,
            export_retailer_adjustment_cents_per_kwh=(
                self.export_retailer_adjustment_cents_per_kwh
            ),
            export_transfer_fee_cents_per_kwh=(
                self.grid_export_transfer_fee_cents_per_kwh
            ),
            import_unit_price_cents_per_kwh=import_unit_price,
            export_unit_price_cents_per_kwh=export_unit_price,
        )

    def calculate_monthly_power_fee(
        self,
        *,
        hourly_average_demands_kw: dict[str, float],
    ) -> tuple[float, float]:
        """Return qualifying peak kW and estimated monthly power fee in EUR."""
        if (
            not hourly_average_demands_kw
            or self.power_fee_rule == "none"
            or self.power_fee_rate_eur_per_kw_month <= 0
        ):
            return 0.0, 0.0

        qualifying = [
            demand_kw
            for hour_key, demand_kw in hourly_average_demands_kw.items()
            if self._qualifies_for_power_fee(datetime.fromisoformat(hour_key))
        ]
        if not qualifying:
            return 0.0, 0.0

        qualifying.sort(reverse=True)
        peak_kw = qualifying[0]

        if self.power_fee_rule == POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS:
            fee_basis_kw = peak_kw
        elif self.power_fee_rule in (
            POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
            POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME,
        ):
            fee_basis_kw = sum(qualifying[:3]) / 3
        else:
            fee_basis_kw = 0.0

        return peak_kw, fee_basis_kw * self.power_fee_rate_eur_per_kw_month

    def _qualifies_for_power_fee(self, timestamp: datetime) -> bool:
        """Return True when a given hour qualifies for the selected rule."""
        if self.power_fee_rule in (
            POWER_FEE_RULE_MONTHLY_MAX_ALL_HOURS,
            POWER_FEE_RULE_MONTHLY_TOP3_ALL_HOURS,
        ):
            return True
        if (
            self.power_fee_rule
            == POWER_FEE_RULE_MONTHLY_TOP3_WINTER_WEEKDAY_DAYTIME
        ):
            return (
                timestamp.month in _WINTER_MONTHS
                and timestamp.weekday() < 5
                and _is_day_period(timestamp)
            )
        return False


def cents_per_kwh_to_eur(amount_cents_per_kwh: float, energy_kwh: float) -> float:
    """Convert c/kWh pricing into EUR for the given energy."""
    return amount_cents_per_kwh * energy_kwh / 100


def normalize_tariff_options(options: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Return tariff options with any preset applied."""
    normalized = dict(options)
    preset_key = str(normalized.get(CONF_TARIFF_PRESET, DEFAULT_TARIFF_PRESET))
    normalized[CONF_TARIFF_PRESET] = preset_key
    if preset_key == TARIFF_PRESET_CUSTOM:
        return normalized

    preset = get_tariff_preset(preset_key)
    if preset is None:
        return normalized

    normalized[CONF_TARIFF_MODE] = preset.tariff_mode
    if preset.tariff_mode == TARIFF_MODE_FLAT:
        normalized[CONF_GRID_IMPORT_TRANSFER_FEE] = (
            preset.grid_import_transfer_fee_cents_per_kwh
        )
        normalized.setdefault(
            CONF_DAY_GRID_IMPORT_TRANSFER_FEE,
            preset.day_grid_import_transfer_fee_cents_per_kwh,
        )
        normalized.setdefault(
            CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE,
            preset.night_grid_import_transfer_fee_cents_per_kwh,
        )
    elif preset.tariff_mode in (
        TARIFF_MODE_DAY_NIGHT,
        TARIFF_MODE_SEASONAL_DAY_NIGHT,
    ):
        normalized[CONF_DAY_GRID_IMPORT_TRANSFER_FEE] = (
            preset.day_grid_import_transfer_fee_cents_per_kwh
        )
        normalized[CONF_NIGHT_GRID_IMPORT_TRANSFER_FEE] = (
            preset.night_grid_import_transfer_fee_cents_per_kwh
        )
        normalized[CONF_GRID_IMPORT_TRANSFER_FEE] = (
            preset.grid_import_transfer_fee_cents_per_kwh
        )

    return normalized


def get_tariff_preset(key: str) -> TariffPreset | None:
    """Return a tariff preset by key."""
    return _TARIFF_PRESETS.get(key)


def tariff_preset_keys() -> tuple[str, ...]:
    """Return available preset keys in a stable order."""
    return (TARIFF_PRESET_CUSTOM, *tuple(_TARIFF_PRESETS))


def _is_day_period(timestamp: datetime) -> bool:
    """Return True for the default Finnish day tariff window."""
    return _DAY_START_HOUR <= timestamp.hour < _DAY_END_HOUR


def _is_seasonal_day_period(timestamp: datetime) -> bool:
    """Return True for Caruna-style winter daytime seasonal pricing."""
    return (
        timestamp.month in _WINTER_MONTHS
        and timestamp.weekday() < 6
        and _is_day_period(timestamp)
    )
