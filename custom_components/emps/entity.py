# Entities for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""Common entity base with device info."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import EmpsCoordinator, EmpsEntity


class EmpsDeviceEntity(EmpsEntity):
    """Entity attached to the EMPS device of a config entry."""

    def __init__(self, coordinator: EmpsCoordinator, name: str) -> None:
        """Set up device info and identifiers."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer="EMPS",
            entry_type=DeviceEntryType.SERVICE,
        )
