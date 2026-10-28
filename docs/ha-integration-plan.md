# Home Assistant Integration Plan — `emps` Custom Component

Status: proposal / plan. Nothing described here is implemented yet.

Goal: ship a first-class Home Assistant custom integration (`emps`) that talks to
the EMPS FastAPI service over the LAN, installable through the Home Assistant
Marketplace (HACS built into HA since 2026.11; for older installs, classic HACS).

The existing `docs/home-assistant.md` recipe (`rest_command` + YAML scripts)
remains supported as the zero-install path. This plan covers the "real"
integration: UI setup, device/entity model, service actions, diagnostics, and
Marketplace publication.

---

## 1. Research

### 1.1 What the integration talks to

EMPS is an HTTP service on the printer host (`emps/api.py`):

| Endpoint | Method | Purpose |
|---|---|---|
| `/print` | POST | `{markdown: str}` (1–20 000 chars) → `{"status":"printed","bytes":n}`; `422` invalid payload, `503` printer error |
| `/print/test` | POST (no body) | prints the built-in feature test page |
| `/health` | GET | `{"status":"ok","backend":"...","printer":"unknown"|"ok"|"error","last_error":...}`; always 200 |

Consequences for the design:

- The integration is a **client of a LAN HTTP API**, not a driver. No USB,
  no pyusb, no udev concerns inside HA. All heavy lifting (markdown → ESC/POS,
  QR codes, USB I/O) stays in the service.
- The API is intentionally small, so the integration can be thin: one client
  module, one coordinator, a couple of entities, a couple of service actions.
- `printer` in `/health` only reflects the last print attempt, so "unknown" is
  a normal, non-error state.
- The service is unauthenticated on the LAN today. The integration should
  optionally send a bearer token (needs a small EMPS-side addition, see 4.6).

### 1.2 Distribution: Marketplace (ex-HACS)

- From Home Assistant **2026.11**, HACS ships in HA core as the **Marketplace**
  (Settings > Marketplace). Same catalog (`hacs/default`), same `hacs.json`
  per-repo manifest; existing HACS installs migrate automatically. Publication
  still happens by submitting the repo to `hacs/default`; the HACS action
  validates the repository structure.
- For pre-2026.11 installs, the repo also works as a classic HACS custom
  repository (category "Integration").
- Repo requirements for an integration: `custom_components/<domain>/` with a
  valid `manifest.json`, a `hacs.json` at the repo root
  (`{"name": "...", "render_readme": true}` plus e.g. `"home_assistant_version":
  "2025.2.0"` as the minimum HA version), a README, and (recommended) brand
  images. Since HA 2026.x, brand images live in
  `custom_components/<domain>/brand/` (logo, icon, @2x/dark variants) instead
  of a `home-assistant/brands` PR.
- Monorepo layout works fine: `hacs.json` points Marketplace at
  `custom_components/emps` via `"zip_url"`/content filters or the default
  integration convention (`custom_components/<domain>` is auto-detected).

### 1.2.1 Repository layout: monorepo (chosen) vs. separate repo

Marketplace/HACS resolves integrations from any GitHub repository as long as
it contains `custom_components/emps/` with a valid `manifest.json` and a root
`hacs.json` — a dedicated repository is **not** required. Two layouts were
considered:

**A. Monorepo (chosen): integration lives in this repository**

```
EMPS/
├── emps/                    # existing FastAPI service (unchanged)
├── custom_components/emps/  # the Home Assistant integration
├── hacs.json                # new, points Marketplace at the integration
└── ...
```

- Pros: one repo, one issue tracker, one release flow — a single tag can
  ship a service change and the matching integration change together, which
  matters because the integration is coupled to the service's HTTP API
  (e.g. the optional bearer token, `version` in `/health`); users already
  watch this repo; lowest overhead for a solo maintainer.
- Cons: every tag updates the integration for all Marketplace users even for
  service-only changes (mitigate with component-scoped release notes and the
  `home_assistant_version` minimum in `hacs.json`); CI gains a HACS/hassfest
  job (purely additive); the README must lead with both components so
  integration-only users are not confused by the Docker/ESC/POS content.
  Repo zip download size is trivial at this footprint.

