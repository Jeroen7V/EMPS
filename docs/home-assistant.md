# Home Assistant Integration

Home Assistant can print to this service by POSTing markdown to
`POST /print`. The cleanest setup uses HA's built-in `rest_command`
integration - no custom integration or add-on required.

```
HA automation / dashboard button
        |
        v
rest_command.print_markdown  --HTTP POST-->  http://<printer-host>:8000/print
```

All snippets below go in HA's `configuration.yaml` (or their respective
files, e.g. `scripts.yaml`, if you use split configuration), except the
dashboard steps, which use the UI.

## 1. rest_command

```yaml
rest_command:
  print_markdown:
    url: http://<host-where-the-service-runs>:8000/print
    method: POST
    content_type: application/json
    payload: '{"markdown": {{ markdown | to_json }}}'
```

The `to_json` filter matters: it escapes quotes and newlines in the
markdown so the JSON body is always valid. Every call site below just
passes a markdown string.

## 2. Reusable print script

```yaml
script:
  print_message:
    description: Print a message on the thermal printer
    fields:
      message:
        description: The message text (markdown allowed)
        example: "Dinner at 19:00"
    sequence:
      - action: rest_command.print_markdown
        data:
          markdown: >-
            # Message

            {{ message }}
```

Call it from an automation or the Developer Tools (Actions tab):
`script.print_message` with `message: hello`.

## 3. To-do list printing

HA's To-do List entities expose their items as the `items` attribute, so a
template turns a list into markdown checkboxes directly. The service's
task-list support prints these as `[ ]` / `[x]` boxes.

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
      - action: rest_command.print_markdown
        data:
          markdown: >-
            # {{ friendly_name(todo_entity) }}

            {% for item in items %}
            - [{{ 'x' if item.status == 'completed' else ' ' }}] {{ item.summary }}
            {% endfor %}
```

### Automation trigger: print on list change

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
      - delay: "00:00:30"   # debounce rapid edits before printing
      - action: script.print_todo
        data:
          todo_entity: todo.groceries
```

The `delay` batches several quick edits into one print. Printing the whole
list on every change (rather than the changed item) keeps the paper
useful: you always get a complete, current checklist.

## 4. Dashboard entry points

For quick manual printing:

1. Settings > Devices & Services > Helpers: create an `input_text`
   helper (e.g. `input_text.print_message`, character limit 255 or more).
2. Add a button card to a dashboard that calls `script.print_message`
   with `message: "{{ states('input_text.print_message') }}"`.

## Markdown subset supported by the service

Headings (`#`, `##`, `###` — centered), bold, italic, `<u>underline</u>` (inline HTML),
`~~strikethrough~~` (printed as reverse video), http(s) links (printed as
text plus a scannable QR code), lists
(ordered/unordered/nested), task list checkboxes (`- [ ]` / `- [x]`), block
quotes, and fenced code blocks (both printed white-on-black), and
`---` separators. Paper is 58 mm (32
columns); text wraps automatically.

## Practical notes

- **Reachability**: if HA runs in a container, do not use `localhost` -
  use the Docker host IP or the printer machine's LAN IP. The service
  binds `0.0.0.0` inside the container, so any LAN client can reach it.
- **Auth**: the service accepts unauthenticated POSTs from your LAN. If
  you want a gate, add a bearer token to the service (env var) and pass
  `headers` in the `rest_command`.
- **Payload limit**: markdown is capped at 20,000 characters.
- **Errors**: `422` means invalid markdown payload, `503` means the
  printer failed (unreachable, busy, etc). `GET /health` reports the
  printer state from the last print attempt.
