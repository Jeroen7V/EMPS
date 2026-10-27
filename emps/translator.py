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
"""Translate markdown to a raw ESC/POS byte stream.

Uses mistune's token output. Emits standard Epson ESC/POS commands so the
result can be sent verbatim to any ESC/POS printer:

- ESC @            initialize
- ESC E n          bold on/off
- ESC 4 / ESC 5    italic on/off
- ESC - n          underline on/off
- GS B n           reverse video on/off (used for strikethrough)
- GS ! n           character size (width/height)
- ESC a n          alignment (not used; everything is left-aligned)
- GS V 66 n        partial cut with feed
"""

from __future__ import annotations

import re
import textwrap

import mistune

ESC = b"\x1b"
GS = b"\x1d"

_BOLD_ON = ESC + b"E\x01"
_BOLD_OFF = ESC + b"E\x00"
_ITALIC_ON = ESC + b"4"
_ITALIC_OFF = ESC + b"5"
_UNDERLINE_ON = ESC + b"-\x01"
_UNDERLINE_OFF = ESC + b"-\x00"
_REVERSE_ON = GS + b"B\x01"
_REVERSE_OFF = GS + b"B\x00"
_INIT = ESC + b"@"
_SIZE_NORMAL = GS + b"!\x00"
_SIZE_DOUBLE_HEIGHT = GS + b"!\x01"
_SIZE_DOUBLE_BOTH = GS + b"!\x11"
_CUT_PARTIAL = GS + b"V\x42\x00"

_BULLET = "*"  # ASCII: this printer renders only the low code page reliably
_CHECKBOX_ON = "[x] "
_CHECKBOX_OFF = "[ ] "
_CODE_INDENT = "  "
_LIST_INDENT = "  "

_BOLD = 1
_ITALIC = 2
_UNDERLINE = 4
_STRIKETHROUGH = 8

_STYLE_COMMANDS = {
    _BOLD: (_BOLD_ON, _BOLD_OFF),
    _ITALIC: (_ITALIC_ON, _ITALIC_OFF),
    _UNDERLINE: (_UNDERLINE_ON, _UNDERLINE_OFF),
    _STRIKETHROUGH: (_REVERSE_ON, _REVERSE_OFF),
}


