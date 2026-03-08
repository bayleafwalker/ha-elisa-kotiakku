"""Shared utility helpers for Elisa Kotiakku."""

from __future__ import annotations

from datetime import datetime

from .const import DEFAULT_WINDOW_HOURS


def parse_iso8601(value: str) -> datetime | None:
    """Parse ISO 8601 timestamp and return None on malformed input."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def measurement_duration_hours(period_start: str, period_end: str) -> float:
    """Return measurement window duration in hours, with a sane fallback."""
    start = parse_iso8601(period_start)
    end = parse_iso8601(period_end)

    if start is None or end is None:
        return DEFAULT_WINDOW_HOURS

    delta_hours = (end - start).total_seconds() / 3600
    if delta_hours <= 0:
        return DEFAULT_WINDOW_HOURS

    return delta_hours
