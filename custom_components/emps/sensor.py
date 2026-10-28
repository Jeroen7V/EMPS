# Sensors for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""Sensor entities for printer status, backend, and last print."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EmpsConfigEntry
from .const import PRINTER_STATE_ERROR, PRINTER_STATE_OK
from .coordinator import EmpsCoordinator
from .entity import EmpsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add all EMPS sensors."""
    coordinator: EmpsCoordinator = entry.runtime_data
    name = f"EMPS {entry.data['host']}"
    async_add_entities(
        [
            EmpsPrinterStatusSensor(coordinator, name),
            EmpsBackendSensor(coordinator, name),
            EmpsLastPrintSensor(coordinator, name),
        ]
    )


class EmpsPrinterStatusSensor(EmpsDeviceEntity, SensorEntity):
    """Printer status from the last print attempt."""

    _attr_icon = "mdi:printer"

    def __init__(self, coordinator: EmpsCoordinator, name: str) -> None:
        """Configure the status sensor."""
        super().__init__(coordinator, name)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_printer_status"
        self._attr_name = f"{name} printer status"

    @property
    def native_value(self) -> str:
        """Map the service state to a sensor value."""
        printer = self.coordinator.data.health.printer
        if printer == PRINTER_STATE_OK:
            return "ok"
        if printer == PRINTER_STATE_ERROR:
            return "error"
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose the last printer error detail."""
        return {"last_error": self.coordinator.data.health.last_error}


class EmpsBackendSensor(EmpsDeviceEntity, SensorEntity):
    """Which backend the service uses (file/usb)."""

    _attr_icon = "mdi:harddisk-plus"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EmpsCoordinator, name: str) -> None:
        """Configure the backend sensor."""
        super().__init__(coordinator, name)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_backend"
        self._attr_name = f"{name} backend"

    @property
    def native_value(self) -> str:
        """Return the backend name."""
        return self.coordinator.data.health.backend


class EmpsLastPrintSensor(EmpsDeviceEntity, SensorEntity):
    """Size in bytes of the most recent successful print."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "B"

    def __init__(self, coordinator: EmpsCoordinator, name: str) -> None:
        """Configure the last-print sensor."""
        super().__init__(coordinator, name)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_last_print_bytes"
        self._attr_name = f"{name} last print"

    @property
    def native_value(self) -> int | None:
        """Return the last print size, if any."""
        return self.coordinator.data.last_print_bytes
