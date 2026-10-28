# Coordinator for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""DataUpdateCoordinator polling the EMPS /health endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import time

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    EmpsApiClient,
    EmpsApiAuthError,
    EmpsApiConnectionError,
    EmpsHealth,
)
from .const import LOGGER


@dataclass
class EmpsState:
    """Snapshot of service health plus the last print result."""

    health: EmpsHealth
    last_print_bytes: int | None = None
    last_print_at: float | None = None
    last_print_error: str | None = None


class EmpsCoordinator(DataUpdateCoordinator[EmpsState]):
    """Poll /health and remember the result of the most recent print."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EmpsApiClient,
        update_interval: int,
    ) -> None:
        """Create the coordinator; the client is fully constructed."""
        super().__init__(
            hass,
            LOGGER,
            name="emps",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self._last_print_bytes: int | None = None
        self._last_print_at: float | None = None
        self._last_print_error: str | None = None

    async def _async_update_data(self) -> EmpsState:
        """Fetch the current health snapshot."""
        try:
            health = await self.client.async_health()
        except EmpsApiAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EmpsApiConnectionError as err:
            raise UpdateFailed(f"EMPS unreachable: {err}") from err
        return EmpsState(
            health=health,
            last_print_bytes=self._last_print_bytes,
            last_print_at=self._last_print_at,
            last_print_error=self._last_print_error,
        )

    async def async_record_print(self, nbytes: int) -> None:
        """Record a successful print and refresh state."""
        self._last_print_bytes = nbytes
        self._last_print_at = time.time()
        self._last_print_error = None
        await self.async_refresh()

    def record_print_error(self, detail: str) -> None:
        """Record a failed print; the next poll picks it up."""
        self._last_print_error = detail


class EmpsEntity(CoordinatorEntity[EmpsCoordinator]):
    """Base entity wired to the coordinator and config entry."""
