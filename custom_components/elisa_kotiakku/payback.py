"""Payback and monthly profitability helper calculations."""

from __future__ import annotations

import calendar
from datetime import datetime

from .const import (
    BATTERY_COST_BASES,
    BATTERY_COST_BASIS_INSTALMENT,
    BATTERY_COST_BASIS_TOTAL_COST,
    BATTERY_TOTAL_COST_MONTHS,
)


def resolve_battery_cost_basis(
    *,
    battery_cost_basis: str | None,
    battery_monthly_cost: float,
    battery_total_cost: float,
) -> str:
    """Return the configured cost basis, defaulting entries saved before v1.6.0.

    Entries without an explicit basis use ``instalment`` when a monthly
    instalment is configured, otherwise ``total_cost``. With neither input
    configured ``total_cost`` is returned, which yields no effective cost.
    """
    if battery_cost_basis in BATTERY_COST_BASES:
        return str(battery_cost_basis)
    if battery_monthly_cost > 0:
        return BATTERY_COST_BASIS_INSTALMENT
    return BATTERY_COST_BASIS_TOTAL_COST


def effective_monthly_cost(
    *,
    battery_cost_basis: str,
    battery_monthly_cost: float,
    battery_total_cost: float,
    akkureservihyvitys: float,
) -> float | None:
    """Return the net monthly battery cost after akkureservihyvitys.

    The gross monthly cost comes from the selected basis: the gross monthly
    instalment (``instalment``; 0 means paid off) or the total battery cost
    spread over 120 months (``total_cost``). Akkureservihyvitys is always
    subtracted, so the result may be negative when the compensation exceeds
    the gross cost. ``None`` is returned only when the basis has no usable
    input (``total_cost`` with a total cost of 0 or less).

    This is a monthly-profitability figure only; payback uses the total cost
    with compensation as a benefit (see ``payback_remaining_months``) and does
    not consume this value, so compensation is never counted twice.
    """
    if battery_cost_basis == BATTERY_COST_BASIS_INSTALMENT:
        gross = max(battery_monthly_cost, 0.0)
    elif battery_total_cost > 0:
        gross = battery_total_cost / BATTERY_TOTAL_COST_MONTHS
    else:
        return None
    return gross - akkureservihyvitys


def monthly_first_day_of_profit(
    *,
    monthly_cost: float | None,
    month_savings: float,
    timestamp: datetime,
) -> int | None:
    """Estimate first profitable day in current month using linear interpolation."""
    if monthly_cost is None:
        return None
    if monthly_cost <= 0:
        return 1
    if month_savings <= 0:
        return None

    current_day = timestamp.day
    if current_day == 0:
        return None

    daily_rate = month_savings / current_day
    if daily_rate <= 0:
        return None

    breakeven_day = monthly_cost / daily_rate
    days_in_month = calendar.monthrange(timestamp.year, timestamp.month)[1]
    if breakeven_day > days_in_month:
        return None

    return max(1, min(int(breakeven_day) + 1, days_in_month))


def payback_remaining_months(
    *,
    battery_total_cost: float,
    total_battery_savings: float,
    tracked_months: int,
    akkureservihyvitys: float,
) -> float | None:
    """Estimate remaining months until total battery cost is recovered."""
    if battery_total_cost <= 0:
        return None

    akkureservi_total = akkureservihyvitys * tracked_months
    effective_savings = total_battery_savings + akkureservi_total
    if effective_savings <= 0:
        return None

    remaining = battery_total_cost - effective_savings
    if remaining <= 0:
        return 0.0

    if tracked_months == 0:
        return None

    avg_energy_savings = total_battery_savings / tracked_months
    effective_monthly_rate = avg_energy_savings + akkureservihyvitys
    if effective_monthly_rate <= 0:
        return None

    return round(remaining / effective_monthly_rate, 1)
