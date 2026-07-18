"""Offline smoke tests — no network, no API key required."""

from fastapi.testclient import TestClient

import halo
from halo.app import app


def test_package_imports() -> None:
    assert halo.__version__


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"]