**B. Separate `EMPS-home-assistant` repository**

- Pros: clean separation of audiences and release cadences; the integration
  repo is exactly what Marketplace expects at its root; service releases never
  touch integration users.
- Cons: two repos to maintain; cross-repo coordination whenever the HTTP API
  changes (the one real coupling point); issue triage across both; manual
  version sync.

**Decision: monorepo (A).** The service↔integration API coupling benefits
from same-repo, same-tag releases, and EMPS is small enough that the monorepo
 downsides don't bite. If the integration later grows a large audience or
needs an independent release cadence, splitting it out is a mechanical move
(copy `custom_components/emps/` + `hacs.json` to a new repo) — nothing in the
integration design locks us in.

### 1.3 Alternatives considered (pros / cons)

**A. Keep `rest_command` + YAML scripts (status quo, `docs/home-assistant.md`)**

- Pros: zero maintenance, no HA version coupling, no HACS review, works today.
- Cons: manual YAML; no device/entity in the UI, so no health visibility, no
  automations on printer state, no update entity for the integration itself,
  no discovery; easy to mis-configure (host/port in three YAML places).

**B. Custom integration (this plan)**

- Pros: UI config flow (host/port/token, validated on submit); a Device with
  entities (printer health, last print, paper/error state) that can drive
  automations and dashboards; first-class service actions
  (`emps.print_markdown`, `emps.print_test_page`) selectable in the UI with
  description/fields; options flow; diagnostics; repair/re-auth flows; proper
  logging and error mapping; versioned releases and update flow through
  Marketplace; single install step for users.
- Cons: ongoing maintenance against HA's deprecation cycle (needs a tested
  minimum HA version per release); testing burden
  (`pytest-homeassistant-custom-component`); Marketplace catalog submission
  and review latency; more code in this repo; a second moving part users must
  still deploy (the EMPS service itself — the integration does not remove that
  requirement).

**C. HA Add-on (run EMPS inside the HAOS supervisor)**

- Pros: one-box deployment for HAOS users; the add-on can expose the service on
  the LAN and the integration could then even target `localhost`/addon hostname.
- Cons: only works on HAOS/Supervised (not container/core installs); add-on
  build/publish pipeline in addition to everything else; USB passthrough to an
  add-on requires udev/device mapping anyway, which is exactly what running
  EMPS on the printer host avoids.
- Verdict: possible later, out of scope. The integration is deliberately
  add-on-agnostic: any reachable `http://host:port` works.

**D. Submitting to HA core (built-in integration)**

- Pros: highest trust, automatic updates, brand included in core.
- Cons: the quality bar is very high (silver/gold); API review requires
  documentation of a public API; long review cycles; a niche hobby service is
  not a good core candidate. Verdict: no. Custom component via Marketplace is
  the right ceiling.

**Recommendation: B**, with A documented as fallback and C kept as a future
optional extra.

### 1.4 Risks / drawbacks

- **HA API churn**: custom integrations must chase renames (e.g. `async_setup_
  entry`, coordinator generics, manifest rules, the 2026.12 update-listener
  restriction). Mitigation: pin minimum HA version in the manifest, run hassfest
  + the HACS action in CI on every push, test against the lowest supported HA.
- **Unauthenticated LAN API**: printing (and service control) is open to the
  LAN. Mitigation: ship optional bearer-token auth in EMPS (env var) and make
  the token a config-flow field; document the exposure.
- **Small user base**: Marketplace submission has review latency; a niche repo
  may wait. Mitigation: classic HACS custom-repo install instructions work
  meanwhile.
- **Duplication of printer logic**: none — by design the integration never
  re-implements ESC/POS. If the service is down, the integration reports
  unavailable rather than failing over.
- **Monorepo packaging**: Marketplace must download only the integration.
  Mitigation: `hacs.json` with the integration content filter; HACS action
  validates in CI before submission.

---

## 2. Architecture

### 2.1 System view

