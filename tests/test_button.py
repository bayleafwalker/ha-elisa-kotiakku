"""Tests for the Elisa Kotiakku button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.elisa_kotiakku.button import (
    BUTTON_DESCRIPTIONS,
    PARALLEL_UPDATES,
    ElisaKotiakkuButton,
    async_setup_entry,
)


class TestButtonDescriptions:
    """Tests for button entity descriptions."""

    EXPECTED_KEYS = {
        "backfill_energy",
        "rebuild_economics",
        "force_data_refresh",
    }

    def test_all_expected_buttons_defined(self) -> None:
        keys = {d.key for d in BUTTON_DESCRIPTIONS}
        assert keys == self.EXPECTED_KEYS

    def test_count(self) -> None:
        assert len(BUTTON_DESCRIPTIONS) == 3

    def test_all_have_translation_key(self) -> None:
        for desc in BUTTON_DESCRIPTIONS:
            assert desc.translation_key == desc.key

    def test_all_diagnostic_category(self) -> None:
        from homeassistant.const import EntityCategory

        for desc in BUTTON_DESCRIPTIONS:
            assert desc.entity_category == EntityCategory.DIAGNOSTIC

    def test_parallel_updates(self) -> None:
        assert PARALLEL_UPDATES == 1


class TestButtonSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_creates_all_buttons(
        self, mock_coordinator: MagicMock
    ) -> None:
        entry = mock_coordinator.config_entry
        entry.runtime_data = mock_coordinator

        added: list = []
        hass = MagicMock()
        async_add_entities = MagicMock(
            side_effect=lambda entities: added.extend(entities)
        )

        await async_setup_entry(hass, entry, async_add_entities)

        assert async_add_entities.call_count == 1
        assert len(added) == 3
        keys = {e.entity_description.key for e in added}
        assert keys == {"backfill_energy", "rebuild_economics", "force_data_refresh"}


class TestElisaKotiakkuButton:
    """Tests for individual button entities."""

    def _make_button(
        self, mock_coordinator: MagicMock, key: str
    ) -> ElisaKotiakkuButton:
        desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == key)
        return ElisaKotiakkuButton(mock_coordinator, desc)

    def test_unique_id(self, mock_coordinator: MagicMock) -> None:
        button = self._make_button(mock_coordinator, "backfill_energy")
        assert button.unique_id == "test_entry_id_backfill_energy"

    def test_entity_description(self, mock_coordinator: MagicMock) -> None:
        button = self._make_button(mock_coordinator, "rebuild_economics")
        assert button.entity_description.key == "rebuild_economics"

    @pytest.mark.asyncio
    async def test_backfill_energy_press(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.async_backfill_energy = AsyncMock(return_value=5)
        button = self._make_button(mock_coordinator, "backfill_energy")

        await button.async_press()

        mock_coordinator.async_backfill_energy.assert_awaited_once()
        call_kwargs = mock_coordinator.async_backfill_energy.call_args
        assert "start_time" in call_kwargs.kwargs or len(call_kwargs.args) >= 1

    @pytest.mark.asyncio
    async def test_backfill_energy_press_error(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.async_backfill_energy = AsyncMock(
            side_effect=Exception("API error")
        )
        button = self._make_button(mock_coordinator, "backfill_energy")

        with pytest.raises(HomeAssistantError, match="Backfill energy failed"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_rebuild_economics_press(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.async_rebuild_economics = AsyncMock(return_value=10)
        button = self._make_button(mock_coordinator, "rebuild_economics")

        await button.async_press()

        mock_coordinator.async_rebuild_economics.assert_awaited_once()
        call_kwargs = mock_coordinator.async_rebuild_economics.call_args
        assert "start_time" in call_kwargs.kwargs or len(call_kwargs.args) >= 1

    @pytest.mark.asyncio
    async def test_rebuild_economics_press_error(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.async_rebuild_economics = AsyncMock(
            side_effect=Exception("Rebuild error")
        )
        button = self._make_button(mock_coordinator, "rebuild_economics")

        with pytest.raises(HomeAssistantError, match="Rebuild economics failed"):
            await button.async_press()

    @pytest.mark.asyncio
    async def test_force_data_refresh_press(
        self, mock_coordinator: MagicMock
    ) -> None:
        mock_coordinator.async_request_refresh = AsyncMock()
        button = self._make_button(mock_coordinator, "force_data_refresh")

        await button.async_press()

        mock_coordinator.async_request_refresh.assert_awaited_once()

    def test_device_info(self, mock_coordinator: MagicMock) -> None:
        button = self._make_button(mock_coordinator, "backfill_energy")
        info = button.device_info
        assert ("elisa_kotiakku", "test_entry_id") in info["identifiers"]
