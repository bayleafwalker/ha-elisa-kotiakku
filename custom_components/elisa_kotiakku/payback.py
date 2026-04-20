"""Payback and monthly profitability helper calculations."""

from __future__ import annotations

import calendar
from datetime import datetime


def effective_monthly_cost(
    *,
    battery_monthly_cost: float,
    battery_total_cost: float,
    akkureservihyvitys: float,
) -> float | None:
    """Return effective monthly cost after akkureservi compensation.

    A direct monthly cost is treated as the already-effective aggregate value.
    Akkureservihyvitys only adjusts the derived monthly cost path based on the
    total battery cost.
    """
    if battery_monthly_cost > 0:
        return battery_monthly_cost
    if battery_total_cost > 0:
        derived = battery_total_cost / 120.0
        return derived - akkureservihyvitys
    return None


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
