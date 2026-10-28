# Config flow for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""UI configuration flow for EMPS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    EmpsApiClient,
    EmpsApiAuthError,
    EmpsApiConnectionError,
    EmpsApiError,
)
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=8000): int,
        vol.Optional(CONF_TOKEN): str,
    }
)


class EmpsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the EMPS config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host/port/token and validate by calling /health."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            client = EmpsApiClient(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_TOKEN),
            )
            try:
                await client.async_health()
            except EmpsApiAuthError:
                errors["base"] = "invalid_auth"
            except EmpsApiConnectionError:
                errors["base"] = "cannot_connect"
            except EmpsApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"EMPS {user_input[CONF_HOST]}",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Any,
    ) -> EmpsOptionsFlow:
        """Return the options flow handler."""
        return EmpsOptionsFlow()


class EmpsOptionsFlow(OptionsFlow):
    """Options: poll interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            interval = user_input[CONF_POLL_INTERVAL]
            if not MIN_POLL_INTERVAL <= interval <= MAX_POLL_INTERVAL:
                errors["base"] = "invalid_poll_interval"
            else:
                return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL, default=current, description="Poll interval (s)"
                ): int,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
