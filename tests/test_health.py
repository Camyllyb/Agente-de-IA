"""Testes do endpoint /health (sem internet, sem API key)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import __version__
from app.api.app import create_app

client = TestClient(create_app())


def test_health_status_code() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_payload() -> None:
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "financial-prompt-agent"
    assert data["version"] == __version__
    assert "environment" in data
