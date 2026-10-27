FROM python:3.12-slim

# libusb-1.0 is loaded at runtime by pyusb for raw USB access
RUN apt-get update \
    && apt-get install -y --no-install-recommends libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

LABEL org.opencontainers.image.title="markdown-escpos-printer" \
      org.opencontainers.image.description="HTTP service that translates markdown to ESC/POS and prints it on a USB receipt printer" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.authors="Jeroen Vermeylen <jeroen@fork-it.be>"

COPY pyproject.toml ./
COPY printer_service ./printer_service
RUN pip install --no-cache-dir .

ENV PRINTER_BACKEND=usb

EXPOSE 8000

CMD ["uvicorn", "printer_service.api:app", "--host", "0.0.0.0", "--port", "8000"]
