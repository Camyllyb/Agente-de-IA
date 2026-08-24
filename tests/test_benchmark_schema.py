"""Testes do schema do benchmark (30 questões) e das validações (PROMPT 13)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.benchmark import (
    BenchmarkDataset,
    BenchmarkQuestion,
    ExpectedAnswer,
    validate_dataset,
)
from experiments.datasets import load_questions  # loader antigo (compat)


def _q(qid="Q001", **kwargs) -> BenchmarkQuestion:
    base = dict(id=qid, category="calculation", difficulty="medium")
    base.update(kwargs)
    return BenchmarkQuestion(**base)


def _dataset(questions) -> BenchmarkDataset:
    return BenchmarkDataset(dataset_version="test-v1", questions=questions)


# --- Normalização ------------------------------------------------------------

def test_difficulty_and_category_normalization_from_ptbr() -> None:
    q = BenchmarkQuestion(id="Q1", category="Cálculo", difficulty="Difícil")
    assert q.category.value == "calculation"
    assert q.difficulty.value == "hard"


def test_old_category_maps_to_new() -> None:
    q = BenchmarkQuestion(id="Q1", category="return_calculation", difficulty="easy")
    assert q.category.value == "calculation"


# --- Validações estruturais --------------------------------------------------

def test_duplicate_ids_detected() -> None:
    ds = _dataset([_q("Q001"), _q("Q001")])
    result = validate_dataset(ds)
    assert not result.ok
    assert any("duplicado" in e for e in result.errors)


def test_negative_tolerance_rejected_by_model() -> None:
    with pytest.raises(ValidationError):
        ExpectedAnswer(type="numeric", value=1.0, tolerance=-0.5)


def test_inconsistent_dates_detected() -> None:
    ds = _dataset([_q(start_date="2024-06-01", end_date="2024-01-01")])
    result = validate_dataset(ds)
    assert not result.ok
    assert any("start_date > end_date" in e for e in result.errors)


def test_invalid_tool_rejected() -> None:
    with pytest.raises(ValidationError):
        _q(expected_tool="ferramenta_inexistente")


def test_unknown_snapshot_detected() -> None:
    ds = _dataset([_q(snapshot_id="snap_x")])
    result = validate_dataset(ds, known_snapshots={"snap_y"})
    assert not result.ok
    assert any("snapshot inexistente" in e for e in result.errors)


# --- Validações estritas (congelamento) -------------------------------------

def test_strict_requires_reference_and_metrics() -> None:
    ds = _dataset([
        _q("Q001", question="Retorno da PETR4?", expected_answer=ExpectedAnswer(type="percentage"))
    ])
    result = validate_dataset(ds, strict=True)
    assert not result.ok
    assert any("sem métrica" in e for e in result.errors)
    assert any("sem gabarito" in e for e in result.errors)


def test_strict_passes_when_complete() -> None:
    ds = _dataset([
        _q(
            "Q001",
            question="Retorno da PETR4 entre datas?",
            expected_answer=ExpectedAnswer(type="percentage", value=5.0, unit="%", tolerance=0.1),
            evaluation_metrics=["factual_precision"],
            expected_tool="calculate_return",
        )
    ])
    result = validate_dataset(ds, strict=True)
    assert result.ok, result.errors


# --- Distribuição ------------------------------------------------------------

def test_enforce_distribution_flags_wrong_counts() -> None:
    ds = _dataset([_q(f"Q{i:03d}") for i in range(5)])
    result = validate_dataset(ds, enforce_distribution=True)
    assert not result.ok
    assert any("Total de questões" in e for e in result.errors)


# --- Compatibilidade / adaptação --------------------------------------------

def test_to_runner_dict_mapping() -> None:
    q = _q(
        tickers=["PETR4"],
        start_date="2024-01-02",
        end_date="2024-06-03",
        expected_tool="calculate_return",
        expected_answer=ExpectedAnswer(type="percentage", value=5.0, unit="%", tolerance=0.1),
    )
    d = q.to_runner_dict()
    assert d["params"]["symbol"] == "PETR4"
    assert d["expected_tools"] == ["calculate_return"]
    assert d["expected_answer"]["type"] == "numeric"


def test_old_dataset_still_loads() -> None:
    questions = load_questions()  # dataset sintético de 20 questões
    assert len(questions) == 20
    assert all("expected_answer" in q for q in questions)
