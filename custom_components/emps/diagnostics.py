# Diagnostics for the EMPS integration.
#
# Copyright (C) 2026 Jeroen Vermeylen. GPL-3.0-or-later.
"""Redacted diagnostics for an EMPS config entry."""

from __future__ import annotations

from typing import Any

from . import EmpsConfigEntry


def async_get_config_entry_diagnostics(
    entry: EmpsConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics with the token masked."""
    data = dict(entry.data)
    if "token" in data:
        data["token"] = "**REDACTED**"
    coordinator = entry.runtime_data
    state = coordinator.data
    return {
        "entry": data,
        "health": {
            "status": state.health.status,
            "backend": state.health.backend,
            "printer": state.health.printer,
            "last_error": state.health.last_error,
            "version": state.health.version,
        },
        "last_print_bytes": state.last_print_bytes,
        "last_print_at": state.last_print_at,
        "last_print_error": state.last_print_error,
    }
