# Home Assistant + EMPS

There are two ways to use EMPS from Home Assistant:

1. **The `emps` custom integration** (recommended): UI setup, printer health
   entities, and service actions. Installable through the Marketplace.
2. **YAML-only (`rest_command`)**: no custom component needed, works on any
   HA install.

## 1. Installing the custom integration

### Home Assistant 2026.11+ (Marketplace)

1. Settings > Marketplace, search for **EMPS**.
2. Download/install the integration.
3. Settings > Devices & Services > Add Integration > **EMPS**.
4. Enter the host/port of the EMPS service (and the bearer token if
   `EMPS_AUTH_TOKEN` is set on the service). Setup validates the connection
   against `GET /health`.

### Older installs (classic HACS)

1. HACS > ⋮ > Custom repositories, add `https://github.com/Jeroen7V/EMPS`,
   category **Integration**.
2. Download the repository, restart Home Assistant.
3. Add the **EMPS** integration as above.

The EMPS service itself must be running somewhere reachable from HA — see
[deployment.md](deployment.md). If HA runs in a container, do not use
`localhost`; use the printer machine's LAN IP.

### What you get

- A **Device** per configured printer, with sensors:
  - *printer status* (`unknown` / `ok` / `error`) with the last error as an
    attribute,
  - *backend* (file/usb, diagnostic),
  - *last print* size in bytes.
- A **test page button** on the device.
- Service actions (usable from automations, scripts, and dashboards):
  - `emps.print_markdown` — fields: printer (config entry), markdown text.
  - `emps.print_test_page` — field: printer.
- An options flow (poll interval, 30–3600 s) and redacted diagnostics.

### Usage examples

Print a simple message from a script:

```yaml
script:
  print_message:
    description: Print a message on the thermal printer
    fields:
      message:
        description: The message text (markdown allowed)
        example: "Dinner at 19:00"
    sequence:
      - action: emps.print_markdown
        data:
          config_entry_id: "<your EMPS config entry id>"
          markdown: >-
            # Message

            {{ message }}
```

Print a To-do List entity as a paper checklist:

```yaml
script:
  print_todo:
    description: Print a To-do List entity as a paper checklist
    fields:
      todo_entity:
        description: To-do List entity id, e.g. todo.groceries
        example: todo.groceries
    variables:
      items: "{{ state_attr(todo_entity, 'items') }}"
    sequence:
      - action: emps.print_markdown
        data:
          config_entry_id: "<your EMPS config entry id>"
          markdown: >-
            # {{ friendly_name(todo_entity) }}

            {% for item in items %}
            - [{{ 'x' if item.status == 'completed' else ' ' }}] {{ item.summary }}
            {% endfor %}
```

Automation that prints the shopping list when it changes (debounced):

```yaml
automation:
  - alias: "Print shopping list when it changes"
    trigger:
      - platform: event
        event_type: todo_item_changed
      - platform: state
        entity_id: todo.groceries
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state not in ['unknown', 'unavailable'] }}"
    action:
      - delay: "00:00:30"
      - action: script.print_todo
        data:
          todo_entity: todo.groceries
```

For quick manual printing, add an `input_text` helper and a dashboard button
that calls `emps.print_markdown` with `{{ states('input_text.print_message') }}`.

## 2. YAML-only fallback (no custom component)

If you don't want to install the integration, a `rest_command` works too:

```yaml
rest_command:
  print_markdown:
    url: http://<printer-host>:8000/print
    method: POST
    content_type: application/json
    payload: '{"markdown": {{ markdown | to_json }}}'
```

Then call `rest_command.print_markdown` with a `markdown` string from any
script or automation, using the script examples above with the action name
swapped. The `to_json` filter escapes quotes and newlines so the JSON body is
always valid. If `EMPS_AUTH_TOKEN` is set, add `headers:
Authorization: Bearer <token>` to the `rest_command`.

## Markdown subset supported

Headings (`#`, `##`, `###` — centered), bold, italic, `<u>underline</u>`
(inline HTML), `~~strikethrough~~` (printed as reverse video), http(s) links
(printed as text plus a scannable QR code), ordered/unordered/nested lists,
task list checkboxes (`- [ ]` / `- [x]`), block quotes, fenced code blocks
(reverse video), and `---` separators. Paper is 58 mm (32 columns); text
wraps automatically. The full mapping table is in [api.md](api.md).

## Practical notes

- **Errors**: invalid markdown raises a `HomeAssistantError` with the service's
  detail; a printer failure (`503`) also flips the *printer status* sensor to
  `error` and stores the service's message in its `last_error` attribute.
- **Polling**: the integration polls `/health` (default every 60 s,
  configurable in the integration's options) and refreshes immediately after
  each print.
- **Security**: the service accepts unauthenticated POSTs from your LAN by
  default; set `EMPS_AUTH_TOKEN` on the service and provide the token during
  integration setup to gate printing.
