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
"""FastAPI application exposing the markdown printing endpoint."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from emps.backends import make_backend
from emps.config import Settings, load_settings
from emps.translator import MarkdownToEscpos


class PrintRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=20_000)


class PrintResponse(BaseModel):
    status: str = "printed"
    bytes: int


TEST_PAGE = """# EMPS Test Page

## Headings & Styles

### H3 heading (bold, centered)

**bold** *italic* <u>underline</u> ~~struck~~ and `code`

**bold *italic* combined** ~~cut **bold***~~

## Structure

- unordered item
  - nested item
1. ordered item
2. second

- [ ] unchecked task
- [x] done task

> block quote line one
> wrapped quote text continues here

---

## Code

```
def hello():
    print("hi")
```

## QR Code

Scan me: [emps on github](https://github.com/Jeroen7V/EMPS)
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(
        title="Markdown ESC/POS printer",
        version="0.1.0",
        description="Receives markdown and prints it on an ESC/POS printer.",
    )
    app.state.settings = settings
    app.state.translator = MarkdownToEscpos(width=settings.paper_width_chars)
    app.state.backend = make_backend(settings)
    app.state.printer_state = {"status": "unknown", "detail": None}

    @app.get("/health")
    def health() -> dict[str, str | None]:
        return {
            "status": "ok",
            "backend": settings.backend,
            "printer": app.state.printer_state["status"],
            "last_error": app.state.printer_state["detail"],
        }

    @app.post("/print", response_model=PrintResponse)
    def print_document(request: PrintRequest) -> PrintResponse:
        try:
            data = app.state.translator.translate(request.markdown)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Failed to translate markdown: {exc}"
            ) from exc
        try:
            app.state.backend.send(data)
        except Exception as exc:
            app.state.printer_state = {"status": "error", "detail": str(exc)}
            raise HTTPException(
                status_code=503, detail=f"Printer error: {exc}"
            ) from exc
        app.state.printer_state = {"status": "ok", "detail": None}
        return PrintResponse(bytes=len(data))

    @app.post("/print/test", response_model=PrintResponse)
    def print_test_page() -> PrintResponse:
        """Print a built-in page exercising every supported markdown feature."""
        return print_document(PrintRequest(markdown=TEST_PAGE))

    return app


app = create_app()
