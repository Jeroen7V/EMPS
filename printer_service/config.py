# markdown-escpos-printer: HTTP service that prints markdown on a USB
# ESC/POS receipt printer.
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
"""Application configuration, loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_WIDTH_CHARS = 32  # 58 mm paper (80 mm paper is 48 chars)


@dataclass(frozen=True)
class Settings:
    paper_width_chars: int = DEFAULT_WIDTH_CHARS
    usb_vendor_id: int = 0x28E9  # GDMicroelectronics YC Printer
    usb_product_id: int = 0x0289
    backend: str = "file"  # "file" or "usb"
    file_backend_path: str = "/tmp/escpos-output.bin"


def load_settings() -> Settings:
    return Settings(
        paper_width_chars=int(os.environ.get("PAPER_WIDTH_CHARS", DEFAULT_WIDTH_CHARS)),
        usb_vendor_id=int(os.environ.get("USB_VENDOR_ID", "0x28E9"), 0),
        usb_product_id=int(os.environ.get("USB_PRODUCT_ID", "0x0289"), 0),
        backend=os.environ.get("PRINTER_BACKEND", "file"),
        file_backend_path=os.environ.get("PRINTER_OUTPUT_FILE", "/tmp/escpos-output.bin"),
    )
