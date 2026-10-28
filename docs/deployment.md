# Deploying the EMPS service

The service runs on the machine with the USB thermal printer attached.
The Home Assistant integration talks to it over HTTP, so HA can run anywhere
that can reach this host.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `PRINTER_BACKEND` | `file` | `file` (dry-run, writes raw ESC/POS bytes) or `usb` |
| `PRINTER_OUTPUT_FILE` | `/tmp/escpos-output.bin` | Output file for the `file` backend |
| `USB_VENDOR_ID` | `0x28E9` | USB vendor id of the printer |
| `USB_PRODUCT_ID` | `0x0289` | USB product id of the printer |
| `PAPER_WIDTH_CHARS` | `32` | Paper width in characters (58 mm ≈ 32, 80 mm ≈ 48) |
| `EMPS_AUTH_TOKEN` | unset | When set, `/print` and `/print/test` require `Authorization: Bearer <token>` |

## Native (venv + uvicorn)

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# Dry run (no printer needed):
PRINTER_BACKEND=file PRINTER_OUTPUT_FILE=/tmp/escpos.bin \
  .venv/bin/uvicorn emps.api:app --host 0.0.0.0 --port 8000

# With a USB printer:
PRINTER_BACKEND=usb USB_VENDOR_ID=0x04b8 USB_PRODUCT_ID=0xe035 \
  .venv/bin/uvicorn emps.api:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker compose up -d
```

See `docker-compose.yml` in the repo root. The service binds `0.0.0.0`
inside the container; publish port 8000 to your LAN.

## USB permissions (udev)

Install the provided udev rule so the service user can access the printer
without root:

```bash
sudo cp 99-escpos.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Adjust the vendor/product ids in the rule to match your printer (check with
`lsusb`).

## Verifying

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/print/test
```

A full endpoint reference is in [api.md](api.md).
