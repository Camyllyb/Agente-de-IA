"""Testes do sistema de experimentos (offline).

Exercitam o pipeline completo com o oráculo determinístico e snapshots: plano,
dry-run, execução, registro de falhas, persistência e exportação CSV.
"""

from __future__ import annotations

import pytest

from experiments.datasets import load_questions
from experiments.runner import (
    ExperimentRunner,
    ModelSpec,
    ResultStore,
    RunnerConfig,
    oracle_model_spec,
)


@pytest.fixture()
def questions() -> list[dict]:
    all_q = {q["id"]: q for q in load_questions()}
    # Uma de cada tipo com resposta automática.
    return [all_q["Q001"], all_q["Q009"], all_q["Q013"], all_q["Q016"]]


@pytest.fixture()
def store(tmp_path) -> ResultStore:
    s = ResultStore(tmp_path / "exp.db")
    yield s
    s.close()


def _config(**kwargs) -> RunnerConfig:
    base = dict(
        experiment_id="test-exp",
        strategies=["zero_shot", "few_shot", "chain_of_thought"],
        repetitions=1,
    )
    base.update(kwargs)
    return RunnerConfig(**base)


# --- Planejamento ------------------------------------------------------------

def test_plan_count(questions, store) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(), store)
    plan = runner.plan()
    # 1 modelo × 3 técnicas × 4 questões × 1 repetição
    assert plan.total == 12
    assert plan.effective == 12


def test_plan_respects_max_runs(questions, store) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(max_runs=5), store)
    assert runner.plan().effective == 5


def test_dry_run_executes_nothing(questions, store) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(dry_run=True), store)
    summary = runner.run()
    assert summary.executed == 0
    assert store.count() == 0


# --- Execução offline (3 técnicas × 4 questões) -----------------------------

def test_offline_pipeline_runs_and_persists(questions, store) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(), store)
    summary = runner.run()

    assert summary.executed == 12
    assert summary.succeeded == 12
    assert summary.failed == 0
    assert store.count("test-exp") == 12

    rows = store.fetch_all("test-exp")
    # Todos os campos científicos foram registrados.
    for row in rows:
        for field in (
            "experiment_id", "question_id", "category", "provider", "model",
            "strategy", "prompt_version", "answer", "expected_answer",
            "tools_called", "latency_ms", "total_tokens",
        ):
            assert field in row
        assert "Resposta final" in row["answer"]


def test_oracle_answers_use_tool_data(questions, store) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(), store)
    runner.run()
    rows = store.fetch_all("test-exp")
    q001_rows = [r for r in rows if r["question_id"] == "Q001"]
    # O oráculo ecoa o retorno real do snapshot (PETR4: +5.0%).
    assert all("5.0" in r["answer"] for r in q001_rows)
    assert all("calculate_return" in r["tools_called"] for r in q001_rows)


# --- Falha registrada e execução continua -----------------------------------

def test_failure_is_recorded_and_run_continues(questions, store) -> None:
    def _boom(_question):
        raise RuntimeError("provedor simulado com falha")

    failing = ModelSpec(provider="fake", model="broken", build=_boom)
    runner = ExperimentRunner([failing], questions, _config(strategies=["zero_shot"]), store)
    summary = runner.run()

    assert summary.executed == 4
    assert summary.failed == 4
    assert summary.succeeded == 0
    rows = store.fetch_all("test-exp")
    assert all(r["error"] for r in rows)
    # Nunca inventa resposta em caso de falha.
    assert all(r["answer"] == "" for r in rows)


# --- Exportação CSV ----------------------------------------------------------

def test_export_csv(questions, store, tmp_path) -> None:
    runner = ExperimentRunner([oracle_model_spec()], questions, _config(strategies=["zero_shot"]), store)
    runner.run()
    csv_path = tmp_path / "out.csv"
    n = store.export_csv(csv_path, "test-exp")
    assert n == 4
    content = csv_path.read_text(encoding="utf-8")
    assert "experiment_id" in content
    assert "Q001" in content