```
HA Automation / Dashboard / Voice
        |
        v
service action: emps.print_markdown  (or script/diagram call)
        |
        v
+--------------------------- Home Assistant ---------------------------+
|  custom_components/emps                                              |
|   __init__.py      async_setup_entry, runtime data, unload/reload     |
|   config_flow.py   user + reconfigure flow (host, port, token)        |
|   options_flow.py  poll interval, debounce delay                      |
|   api.py           EmpsApiClient: aiohttp thin wrapper, typed errors  |
|   coordinator.py   DataUpdateCoordinator -> GET /health                |
|   device.py        DeviceInfo (single device, config entry = printer) |
|   sensor.py        printer status, last print bytes, last error       |
|   button.py        print test page (POST /print/test)                 |
|   services.py      async_register: print_markdown, print_test_page    |
|   diagnostics.py   redacted entry + coordinator dump                  |
+----------------------------------------------------------------------+
        |  HTTP (aiohttp session from hass.helpers.aiohttp_client)
        v
EMPS FastAPI service on printer host: POST /print, POST /print/test, GET /health
        |
        v
USB thermal printer (ESC/POS)
```

### 2.2 Integration model

- **Domain**: `emps`. Integration type: `IntegrationType.PUSH`-like — a service
  integration with a coordinator for health polling; no polling of print state.
- **Config entry**: one entry per EMPS instance (single entry allowed unless
  multi-printer support is wanted later; start with `single_config_entry`-
  style uniqueness by `(host, port)` to keep multi-printer open).
- **Device**: one `DeviceInfo` per config entry (name from options, model
  "EMPS markdown printer", sw version from a new `GET /version` or baked into
  `/health`).
- **Entities** (all optional; driven by coordinator data):
  - `sensor.emps_<name>_printer_status`: `unknown|ok|error` mapped to
    `unknown|on|problem` device-class style values.
  - `sensor.emps_<name>_backend`: service backend (file/usb), static-ish.
  - `sensor.emps_<name>_last_print_bytes`: from the last print response, stored
    in coordinator runtime data.
  - `button.emps_<name>_test_page`: fires `POST /print/test`.
- **Service actions** (the core value):
  - `emps.print_markdown` — target: config entry (via `cv.config_entry_id` or
    entity/device selectors); field `markdown` (string, template-friendly).
    Returns bytes printed in the action result.
  - `emps.print_test_page` — target-based, no fields.
- **Coordinator**: `DataUpdateCoordinator[EmpsHealth]`, default interval 60 s
  (configurable in options), `update_method = client.async_health()`. Map HTTP
  errors: connection errors → `ConfigEntryNotReady` during setup and
  `UpdateFailed` during polling; `503` from `/print` → user-facing
  `HomeAssistantError` with the service's `detail`.
- **Error handling matrix**:

  | Condition | Behavior |
  |---|---|
  | setup cannot reach `/health` | `ConfigEntryNotReady`, HA retries |
  | poll connection error | coordinator `UpdateFailed`, entities unavailable |
  | `print` returns 422 | `HomeAssistantError("invalid markdown payload: …")` |
  | `print` returns 503 | `HomeAssistantError("printer error: …")`, coordinator force-refresh |
  | auth token rejected (after 4.6) | `ConfigEntryAuthFailed`, reauth flow |

### 2.3 Repository / packaging layout

```
EMPS (monorepo root)
├── hacs.json                      # {"name": "EMPS", "category": "integration", ...}
├── custom_components/
│   └── emps/
│       ├── __init__.py
│       ├── manifest.json          # domain, name, codeowners, config_flow,
│       │                           # requirements: [] (aiohttp comes with HA),
│       │                           # integration_type: "service", iot_class: "local_polling"
│       ├── config_flow.py
│       ├── options_flow.py (fold into config_flow.py per HA style)
│       ├── api.py
│       ├── coordinator.py
│       ├── const.py               # CONF_HOST/CONF_PORT/CONF_TOKEN, DOMAIN, PLATFORMS
│       ├── entity.py              # EmpsEntity base (coordinator + entry wiring)
│       ├── sensor.py
│       ├── button.py
│       ├── services.py + services.yaml
│       ├── diagnostics.py
│       ├── strings.json
│       ├── translations/en.json (+ nl.json)
│       └── brand/{logo.png, icon.png, @2x variants}
├── tests/test_ha_integration/     # pytest-homeassistant-custom-component
└── .github/workflows/ha-ci.yml    # hassfest-equivalent + HACS validation
```

