"""Tests for Elisa Kotiakku diagnostics."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock

import pytest

from custom_components.elisa_kotiakku.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import SAMPLE_MEASUREMENT


@pytest.fixture
def mock_entry_with_coordinator(
    mock_config_entry: MagicMock,
    mock_coordinator: MagicMock,
) -> MagicMock:
    """Return a config entry with coordinator attached as runtime_data."""
    mock_config_entry.runtime_data = mock_coordinator
    return mock_config_entry


class TestDiagnostics:
    """Tests for diagnostics output."""

    async def test_api_key_is_redacted(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """API key must be redacted in diagnostics output."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["config"]["api_key"] == "**REDACTED**"

    async def test_measurement_data_included(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Latest measurement is included as a dict."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        measurement = result["latest_measurement"]
        assert measurement is not None
        assert measurement["battery_power_kw"] == -2.727
        assert measurement["period_start"] == "2025-12-17T00:00:00+02:00"
        assert measurement["spot_price_cents_per_kwh"] == 1.87

    async def test_handles_none_measurement(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """None measurement is serialised as None."""
        mock_entry_with_coordinator.runtime_data.data = None
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert result["latest_measurement"] is None

    async def test_output_structure(
        self, mock_entry_with_coordinator: MagicMock
    ) -> None:
        """Output has expected top-level keys."""
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(
            hass, mock_entry_with_coordinator
        )

        assert "config" in result
        assert "latest_measurement" in result
        assert len(result) == 2
