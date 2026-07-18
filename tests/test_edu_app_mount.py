"""The edu router mounted in the real app — and the MCI surface still intact."""

from __future__ import annotations

from fastapi.testclient import TestClient

from halo.app import app

client = TestClient(app)


def test_edu_routes_reachable_in_app() -> None:
    assert client.get("/edu/modules").status_code == 200
    r = client.get("/edu/brief", params={"incident": "factory explosion, 100+ inbound"})
    assert r.status_code == 200
    assert r.json()["cards"]


def test_mci_surface_unaffected() -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/mci/census").status_code == 200
    assert client.get("/mci/scenarios").status_code == 200


def test_board_and_brief_cross_link() -> None:
    brief = client.get("/edu/brief/card", params={"incident": "factory explosion"})
    assert 'href="/"' in brief.text  # brief links back to the track board