Notes:
- **No third-party requirements**: HA ships aiohttp; the client is a thin
  wrapper. This keeps `manifest.json` `requirements: []`, avoiding pip supply
  chain surface and Marketplace friction.
- The EMPS Python package itself is *not* imported by the integration — the
  HTTP boundary keeps the two deployables decoupled (different Python
  versions, different hosts).
- GPL-3: the integration is a separate work communicating over HTTP; it will
  still be GPL-3 to match the repo (note in README that MIT-style HA blueprint
  scaffolding is not copied verbatim, or the integration inherits GPL-3).

---

## 3. Technical plan

### 3.1 Phases

**Phase 0 — groundwork (repo, ~0.5 day)**
- Create `custom_components/emps/` skeleton, `hacs.json`, README section,
  brand placeholders.
- `manifest.json`: `domain: emps`, `name: EMPS`, `codeowners: [Jeroen7V]`,
  `config_flow: true`, `integration_type: service`,
  `iot_class: local_polling`, `version: 0.1.0` (required for custom
  integrations), `requirements: []`.
- CI job: run `hacs/action` validation + `home-assistant/actions/hassfest`
  on pushes touching `custom_components/`.

**Phase 1 — client + setup (~1 day)**
- `api.py`: `EmpsApiClient` with `async_health()`, `async_print(markdown)`,
  `async_print_test()`, built on `async_get_clientsession(hass)`, 10 s timeout,
  `EmpsApiConnectionError` / `EmpsApiInvalidPayload` / `EmpsApiPrinterError`
  exceptions carrying status and detail.
- `__init__.py`: `async_setup_entry` (create client, validate via health,
  create coordinator, forward to `sensor`/`button` platforms, register
  services), `async_unload_entry`, reload listener for options updates.
- `config_flow.py`: user step (host, port, optional token), uniqueness key,
  `reconfigure` support; error mapping to `cannot_connect`/`invalid_auth`.

**Phase 2 — coordinator, entities, services (~1–2 days)**
- `coordinator.py` as described in 2.2; store last print result in the
  coordinator dataclass so sensors reflect it.
- `sensor.py` / `button.py` / `entity.py` per 2.2, with `entity_category:
  diagnostic` for backend/last-error sensors.
- `services.yaml` + `services.py`: `emps.print_markdown` (markdown field,
  20 000-char validation mirrored client-side for a friendlier error) and
  `emps.print_test_page`, both targetable at the config entry; update the
  coordinator after each print so status sensors refresh immediately.
- `strings.json` + `translations/en.json`, `nl.json` (author is Dutch; cheap
  goodwill).

**Phase 3 — polish (~1 day)**
- `options_flow`: display name, poll interval (30 s–1 h), maybe a "print
  header/footer template" convenience later.
- `diagnostics.py`: redacted config (host, port, token masked) + last health.
- Logbook/repairs: a repair issue if the printer stays `error` for N polls.
- Docs: rewrite `docs/home-assistant.md` into three sections — Marketplace
  install (2026.11+), classic HACS install, YAML-only fallback — with the
  existing script examples ported to `emps.print_markdown` action calls
  (simpler: no `rest_command`, no `to_json` escaping).
- **README restructuring** (part of this phase, see 3.3.1): slim the README
  down to a general overview + quick-start pointers, move detailed
  documentation into `docs/`.

**Phase 4 — tests + validation (~1 day)**
- `pytest-homeassistant-custom-component` suite: config flow (success,
  duplicate, unreachable host), coordinator error mapping, service action
  against an `aioresponses`/`pytest-httpx`-mocked API, entity availability.
- Local smoke: run EMPS with `PRINTER_BACKEND=file`, point a dev HA instance
  (PYTHONPATH trick) at it, print via the UI action.
- `ruff` + `mypy --strict` on `custom_components/`.