class MarkdownToEscpos:
    def __init__(self, width: int = 32, encoding: str = "cp437", feed_lines: int = 3) -> None:
        self.width = width
        self.encoding = encoding
        self.feed_lines = feed_lines
        self._md = mistune.create_markdown(renderer=None, plugins=["task_lists", "strikethrough"])

    # ------------------------------------------------------------------ API

    def translate(self, markdown: str) -> bytes:
        """Convert a markdown document to ESC/POS bytes, ending with a cut."""
        out = bytearray(_INIT)
        for token in self._md(markdown):
            self._block(token, out)
        out += b"\n" * self.feed_lines
        out += _CUT_PARTIAL
        return bytes(out)

    # ---------------------------------------------------------------- blocks

    def _block(self, token: dict, out: bytearray) -> None:
        kind = token["type"]
        if kind == "heading":
            self._heading(token, out)
        elif kind == "paragraph":
            self._paragraph(token, out)
        elif kind == "list":
            self._list(token, out, depth=0)
        elif kind == "block_code":
            self._code_block(token, out)
        elif kind == "thematic_break":
            self._separator(out)
        elif kind == "block_quote":
            self._quote(token, out)
        elif kind == "blank_line":
            pass  # spacing is emitted per block instead
        elif "raw" in token:  # html and other raw blocks: print the text
            self._text(token["raw"].strip(), out)
        out += b"\n"  # one blank line after every block

    def _heading(self, token: dict, out: bytearray) -> None:
        level = token.get("attrs", {}).get("level", 1)
        if level == 1:
            out += _SIZE_DOUBLE_BOTH
        elif level == 2:
            out += _SIZE_DOUBLE_HEIGHT
        # force the heading text bold; double width halves the chars per line
        segments = [(text, style | _BOLD) for text, style in self._inline(token["children"])]
        wrap_width = self.width // 2 if level == 1 else self.width
        for line in self._wrap(segments, wrap_width):
            self._emit_line(line, out, "")
        if level <= 2:
            out += _SIZE_NORMAL

    def _paragraph(self, token: dict, out: bytearray) -> None:
        self._emit_inline(token["children"], out)

    def _quote(self, token: dict, out: bytearray) -> None:
        # block_quote children are block tokens (paragraph etc.)
        for child in token["children"]:
            if child["type"] in ("paragraph", "block_text"):
                segments = self._inline(child["children"])
                for line in self._wrap(segments, self.width - 2, subsequent="  "):
                    self._emit_line(line, out, "> ")
            elif child["type"] == "block_quote":
                self._quote(child, out)
            else:
                self._block(child, out)

    def _list(self, token: dict, out: bytearray, depth: int) -> None:
        indent = _LIST_INDENT * depth
        ordered = token.get("attrs", {}).get("ordered", False)
        for index, item in enumerate(token["children"], start=1):
            if item["type"] == "task_list_item":
                marker = _CHECKBOX_ON if item.get("attrs", {}).get("checked") else _CHECKBOX_OFF
            elif ordered:
                marker = f"{index}. "
            else:
                marker = _BULLET + " "
            marker_pad = indent + " " * len(marker)
            first = True
            for child in item["children"]:
                if child["type"] in ("block_text", "paragraph"):
                    segments = self._inline(child["children"])
                    lines = self._wrap(segments, self.width, subsequent=marker_pad)
                    for i, line in enumerate(lines):
                        prefix = indent + marker if (i == 0 and first) else marker_pad
                        self._emit_line(line, out, prefix)
                        first = False
                elif child["type"] == "list":
                    self._list(child, out, depth + 1)
                else:
                    self._block(child, out)

    def _code_block(self, token: dict, out: bytearray) -> None:
        for line in token["raw"].rstrip("\n").split("\n"):
            self._emit_line([(line, False, False)], out, _CODE_INDENT)

    def _separator(self, out: bytearray) -> None:
        out += self._enc("-" * self.width) + b"\n"

    # ---------------------------------------------------------------- inline

    def _inline(self, children: list[dict]) -> list[tuple[str, int]]:
        """Flatten inline tokens to (text, style) segments with a style
        bitmask (bold/italic/underline/strikethrough). Links print their text
        only; <u>/</u> inline HTML toggles underline."""
        segments: list[tuple[str, int]] = []
        underline = False
        for token in children:
            kind = token["type"]
            if kind in ("text", "codespan"):
                segments.append((token["raw"], _UNDERLINE if underline else 0))
            elif kind == "inline_html":
                raw = token["raw"].strip().lower()
                if raw == "<u>":
                    underline = True
                elif raw == "</u>":
                    underline = False
            elif kind == "strong":
                for text, style in self._inline(token["children"]):
                    segments.append((text, style | _BOLD))
            elif kind == "emphasis":
                for text, style in self._inline(token["children"]):
                    segments.append((text, style | _ITALIC))
            elif kind == "strikethrough":
                for text, style in self._inline(token["children"]):
                    segments.append((text, style | _STRIKETHROUGH))
            elif kind == "link":
                segments.extend(self._inline(token["children"]))
            elif kind == "linebreak":
                segments.append(("\n", 0))
            elif kind == "softbreak":
                segments.append((" ", 0))
        return segments

    def _emit_inline(self, children: list[dict], out: bytearray) -> None:
        for line in self._wrap(self._inline(children), self.width):
            self._emit_line(line, out, "")

    def _emit_line(
        self,
        line: list[tuple[str, int, bool]],
        out: bytearray,
        prefix: str,
    ) -> None:
        """line items are (word, style, preceded_by_space) tuples."""
        out += self._enc(prefix)
        style_state = 0
        for index, (text, style, preceded_by_space) in enumerate(line):
            if index > 0 and preceded_by_space:
                out += b" "
            if style != style_state:
                out += self._style_bytes(style_state, style)
                style_state = style
            out += self._enc(text)
        if style_state:
            out += self._style_bytes(style_state, 0)
        out += b"\n"

    @staticmethod
    def _style_bytes(old: int, new: int) -> bytes:
        """Commands that transition the printer from style old to new."""
        commands = bytearray()
        for flag, (on, off) in _STYLE_COMMANDS.items():
            if old & flag and not new & flag:
                commands += off
            elif new & flag and not old & flag:
                commands += on
        return bytes(commands)

    def _enc(self, text: str) -> bytes:
        return text.encode(self.encoding, errors="replace")

    # ------------------------------------------------------------------ wrap

    def _wrap(
        self, segments: list[tuple[str, int]], width: int, subsequent: str = ""
    ) -> list[list[tuple[str, bool, bool]]]:
        """Greedy word wrap of (text, style) segments. Returns lines, each a
        list of (word, style, preceded_by_space) tuples. Original spacing
        between words is preserved; hard newlines force a break; words longer
        than the line are hard-split."""
        hard_lines: list[list[tuple[str, int]]] = [[]]
        for text, style in segments:
            for i, piece in enumerate(text.split("\n")):
                if i > 0:
                    hard_lines.append([])
                if piece:
                    hard_lines[-1].append((piece, style))

        lines: list[list[tuple[str, bool, bool]]] = []
        for parts in hard_lines:
            words: list[tuple[str, bool, bool]] = []
            pending_space = False
            for text, style in parts:
                for piece in re.split(r"(\s+)", text):
                    if not piece:
                        continue
                    if piece.isspace():
                        pending_space = True
                    else:
                        words.append((piece, style, pending_space))
                        pending_space = False

            current: list[tuple[str, bool, bool]] = []
            used = 0
            indent = 0
            for word, style, preceded_by_space in words:
                avail = width - indent
                if len(word) > avail:
                    if current:
                        lines.append(current)
                    # hard-split words wider than a whole line
                    while len(word) > width:
                        lines.append([(word[:width], style, False)])
                        word = word[width:]
                    current = [(word, style, False)]
                    used = len(word)
                    indent = len(subsequent)
                    continue
                space = 1 if (preceded_by_space and current) else 0
                if current and used + space + len(word) > width - indent:
                    lines.append(current)
                    current = []
                    used = 0
                    indent = len(subsequent)
                    space = 0
                current.append((word, style, preceded_by_space and space == 1))
                used += space + len(word)
            if current:
                lines.append(current)
        return lines
