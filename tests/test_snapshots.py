"""Testes do SnapshotManager (offline)."""

from __future__ import annotations

import json

import pytest

from app.snapshots import (
    SnapshotFrozenError,
    SnapshotIntegrityError,
    SnapshotManager,
    SnapshotStatus,
)


def _records():
    return [
        {"ticker": "PETR4", "date": "2024-01-02", "open": 35.0, "high": 36.5, "low": 34.5,
         "close": 36.0, "volume": 1000000, "currency": "BRL"},
        {"ticker": "PETR4", "date": "2024-06-03", "open": 37.0, "high": 38.0, "low": 36.5,
         "close": 37.8, "volume": 1200000, "currency": "BRL"},
    ]


@pytest.fixture()
def manager(tmp_path) -> SnapshotManager:
    return SnapshotManager(base_dir=tmp_path)


def test_create_and_load(manager) -> None:
    meta = manager.create("snap_2024h1", _records(), sources=["Brapi"], dataset_version="v1")
    assert meta.status == SnapshotStatus.draft
    assert meta.records == 2
    assert meta.tickers == ["PETR4"]
    loaded = manager.load("snap_2024h1")
    assert len(loaded["market_records"]) == 2


def test_validate_and_freeze(manager) -> None:
    manager.create("snap1", _records())
    validation = manager.validate("snap1", required_tickers=["PETR4"])
    assert validation.ok
    assert manager.read_metadata("snap1").status == SnapshotStatus.validated
    meta = manager.freeze("snap1")
    assert meta.status == SnapshotStatus.frozen
    assert meta.checksum
    assert manager.verify_integrity("snap1") is True


def test_frozen_cannot_be_recreated(manager) -> None:
    manager.create("snap1", _records())
    manager.freeze("snap1")
    with pytest.raises(SnapshotFrozenError):
        manager.create("snap1", _records())
    with pytest.raises(SnapshotFrozenError):
        manager.freeze("snap1")  # já congelado


def test_tampering_detected(manager) -> None:
    manager.create("snap1", _records())
    manager.freeze("snap1")
    # Adultera o arquivo de dados após o congelamento.
    market_path = manager._market_path("snap1")
    data = json.loads(market_path.read_text(encoding="utf-8"))
    data[0]["close"] = 999.0
    market_path.write_text(json.dumps(data), encoding="utf-8")

    assert manager.verify_integrity("snap1") is False
    with pytest.raises(SnapshotIntegrityError):
        manager.load("snap1")  # carregamento interrompe o experimento


def test_build_provider_serves_data(manager) -> None:
    manager.create("snap1", _records())
    manager.freeze("snap1")
    provider = manager.build_provider("snap1")
    quote = provider.get_quote("PETR4")
    assert quote.price == 37.8
    hist = provider.get_history("PETR4", "2024-01-01", "2024-12-31")
    assert len(hist.bars) == 2


def test_new_collection_new_id(manager) -> None:
    manager.create("snap_v1", _records())
    manager.freeze("snap_v1")
    # Nova coleta -> novo snapshot_id (não sobrescreve o congelado).
    manager.create("snap_v2", _records(), dataset_version="v2")
    ids = {m.snapshot_id for m in manager.list_snapshots()}
    assert ids == {"snap_v1", "snap_v2"}
