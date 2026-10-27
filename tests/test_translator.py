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
from emps.translator import (
    _BOLD_OFF,
    _BOLD_ON,
    _CUT_PARTIAL,
    _INIT,
    _ITALIC_OFF,
    _ITALIC_ON,
    _REVERSE_OFF,
    _REVERSE_ON,
    _SIZE_DOUBLE_BOTH,
    _SIZE_DOUBLE_HEIGHT,
    _SIZE_NORMAL,
    _UNDERLINE_OFF,
    _UNDERLINE_ON,
    MarkdownToEscpos,
)


def make() -> MarkdownToEscpos:
    return MarkdownToEscpos(width=48)


def visible(data: bytes) -> str:
    """Decode with control sequences stripped, for readability assertions."""
    return (
        data.replace(_INIT, b"")
        .replace(_BOLD_ON, b"")
        .replace(_BOLD_OFF, b"")
        .replace(_ITALIC_ON, b"")
        .replace(_ITALIC_OFF, b"")
        .replace(_UNDERLINE_ON, b"")
        .replace(_UNDERLINE_OFF, b"")
        .replace(_REVERSE_ON, b"")
        .replace(_REVERSE_OFF, b"")
        .replace(_SIZE_DOUBLE_BOTH, b"")
        .replace(_SIZE_DOUBLE_HEIGHT, b"")
        .replace(_SIZE_NORMAL, b"")
        .replace(_CUT_PARTIAL, b"")
        .decode("cp437")
    )


class TestStructure:
    def test_starts_with_init_and_ends_with_cut(self):
        data = make().translate("# hi\n")
        assert data.startswith(_INIT)
        assert data.endswith(_CUT_PARTIAL)

    def test_empty_content_still_initializes_and_cuts(self):
        data = make().translate("")
        assert _INIT in data and _CUT_PARTIAL in data


class TestHeadings:
    def test_h1_double_size_bold(self):
        data = make().translate("# Title\n")
        assert _SIZE_DOUBLE_BOTH in data
        assert b"Title" in data

    def test_h2_double_height(self):
        assert _SIZE_DOUBLE_HEIGHT in make().translate("## Sub\n")

    def test_h3_normal_size(self):
        data = make().translate("### Small\n")
        assert _SIZE_DOUBLE_BOTH not in data and _SIZE_DOUBLE_HEIGHT not in data
        assert b"Small" in data

    def test_h1_wrap_width_is_halved(self):
        text = "Heading that is way too long for twenty four characters"
        data = make().translate(f"# {text}\n")
        # every visible line must fit in 24 columns (double width)
        lines = visible(data).splitlines()
        assert max(len(line) for line in lines) <= 24


class TestInline:
    def test_bold(self):
        data = make().translate("**bold** text\n")
        assert _BOLD_ON + b"bold" in data
        assert _BOLD_OFF + b"text" in data  # unbolded before the next word

    def test_italic(self):
        data = make().translate("a *side* here\n")
        assert _ITALIC_ON + b"side" in data
        assert _ITALIC_OFF + b"here" in data

    def test_underline_html_tag(self):
        data = make().translate("a <u>line</u> here\n")
        assert _UNDERLINE_ON + b"line" in data
        assert _UNDERLINE_OFF + b"here" in data

    def test_strikethrough_reverse_video(self):
        data = make().translate("a ~~gone~~ here\n")
        assert _REVERSE_ON + b"gone" in data
        assert _REVERSE_OFF + b"here" in data

    def test_combined_styles(self):
        data = make().translate("**bold *and italic***\n")
        assert _BOLD_ON + b"bold" in data
        assert _ITALIC_ON + b"and" in data  # italic turns on while bold is on
        assert _BOLD_OFF + _ITALIC_OFF in data  # both off at line end

    def test_codespan_text_is_printed(self):
        assert b"extra" in make().translate("order `extra`\n")

    def test_link_prints_text_not_url(self):
        data = make().translate("see [docs](https://example.com)\n")
        assert b"docs" in data and b"https" not in data

    def test_spacing_is_preserved_between_styles(self):
        assert visible(make().translate("a *side*:\n")).strip() == "a side:"


class TestWrap:
    def test_paragraph_wraps_at_width(self):
        text = "word " * 30
        lines = visible(make().translate(text)).splitlines()
        assert all(len(line) <= 48 for line in lines)
        assert len(lines) >= 3

    def test_overlong_word_is_hard_split(self):
        word = "x" * 100
        lines = visible(make().translate(word)).splitlines()
        assert all(len(line) <= 48 for line in lines)
        assert "".join(lines).startswith("x" * 48)

    def test_hard_line_break(self):
        lines = visible(make().translate("line one  \nline two\n")).splitlines()
        assert "line one" in lines and "line two" in lines


class TestBlocks:
    def test_unordered_list_bullet(self):
        text = visible(make().translate("- one\n- two\n"))
        assert "* one" in text and "* two" in text

    def test_ordered_list_numbering(self):
        text = visible(make().translate("1. first\n2. second\n"))
        assert "1. first" in text and "2. second" in text

    def test_nested_list_indent(self):
        text = visible(make().translate("- top\n  - nested\n"))
        assert "  * nested" in text

    def test_task_list_checkboxes(self):
        text = visible(make().translate("- [ ] unchecked\n- [x] done\n"))
        assert "[ ] unchecked" in text
        assert "[x] done" in text

    def test_task_list_no_bullet_prefix(self):
        text = visible(make().translate("- [ ] only task\n"))
        assert "* [ ]" not in text
        assert text.startswith("[ ]")

    def test_mixed_task_and_plain_items(self):
        text = visible(make().translate("- [x] task\n- plain\n"))
        assert "[x] task" in text and "* plain" in text

    def test_task_item_wraps_aligned_under_text(self):
        text = visible(
            make().translate("- [x] " + "word " * 12)
        ).splitlines()
        assert len(text) > 1
        assert text[1].startswith("    word")

    def test_thematic_break_is_full_width(self):
        assert "-" * 48 in visible(make().translate("---\n"))

    def test_code_block_indented(self):
        assert "  echo hi" in visible(make().translate("```\necho hi\n```\n"))

    def test_block_quote_prefix(self):
        assert "> noted" in visible(make().translate("> noted\n"))

    def test_list_item_wraps_with_hanging_indent(self):
        text = visible(make().translate("- " + "word " * 20)).splitlines()
        assert len(text) > 1
        # continuation lines align under the text after the "bullet " marker
        assert text[1].startswith("  word")
