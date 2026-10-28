# Constants for the EMPS integration.
from __future__ import annotations

import logging

DOMAIN = "emps"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TOKEN = "token"

DEFAULT_PORT = 8000

MIN_POLL_INTERVAL = 30
MAX_POLL_INTERVAL = 3600
DEFAULT_POLL_INTERVAL = 60

CONF_POLL_INTERVAL = "poll_interval"

PLATFORMS = ["sensor", "button"]

MAX_MARKDOWN_LENGTH = 20_000

PRINTER_STATE_UNKNOWN = "unknown"
PRINTER_STATE_OK = "ok"
PRINTER_STATE_ERROR = "error"

LOGGER = logging.getLogger(__package__)
