# ESCPOS Markdown Printing Service (EMPS): HTTP service that translates
# markdown to ESC/POS and prints it on a USB receipt printer.
# Copyright (C) 2026 Jeroen Vermeylen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""Printer backends: raw byte sinks for ESC/POS output.

FileBackend writes the raw byte stream to a file (testing / dry runs).
UsbBackend sends the bytes to a USB printer via python-escpos.
"""

from __future__ import annotations

from typing import Protocol

from emps.config import Settings


class PrinterBackend(Protocol):
    def send(self, data: bytes) -> None:
        """Send a complete ESC/POS byte stream to the printer."""
        ...


class FileBackend:
    def __init__(self, path: str) -> None:
        self.path = path

    def send(self, data: bytes) -> None:
        with open(self.path, "ab") as f:
            f.write(data)


class UsbBackend:
    def __init__(self, settings: Settings) -> None:
        # Imported lazily so the file backend works without libusb installed.
        from escpos.printer import Usb

        self._printer = Usb(
            settings.usb_vendor_id,
            settings.usb_product_id,
            profile="TM-T88II",
        )

    def send(self, data: bytes) -> None:
        self._printer._raw(data)


def make_backend(settings: Settings) -> PrinterBackend:
    if settings.backend == "usb":
        return UsbBackend(settings)
    if settings.backend == "file":
        return FileBackend(settings.file_backend_path)
    raise ValueError(f"Unknown printer backend: {settings.backend!r}")
