"""Testes da separação Experimento A (llm_only) x B (agent) — PROMPT 18."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.metrics import (
    build_scored_records,
    data_grounding_accuracy,
    task_success_rate,
    tool_execution_success_rate,
    tool_selection_accuracy,
)
from app.models.llm import LLMConfig
from app.services.llm.fake import make_fake_config
from experiments.datasets import load_questions
from experiments.runner import (
    ExperimentRunner,
    ResultStore,
    RunnerConfig,
    from_llm_config,
    oracle_model_spec,
)


@pytest.fixture()
def questions() -> list[dict]:
    q = {x["id"]: x for x in load_questions()}
    return [q["Q001"], q["Q009"]]  # cálculo de retorno + cotação


@pytest.fixture()
def store(tmp_path) -> ResultStore:
    s = ResultStore(tmp_path / "ab.db")
    yield s
    s.close()


def _fake_llm_spec():
    config = LLMConfig(
        provider="fake", model="fake-llm",
        extra=make_fake_config(responses=[AIMessage(content="Resposta final: 5.0%.")]).extra,
    )
    return from_llm_config(config)


def test_agent_experiment_records_type(questions, store) -> None:
    config = RunnerConfig(
        experiment_id="exp-agent", strategies=["zero_shot"], repetitions=1,
        experiment_type="agent", protocol_checksum="chk123",
    )
    ExperimentRunner([oracle_model_spec()], questions, config, store).run()
    rows = store.fetch_all("exp-agent")
    assert all(r["experiment_type"] == "agent" for r in rows)
    assert all(r["protocol_checksum"] == "chk123" for r in rows)
    # o agente usa ferramentas
    assert any(r["tools_called"] and r["tools_called"] != "[]" for r in rows)


def test_llm_only_experiment_records_type(questions, store) -> None:
    config = RunnerConfig(
        experiment_id="exp-llm", strategies=["zero_shot"], repetitions=1,
        experiment_type="llm_only",
    )
    ExperimentRunner([_fake_llm_spec()], questions, config, store).run()
    rows = store.fetch_all("exp-llm")
    assert all(r["experiment_type"] == "llm_only" for r in rows)
    # experimento A NÃO usa ferramentas
    assert all(r["tools_called"] in ("[]", None) for r in rows)


def test_experiments_not_mixed(questions, store) -> None:
    ExperimentRunner([oracle_model_spec()], questions,
                     RunnerConfig("A", ["zero_shot"], experiment_type="agent"), store).run()
    ExperimentRunner([_fake_llm_spec()], questions,
                     RunnerConfig("B", ["zero_shot"], experiment_type="llm_only"), store).run()
    types_a = {r["experiment_type"] for r in store.fetch_all("A")}
    types_b = {r["experiment_type"] for r in store.fetch_all("B")}
    assert types_a == {"agent"}
    assert types_b == {"llm_only"}


def test_agentic_metrics_only_for_agent(questions, store) -> None:
    ExperimentRunner([oracle_model_spec()], questions,
                     RunnerConfig("A", ["zero_shot"], experiment_type="agent"), store).run()
    qmap = {q["id"]: q for q in load_questions()}
    scored = build_scored_records(store.fetch_all("A"), qmap)
    # métricas agentivas disponíveis para o agente
    assert tool_selection_accuracy(scored) is not None
    assert tool_execution_success_rate(scored) is not None
    assert data_grounding_accuracy(scored) is not None
    assert task_success_rate(scored) is not None
    assert all(r["experiment_type"] == "agent" for r in scored)
