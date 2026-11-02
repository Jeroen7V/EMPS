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
import pytest
from fastapi.testclient import TestClient

from emps.api import create_app
from emps.config import Settings


@pytest.fixture()
def client(tmp_path):
    output = tmp_path / "output.bin"
    settings = Settings(backend="file", file_backend_path=str(output))
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, output


def test_health(client):
    client, _ = client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["printer"] == "unknown"  # no print attempted yet


def test_health_reports_printer_ok_after_print(client):
    client, _ = client
    assert client.post("/print", json={"markdown": "hello\n"}).status_code == 200
    health = client.get("/health").json()
    assert health["printer"] == "ok"
    assert health["last_error"] is None


def test_health_reports_printer_error_after_failed_send(client):
    client, _ = client

    class FailingBackend:
        def send(self, data: bytes) -> None:
            raise RuntimeError("device not responding")

    client.app.state.backend = FailingBackend()
    assert client.post("/print", json={"markdown": "hello\n"}).status_code == 503
    health = client.get("/health").json()
    assert health["printer"] == "error"
    assert "device not responding" in health["last_error"]


def test_print_returns_byte_count(client):
    client, output = client
    response = client.post("/print", json={"markdown": "# Hello\n\n- a\n- b\n"})
    assert response.status_code == 200
    assert response.json()["status"] == "printed"
    assert response.json()["bytes"] == output.stat().st_size


def test_print_test_page(client):
    client, output = client
    response = client.post("/print/test")
    assert response.status_code == 200
    assert response.json()["status"] == "printed"
    assert response.json()["bytes"] == output.stat().st_size
    data = output.read_bytes()
    assert b"\x1bE\x01" in data  # bold
    assert b"\x1b4" in data  # italic
    assert b"\x1b-\x01" in data  # underline
    assert b"\x1d\x76" + b"0\x00" in data  # raster (code block + QR code)
    assert b"\x1ba\x01" in data  # centered headings
    assert data.count(b"\x1d\x76" + b"0\x00") >= 2  # code block and QR images
    assert b"[x] done" in data  # task list


def test_print_test_page_updates_printer_state(client):
    client, _ = client
    assert client.post("/print/test").status_code == 200
    health = client.get("/health").json()
    assert health["printer"] == "ok"


def test_print_writes_escpos_bytes(client):
    client, output = client
    response = client.post(
        "/print", json={"markdown": "**bold** item\n"}
    )
    assert response.status_code == 200
    data = output.read_bytes()
    assert data.startswith(b"\x1b@")  # ESC @ init
    assert b"\x1bE\x01bold" in data  # bold on
    assert data.endswith(b"\x1dVB\x00")  # partial cut


def test_empty_markdown_rejected(client):
    client, _ = client
    response = client.post("/print", json={"markdown": ""})
    assert response.status_code == 422


def test_missing_markdown_rejected(client):
    client, _ = client
    response = client.post("/print", json={})
    assert response.status_code == 422


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        create_app(Settings(backend="carrier-pigeon"))


def test_health_includes_version(client):
    client, _ = client
    health = client.get("/health").json()
    assert health["version"] == "0.1.0"


def test_auth_token_rejects_missing_and_wrong_token(tmp_path):
    output = tmp_path / "output.bin"
    settings = Settings(
        backend="file", file_backend_path=str(output), auth_token="secret"
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.post("/print", json={"markdown": "x\n"}).status_code == 401
        assert client.post("/print/test").status_code == 401
        assert (
            client.post(
                "/print",
                json={"markdown": "x\n"},
                headers={"Authorization": "Bearer wrong"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/print",
                json={"markdown": "x\n"},
                headers={"Authorization": "Bearer secret"},
            ).status_code
            == 200
        )


def test_health_open_even_with_auth_token(tmp_path):
    output = tmp_path / "output.bin"
    settings = Settings(
        backend="file", file_backend_path=str(output), auth_token="secret"
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_no_auth_token_by_default(client):
    client, _ = client
    assert client.post("/print", json={"markdown": "x\n"}).status_code == 200
