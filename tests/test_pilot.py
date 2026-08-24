"""Testes do piloto experimental (offline)."""

from __future__ import annotations

import pytest

from experiments.pilot import PILOT_LABEL, PilotConfig, run_pilot
from experiments.runner import ResultStore, oracle_model_spec


@pytest.fixture()
def store(tmp_path) -> ResultStore:
    s = ResultStore(tmp_path / "pilot.db")
    yield s
    s.close()


def test_pilot_runs_and_audits(store) -> None:
    config = PilotConfig(num_questions=4, repetitions=2)  # menor para o teste
    summary, prechecks, audit = run_pilot(store, oracle_model_spec(), config, experiment_id="PILOT_ONLY-test")
    assert prechecks["ready"] is True
    # 1 modelo × 3 técnicas × 4 questões × 2 repetições = 24
    assert summary.executed == 24
    assert audit["label"] == PILOT_LABEL
    assert audit["n_runs"] == 24
    assert "note" in audit and "PILOT_ONLY" in audit["note"]


def test_pilot_records_labeled_pilot_only(store) -> None:
    run_pilot(store, oracle_model_spec(), PilotConfig(num_questions=3, repetitions=1),
              experiment_id="PILOT_ONLY-test2")
    rows = store.fetch_all("PILOT_ONLY-test2")
    assert rows
    assert all(r["experiment_id"].startswith("PILOT_ONLY") for r in rows)


def test_pilot_halts_when_prechecks_fail(store) -> None:
    from app.models.llm import LLMConfig
    from experiments.runner import from_llm_config

    # provedor real sem chave -> api_key_available False -> não executa
    real_spec = from_llm_config(LLMConfig(provider="openai", model="algum-modelo"))
    summary, prechecks, audit = run_pilot(store, real_spec, PilotConfig(num_questions=2))
    assert prechecks["api_key_available"] is False
    assert summary is None
    assert audit.get("halted") is True
    assert store.count() == 0  # nada foi executado
