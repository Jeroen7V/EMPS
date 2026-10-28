# Client for the EMPS HTTP service.
#
# Part of the EMPS Home Assistant integration.
# Copyright (C) 2026 Jeroen Vermeylen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Thin async HTTP client for the EMPS markdown printing service."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from .const import MAX_MARKDOWN_LENGTH


class EmpsApiError(Exception):
    """Base error talking to the EMPS service."""


class EmpsApiConnectionError(EmpsApiError):
    """The service is unreachable or returned a transport-level error."""


class EmpsApiInvalidPayloadError(EmpsApiError):
    """The service rejected the markdown payload (HTTP 422)."""


class EmpsApiPrinterError(EmpsApiError):
    """The service failed to print (HTTP 503)."""


class EmpsApiAuthError(EmpsApiError):
    """The service rejected the bearer token (HTTP 401)."""


@dataclass(frozen=True)
class EmpsHealth:
    """Response of GET /health."""

    status: str
    backend: str
    printer: str
    last_error: str | None = None
    version: str | None = None


class EmpsApiClient:
    """Small wrapper around the EMPS HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        token: str | None = None,
    ) -> None:
        """Store connection parameters; no I/O happens here."""
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    @property
    def base_url(self) -> str:
        """Base URL of the service, for logging/diagnostics."""
        return self._base_url

    async def _request(
        self, method: str, path: str, json: dict[str, str] | None = None
    ) -> dict:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                json=json,
                headers=self._headers,
            ) as response:
                body = await response.json()
                if response.status in (400, 422):
                    raise EmpsApiInvalidPayloadError(
                        body.get("detail", "Invalid markdown payload")
                    )
                if response.status == 401:
                    raise EmpsApiAuthError("Invalid or missing bearer token")
                if response.status == 503:
                    raise EmpsApiPrinterError(
                        body.get("detail", "Printer error")
                    )
                response.raise_for_status()
                return body
        except aiohttp.ClientResponseError as err:
            raise EmpsApiError(f"Unexpected response: {err.status}") from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise EmpsApiConnectionError(f"Cannot reach EMPS: {err}") from err

    async def async_health(self) -> EmpsHealth:
        """Fetch GET /health."""
        body = await self._request("GET", "/health")
        return EmpsHealth(
            status=body.get("status", "unknown"),
            backend=body.get("backend", "unknown"),
            printer=body.get("printer", "unknown"),
            last_error=body.get("last_error"),
            version=body.get("version"),
        )

    async def async_print(self, markdown: str) -> int:
        """POST markdown to /print and return the number of bytes printed."""
        if not markdown or len(markdown) > MAX_MARKDOWN_LENGTH:
            raise EmpsApiInvalidPayloadError(
                f"Markdown must be 1-{MAX_MARKDOWN_LENGTH} characters"
            )
        body = await self._request("POST", "/print", {"markdown": markdown})
        return int(body["bytes"])

    async def async_print_test(self) -> int:
        """POST /print/test and return the number of bytes printed."""
        body = await self._request("POST", "/print/test")
        return int(body["bytes"])
