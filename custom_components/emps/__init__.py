# Setup for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""The EMPS markdown printer integration: setup, unload, services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EmpsApiClient,
    EmpsApiAuthError,
    EmpsApiConnectionError,
    EmpsApiError,
    EmpsApiInvalidPayloadError,
    EmpsApiPrinterError,
)
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_MARKDOWN_LENGTH,
    PLATFORMS,
)
from .coordinator import EmpsCoordinator

type EmpsConfigEntry = ConfigEntry[EmpsCoordinator]

PRINT_MARKDOWN_SCHEMA = vol.Schema(
    {
        vol.Required("config_entry_id"): str,
        vol.Required("markdown"): vol.All(
            str, vol.Length(min=1, max=MAX_MARKDOWN_LENGTH)
        ),
    }
)
PRINT_TEST_SCHEMA = vol.Schema({vol.Required("config_entry_id"): str})


def _client_for(hass: HomeAssistant, entry: ConfigEntry) -> EmpsApiClient:
    return EmpsApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: EmpsConfigEntry
) -> bool:
    """Set up EMPS from a config entry."""
    client = _client_for(hass, entry)
    try:
        health = await client.async_health()
    except EmpsApiAuthError as err:
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except EmpsApiConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to EMPS: {err}") from err

    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    )
    coordinator = EmpsCoordinator(hass, client, poll_interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_platforms(entry, PLATFORMS)
    _register_services(hass)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EmpsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: EmpsConfigEntry
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator_for(hass: HomeAssistant, entry_id: str) -> EmpsCoordinator:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(f"No loaded EMPS config entry {entry_id}")
    coordinator: EmpsCoordinator = entry.runtime_data
    return coordinator


@callback
def _register_services(hass: HomeAssistant) -> None:
    """Register service actions; safe to call repeatedly."""

    async def handle_print(call: ServiceCall) -> dict[str, int]:
        coordinator = _coordinator_for(hass, call.data["config_entry_id"])
        try:
            nbytes = await coordinator.client.async_print(call.data["markdown"])
        except EmpsApiInvalidPayloadError as err:
            coordinator.record_print_error(str(err))
            raise HomeAssistantError(f"Invalid markdown: {err}") from err
        except EmpsApiPrinterError as err:
            coordinator.record_print_error(str(err))
            await coordinator.async_refresh()
            raise HomeAssistantError(f"Printer error: {err}") from err
        except EmpsApiAuthError as err:
            raise HomeAssistantError(f"Authentication failed: {err}") from err
        except EmpsApiConnectionError as err:
            raise HomeAssistantError(f"Cannot reach EMPS: {err}") from err
        await coordinator.async_record_print(nbytes)
        return {"bytes": nbytes}

    async def handle_print_test(call: ServiceCall) -> dict[str, int]:
        coordinator = _coordinator_for(hass, call.data["config_entry_id"])
        try:
            nbytes = await coordinator.client.async_print_test()
        except EmpsApiPrinterError as err:
            await coordinator.async_refresh()
            raise HomeAssistantError(f"Printer error: {err}") from err
        except EmpsApiError as err:
            raise HomeAssistantError(f"Print failed: {err}") from err
        await coordinator.async_record_print(nbytes)
        return {"bytes": nbytes}

    if not hass.services.has_service(DOMAIN, "print_markdown"):
        hass.services.async_register(
            DOMAIN, "print_markdown", handle_print, schema=PRINT_MARKDOWN_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, "print_test_page"):
        hass.services.async_register(
            DOMAIN, "print_test_page", handle_print_test, schema=PRINT_TEST_SCHEMA
        )
