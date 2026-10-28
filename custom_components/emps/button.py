# Button entities for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""Button entity that prints the EMPS test page."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EmpsApiPrinterError
from . import EmpsConfigEntry
from .coordinator import EmpsCoordinator
from .entity import EmpsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the test page button."""
    coordinator: EmpsCoordinator = entry.runtime_data
    name = f"EMPS {entry.data['host']}"
    async_add_entities([EmpsTestPageButton(coordinator, name)])


class EmpsTestPageButton(EmpsDeviceEntity, ButtonEntity):
    """Press to print the built-in EMPS test page."""

    _attr_icon = "mdi:file-document-outline"

    def __init__(self, coordinator: EmpsCoordinator, name: str) -> None:
        """Configure the button."""
        super().__init__(coordinator, name)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_test_page"
        self._attr_name = f"{name} test page"

    async def async_press(self) -> None:
        """POST /print/test."""
        try:
            nbytes = await self.coordinator.client.async_print_test()
        except EmpsApiPrinterError as err:
            await self.coordinator.async_refresh()
            raise HomeAssistantError(f"Printer error: {err}") from err
        await self.coordinator.async_record_print(nbytes)