**Phase 5 — publication (~0.5 day + review wait)**
- Tag `v0.1.0` release; ensure `hacs.json` minimum HA version and release
  notes render.
- Submit to `hacs/default` per HACS integration publishing docs; keep the
  classic HACS custom-repo instructions until merged.

### 3.2 Key code shapes (illustrative, to be implemented)

```python
# api.py
class EmpsApiClient:
    def __init__(self, session: aiohttp.ClientSession, host: str,
                 port: int, token: str | None = None) -> None: ...
    async def async_health(self) -> EmpsHealth: ...
    async def async_print(self, markdown: str) -> int:  # returns bytes
        ...
    async def async_print_test(self) -> int: ...

# coordinator.py
class EmpsCoordinator(DataUpdateCoordinator[EmpsState]):
    async def _async_update_data(self) -> EmpsState:
        try:
            health = await self.client.async_health()
        except EmpsApiConnectionError as err:
            raise UpdateFailed(f"EMPS unreachable: {err}") from err
        return EmpsState(health=health, last_print=self.last_print)

# services: after a successful print, await coordinator.async_refresh()
```

### 3.3 Service-side (EMPS) additions needed

Small, backward-compatible additions to the service, each optional:

1. **Optional bearer token** (Phase 1): `EMPS_AUTH_TOKEN` env var; when set,
   require `Authorization: Bearer …` on mutating endpoints (keep `/health` open
   or protect it too, decided during implementation). Document in README and
   the integration's config flow help text.
2. **Version in `/health`**: add `version` to the health payload so the
   integration can set the device's sw_version.
3. *(Defer)* CORS/webhook needs: none; HA is a plain LAN client.

### 3.3.1 README / documentation restructuring

Target documentation layout when the integration ships:

```
README.md                  # general overview only
docs/
  home-assistant.md        # HA integration: Marketplace/HACS/YAML installs, usage
  deployment.md           # (moved from README) service setup: env, Docker, udev, USB
  api.md                  # (moved from README) endpoints, payload limits, error codes,
                          #  markdown->ESC/POS mapping table
  ha-integration-plan.md   # this plan (historical, or retired after implementation)
```

**README.md keeps** (short, link-heavy):

- One-paragraph "what is EMPS": a FastAPI service that turns markdown into
  ESC/POS and prints it on a USB thermal printer, plus a Home Assistant
  integration for it.
- A two-column overview of the two components (service / HA integration)
  with pointers to their respective docs.
- Quick start: install/run the service in a few commands, and the one-line
  "install via Settings > Marketplace" path for HA.
- Links into `docs/` for everything detailed (endpoint reference, markdown
  mapping, HA setup recipes, deployment/udev notes).

**Moved out of the README** (into `docs/` files above): the full
markdown→ESC/POS mapping table, the endpoint/response/error documentation,
Docker Compose / udev / USB configuration detail, and the long usage
examples. The README should answer "what is this and how do I get started"
  in one screen; `docs/` holds the rest.

Do this restructuring in the same PR/phase as the integration docs so the
Marketplace-facing README (which HACS renders) stays short and points users
to the right places, instead of growing ESC/POS service detail that
integration-only users don't need.

- Allow multiple config entries (multiple printers)? Plan says yes via
  uniqueness on `(host, port)`; decide whether service actions target entries
  or the single device during implementation (entry-targeting is cleaner).
- Sensor granularity: is `last_error` a sensor or only diagnostics?
- Whether to also ship an `update` coordinator entity is moot (Marketplace
  handles updates itself).

### 3.5 Milestones & acceptance criteria

| Milestone | Acceptance |
|---|---|
| M0 scaffold | `hacs/action` and hassfest pass in CI; integration loads in dev HA |
| M1 setup | UI flow creates entry against a file-backend EMPS; reload/unload clean |
| M2 actions | `emps.print_markdown` prints via UI Action call; sensors reflect status |
| M3 docs+polish | README slimmed to overview + quick start; detailed docs in `docs/`; diagnostics + options flow work; translations load |
| M4 tests | HA test suite green on min + latest supported HA versions |
| M5 publish | Listed in Marketplace on 2026.11+; classic HACS install verified |
