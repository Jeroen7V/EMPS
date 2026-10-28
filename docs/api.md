# EMPS HTTP API

EMPS is a FastAPI service exposing three endpoints. Full markdown→ESC/POS
mapping is documented at the end of this file.

## Endpoints

### `POST /print`

Body: `{"markdown": "..."}` (1–20 000 characters).

Response: `{"status": "printed", "bytes": <n>}` where `bytes` is the length of
the generated ESC/POS byte stream.

Errors:
- `422` — invalid markdown payload (empty/missing/too long/untranslatable).
- `503` — printer error (device unreachable, out of paper, backend failure).
- `401` — invalid or missing bearer token, when `EMPS_AUTH_TOKEN` is set.

### `POST /print/test` (no body)

Prints a built-in test page exercising every supported markdown feature —
headings, bold, italic, underline, strikethrough, code, lists, task
checkboxes, quotes, separators, and a QR code. Same response/errors as
`/print`.

### `GET /health`

Always returns HTTP 200 (liveness-only, so a failed print does not flip
Docker's healthcheck unhealthy):

```json
{
  "status": "ok",
  "version": "0.1.0",
  "backend": "file",
  "printer": "unknown",
  "last_error": null
}
```

- `backend`: `file` or `usb`, as configured.
- `printer`: reflects the **last actual print attempt** — `unknown` until the
  first print, `ok` after a successful print, `error` after a failed one.
- `last_error`: the exception message of the last failed print, else `null`.
- `version`: the service's version string.

## Authentication

By default the service accepts unauthenticated requests from your LAN. When
the `EMPS_AUTH_TOKEN` environment variable is set, the mutating endpoints
(`/print`, `/print/test`) require `Authorization: Bearer <token>`. `/health`
stays open so health checks and the Home Assistant integration can still read
status.

## Markdown → ESC/POS mapping

| Markdown | ESC/POS |
|---|---|
| `#` | double width + height, bold, centered |
| `##` | double height, bold, centered |
| `###`+ | bold, normal size |
| `**bold**` | ESC E bold on/off |
| `*italic*` | ESC 4 italic on/off |
| `<u>underline</u>` | ESC `-` underline on/off (inline HTML) |
| `~~strikethrough~~` | reverse video on/off |
| `` `code` `` and fenced blocks | reverse video |
| http(s) links | printed as text plus a scannable QR code |
| ordered/unordered/nested lists | indented lines |
| task list checkboxes | `[ ]` / `[x]` boxes |
| `>` block quotes | indented |
| `---` | full-width separator |

Paper is 58 mm (32 columns) by default; text wraps automatically.
See `emps/translator.py` for the authoritative implementation.
