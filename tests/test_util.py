"""Tests for shared utility helpers."""

from __future__ import annotations

import pytest

from custom_components.elisa_kotiakku.const import DEFAULT_WINDOW_HOURS
from custom_components.elisa_kotiakku.util import (
    measurement_duration_hours,
    parse_iso8601,
)


class TestParseIso8601:
    """Tests for parse_iso8601."""

    def test_valid_utc(self) -> None:
        """Parse a valid UTC timestamp."""
        dt = parse_iso8601("2025-06-15T12:00:00+00:00")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6
        assert dt.hour == 12

    def test_valid_with_offset(self) -> None:
        """Parse a valid timestamp with timezone offset."""
        dt = parse_iso8601("2025-12-17T00:00:00+02:00")
        assert dt is not None
        assert dt.hour == 0

    def test_valid_naive(self) -> None:
        """Parse a valid naive timestamp (no timezone)."""
        dt = parse_iso8601("2025-01-01T00:00:00")
        assert dt is not None
        assert dt.year == 2025

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        assert parse_iso8601("") is None

    def test_garbage_input(self) -> None:
        """Non-date string returns None."""
        assert parse_iso8601("not-a-date") is None

    def test_partial_date(self) -> None:
        """Date-only string parses successfully (Python 3.11+)."""
        dt = parse_iso8601("2025-06-15")
        assert dt is not None
        assert dt.day == 15


class TestMeasurementDurationHours:
    """Tests for measurement_duration_hours."""

    def test_five_minute_window(self) -> None:
        """Standard 5-minute window returns correct hours."""
        result = measurement_duration_hours(
            "2025-12-17T00:00:00+02:00", "2025-12-17T00:05:00+02:00"
        )
        assert result == pytest.approx(5 / 60)

    def test_one_hour_window(self) -> None:
        """One-hour window returns 1.0."""
        result = measurement_duration_hours(
            "2025-12-17T00:00:00+02:00", "2025-12-17T01:00:00+02:00"
        )
        assert result == 1.0

    def test_invalid_start(self) -> None:
        """Invalid start returns default window hours."""
        result = measurement_duration_hours(
            "bad", "2025-12-17T00:05:00+02:00"
        )
        assert result == DEFAULT_WINDOW_HOURS

    def test_invalid_end(self) -> None:
        """Invalid end returns default window hours."""
        result = measurement_duration_hours(
            "2025-12-17T00:00:00+02:00", "bad"
        )
        assert result == DEFAULT_WINDOW_HOURS

    def test_both_invalid(self) -> None:
        """Both invalid returns default window hours."""
        result = measurement_duration_hours("bad", "worse")
        assert result == DEFAULT_WINDOW_HOURS

    def test_zero_duration(self) -> None:
        """Zero-duration (same start and end) returns default window hours."""
        ts = "2025-12-17T00:00:00+02:00"
        result = measurement_duration_hours(ts, ts)
        assert result == DEFAULT_WINDOW_HOURS

    def test_negative_duration(self) -> None:
        """End before start returns default window hours."""
        result = measurement_duration_hours(
            "2025-12-17T01:00:00+02:00", "2025-12-17T00:00:00+02:00"
        )
        assert result == DEFAULT_WINDOW_HOURS
