"""Testes do módulo de análise/agregação de resultados (offline)."""

from __future__ import annotations

import pytest

from experiments.analysis import (
    list_experiments,
    load_scored_dataframe,
    overview,
    repetition_consistency,
    technique_comparison,
)
from experiments.datasets import load_questions
from experiments.runner import ExperimentRunner, ResultStore, RunnerConfig, oracle_model_spec


@pytest.fixture()
def db_path(tmp_path) -> str:
    all_q = {q["id"]: q for q in load_questions()}
    questions = [all_q["Q001"], all_q["Q013"], all_q["Q016"]]
    db = tmp_path / "exp.db"
    store = ResultStore(db)
    config = RunnerConfig(
        experiment_id="ana-exp",
        strategies=["zero_shot", "few_shot", "chain_of_thought"],
        repetitions=2,
    )
    ExperimentRunner([oracle_model_spec()], questions, config, store).run()
    store.close()
    return str(db)


def test_list_experiments(db_path) -> None:
    assert "ana-exp" in list_experiments(db_path)


def test_overview(db_path) -> None:
    df = load_scored_dataframe(db_path, "ana-exp")
    ov = overview(df)
    assert ov["total"] == 18  # 1 modelo × 3 técnicas × 3 questões × 2 repetições
    assert ov["techniques"] == 3
    assert ov["questions"] == 3
    assert ov["errors"] == 0


def test_technique_comparison_precision(db_path) -> None:
    df = load_scored_dataframe(db_path, "ana-exp")
    comp = technique_comparison(df)
    assert set(comp["strategy"]) == {"zero_shot", "few_shot", "chain_of_thought"}
    # O oráculo responde corretamente às questões auto-avaliáveis -> precisão 1.0.
    assert (comp["precisao"] == 1.0).all()
    assert (comp["taxa_sucesso"] == 1.0).all()
    # custo não configurado -> None
    assert comp["custo_medio"].isna().all()


def test_repetition_consistency(db_path) -> None:
    df = load_scored_dataframe(db_path, "ana-exp")
    cons = repetition_consistency(df)
    assert not cons.empty
    assert "desvio_medio_repeticoes" in cons.columns


def test_empty_db_returns_empty(tmp_path) -> None:
    df = load_scored_dataframe(tmp_path / "nao_existe.db")
    assert df.empty
    assert overview(df)["total"] == 0
