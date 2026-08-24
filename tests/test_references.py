"""Testes do ReferenceAnswerGenerator (offline, snapshot congelado)."""

from __future__ import annotations

import pytest

from app.models.benchmark import BenchmarkQuestion, ExpectedAnswer
from app.snapshots import SnapshotManager
from app.snapshots.errors import SnapshotError
from experiments.references import ReferenceAnswerGenerator


def _records():
    return [
        {"ticker": "PETR4", "date": "2024-01-02", "close": 36.0, "currency": "BRL"},
        {"ticker": "PETR4", "date": "2024-06-03", "close": 37.8, "currency": "BRL"},
        {"ticker": "VALE3", "date": "2024-01-02", "close": 78.0, "currency": "BRL"},
        {"ticker": "VALE3", "date": "2024-06-03", "close": 64.0, "currency": "BRL"},
    ]


@pytest.fixture()
def gen(tmp_path) -> ReferenceAnswerGenerator:
    manager = SnapshotManager(base_dir=tmp_path)
    manager.create("snap1", _records())
    manager.freeze("snap1")
    return ReferenceAnswerGenerator(manager, "snap1", now="2026-01-01T00:00:00Z")


def _q(category, **kwargs) -> BenchmarkQuestion:
    base = dict(id="Q1", category=category, difficulty="easy")
    base.update(kwargs)
    return BenchmarkQuestion(**base)


def test_requires_frozen_snapshot(tmp_path) -> None:
    manager = SnapshotManager(base_dir=tmp_path)
    manager.create("draft1", _records())  # não congelado
    with pytest.raises(SnapshotError):
        ReferenceAnswerGenerator(manager, "draft1")


def test_factual_reference(gen) -> None:
    q = _q("factual", tickers=["PETR4"], end_date="2024-06-03",
           expected_answer=ExpectedAnswer(type="currency", tolerance=0.01))
    r = gen.generate_for(q)
    assert r.status == "generated"
    assert r.expected_answer["value"] == 37.8
    assert r.reference_audit["snapshot_id"] == "snap1"
    assert "close(PETR4" in r.reference_audit["formula"]


def test_calculation_reference(gen) -> None:
    q = _q("calculation", tickers=["PETR4"], start_date="2024-01-02", end_date="2024-06-03",
           expected_answer=ExpectedAnswer(type="percentage", unit="%", tolerance=0.1))
    r = gen.generate_for(q)
    assert r.status == "generated"
    assert r.expected_answer["value"] == pytest.approx(5.0, abs=1e-6)
    assert "preco_final" in r.reference_audit["formula"]


def test_comparison_reference(gen) -> None:
    q = _q("comparison", tickers=["PETR4", "VALE3"], start_date="2024-01-02", end_date="2024-06-03",
           expected_answer=ExpectedAnswer(type="categorical"))
    r = gen.generate_for(q)
    assert r.status == "generated"
    assert r.expected_answer["value"] == "PETR4"  # maior retorno
    assert r.reference_audit["best"] == "PETR4"


def test_interpretation_reference(gen) -> None:
    q = _q("interpretation", tickers=["PETR4"], start_date="2024-01-02", end_date="2024-06-03")
    r = gen.generate_for(q)
    assert r.status == "generated"
    assert r.expected_answer["value"] is None  # sem valor único
    assert any("tendência de alta" in f for f in r.required_facts)


def test_tool_use_reference(gen) -> None:
    q = _q("tool_use", tickers=["PETR4"], start_date="2024-01-02", end_date="2024-06-03",
           expected_tool="get_stock_history")
    r = gen.generate_for(q)
    assert r.status == "generated"
    assert r.reference_audit["expected_tool"] == "get_stock_history"
    assert r.reference_audit["expected_data"]["found"] is True


def test_missing_data_not_fabricated(gen) -> None:
    q = _q("calculation", tickers=["INEXISTENTE"], start_date="2024-01-02", end_date="2024-06-03",
           expected_answer=ExpectedAnswer(type="percentage"))
    r = gen.generate_for(q)
    assert r.status == "missing_data"
    assert r.expected_answer is None  # nunca inventa
