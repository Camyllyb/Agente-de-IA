"""Testes do ExperimentProtocol (offline)."""

from __future__ import annotations

import pytest

from app.models.benchmark import BenchmarkDataset, BenchmarkQuestion
from experiments.protocol import (
    ExperimentType,
    ModelRef,
    ProtocolManager,
    ProtocolStatus,
    build_default_protocol,
)


def _dataset() -> BenchmarkDataset:
    questions = [
        BenchmarkQuestion(id=f"Q{i:03d}", category="calculation", difficulty="easy")
        for i in range(6)
    ]
    return BenchmarkDataset(dataset_version="v1", questions=questions)


def _protocol(**kwargs):
    return build_default_protocol(
        _dataset(),
        models=[ModelRef(provider="openai", model="modelo-x")],
        **kwargs,
    )


def test_build_and_checksum_stable() -> None:
    p1 = _protocol()
    p2 = _protocol()
    assert p1.compute_checksum() == p2.compute_checksum()


def test_checksum_changes_with_content() -> None:
    p1 = _protocol(temperature=0.0)
    p2 = _protocol(temperature=0.7)
    assert p1.compute_checksum() != p2.compute_checksum()


def test_freeze_sets_checksum_and_status() -> None:
    p = _protocol()
    frozen = p.freeze()
    assert frozen.status == ProtocolStatus.frozen
    assert frozen.checksum
    assert frozen.verify_checksum()
    with pytest.raises(ValueError):
        frozen.freeze()  # já congelado


def test_freeze_rejects_invalid() -> None:
    from experiments.protocol import ExperimentProtocol

    p = ExperimentProtocol(total_questions=0)  # sem modelos/métricas/tipos
    with pytest.raises(ValueError):
        p.freeze()


def test_protocol_manager_versioning(tmp_path) -> None:
    manager = ProtocolManager(base_dir=tmp_path)
    p = _protocol()
    manager.save(p.freeze())
    assert manager.next_version() == "protocol_v2"
    loaded = manager.load("protocol_v1")
    assert loaded.status == ProtocolStatus.frozen
    # Não sobrescreve um congelado.
    with pytest.raises(ValueError):
        manager.save(loaded)


def test_experiment_types_present() -> None:
    p = _protocol()
    assert ExperimentType.llm_only in p.experiment_types
    assert ExperimentType.agent in p.experiment_types
