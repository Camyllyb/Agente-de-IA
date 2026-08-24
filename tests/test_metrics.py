"""Testes das métricas científicas (offline)."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from app.metrics import (
    build_scored_records,
    extract_number,
    factual_accuracy,
    generate_blind_evaluation,
    import_blind_evaluation,
    judge_answer,
    load_price_table,
    score_answer,
    success_rate,
    tool_accuracy,
    tool_correct,
)
from app.metrics.pricing import PriceTable
from app.services.llm.fake import FakeLLMProvider, make_fake_config


# --- Parsing / precisão factual ---------------------------------------------

def test_extract_number_formats() -> None:
    assert extract_number("Resposta final: 5.0%.") == 5.0
    assert extract_number("Resposta final: -17,95%") == -17.95
    assert extract_number("Resposta final: 41,00 BRL") == 41.0
    # Ignora o número do ticker.
    assert extract_number("PETR4.SA teve retorno de 5.0%") == 5.0
    assert extract_number("sem número") is None


def test_score_numeric_within_tolerance() -> None:
    expected = {"type": "numeric", "unit": "percent", "value": 5.0, "tolerance": 0.1}
    good = score_answer(expected, "Resposta final: 5.02%.")
    assert good.applicable and good.correct is True
    bad = score_answer(expected, "Resposta final: 9.0%.")
    assert bad.correct is False


def test_score_categorical() -> None:
    expected = {"type": "categorical", "value": "alta", "accept": ["alta", "subiu"]}
    assert score_answer(expected, "Resposta final: o preço subiu.").correct is True
    assert score_answer(expected, "Resposta final: caiu.").correct is False


def test_score_qualitative_not_applicable() -> None:
    result = score_answer({"type": "qualitative"}, "qualquer texto")
    assert result.applicable is False
    assert result.correct is None


# --- Tool accuracy / success -------------------------------------------------

def test_tool_correct() -> None:
    assert tool_correct(["calculate_return"], ["calculate_return"]) is True
    assert tool_correct(["calculate_return"], ["get_stock_quote"]) is False
    assert tool_correct([], ["get_stock_quote"]) is None


def test_success_rate() -> None:
    records = [{"error": None}, {"error": None}, {"error": "boom"}]
    assert success_rate(records) == 2 / 3


# --- Custo (tabela configurável e versionada) -------------------------------

def test_price_table_unconfigured_returns_none() -> None:
    table = load_price_table()  # pricing.yaml vem sem preços
    assert table.is_configured() is False
    assert table.estimate("qualquer-modelo", 1000, 500) is None


def test_price_table_configured_estimates() -> None:
    table = PriceTable(
        version="test",
        generated_at="2025-01-01",
        unit="per_1m_tokens",
        currency="USD",
        prices={"m1": {"input": 1.0, "output": 2.0}},
    )
    # 1_000_000 in * 1.0 + 500_000 out * 2.0/1e6 => 1.0 + 1.0 = 2.0
    assert table.estimate("m1", 1_000_000, 500_000) == 2.0
    assert table.estimate("desconhecido", 10, 10) is None


# --- Registros pontuados -----------------------------------------------------

def _records():
    return [
        {
            "question_id": "Q001", "model": "m", "error": None,
            "answer": "Resposta final: 5.0%.",
            "expected_answer": {"type": "numeric", "value": 5.0, "tolerance": 0.1},
            "tools_called": ["calculate_return"],
            "input_tokens": "10", "output_tokens": "20", "total_tokens": "30", "latency_ms": "12",
            "estimated_cost": None,
        },
        {
            "question_id": "Q009", "model": "m", "error": "timeout",
            "answer": "",
            "expected_answer": {"type": "numeric", "value": 41.0, "tolerance": 0.01},
            "tools_called": [],
            "input_tokens": "0", "output_tokens": "0", "total_tokens": "0", "latency_ms": "0",
            "estimated_cost": None,
        },
    ]


def test_build_scored_records_and_aggregates() -> None:
    questions_by_id = {
        "Q001": {"expected_tools": ["calculate_return"]},
        "Q009": {"expected_tools": ["get_stock_quote"]},
    }
    scored = build_scored_records(_records(), questions_by_id)
    assert scored[0]["is_correct"] is True
    assert scored[0]["tool_correct"] is True
    assert scored[0]["success"] is True
    assert scored[1]["success"] is False
    # precisão factual: Q001 correta; Q009 falhou (sem número) -> aplicável, incorreta
    assert factual_accuracy(scored) == 0.5
    # tool accuracy: Q001 correta, Q009 não usou ferramenta esperada
    assert tool_accuracy(scored) == 0.5


# --- Avaliação humana cega ---------------------------------------------------

def test_blind_evaluation_roundtrip(tmp_path) -> None:
    records = [
        {"id": 1, "question": "Q1?", "answer": "Resposta A", "model": "m1", "strategy": "zero_shot",
         "question_id": "Q001", "category": "return_calculation", "experiment_id": "e", "prompt_version": "zero_shot_v1", "provider": "fake", "error": None},
        {"id": 2, "question": "Q2?", "answer": "Resposta B", "model": "m2", "strategy": "few_shot",
         "question_id": "Q002", "category": "return_calculation", "experiment_id": "e", "prompt_version": "few_shot_v1", "provider": "fake", "error": None},
    ]
    csv_path = tmp_path / "blind.csv"
    map_path = tmp_path / "map.json"
    n = generate_blind_evaluation(records, csv_path, map_path, seed=1)
    assert n == 2

    content = csv_path.read_text(encoding="utf-8")
    # Cego: não expõe modelo nem técnica.
    assert "m1" not in content and "zero_shot" not in content
    assert (tmp_path / "RUBRICA.md").exists()

    # Preenche as notas e reimporta.
    lines = content.strip().splitlines()
    header = lines[0].split(",")
    filled = [",".join(header)]
    for line in lines[1:]:
        anon = line.split(",")[0]
        filled.append(f"{anon},qpergunta,resposta,5,4,3,2,otimo")
    csv_path.write_text("\n".join(filled), encoding="utf-8")

    imported = import_blind_evaluation(csv_path, map_path)
    assert len(imported) == 2
    assert all(r["evaluator"] == "human" for r in imported)
    assert all(r["clareza"] == 5 for r in imported)
    # o mapeamento reassocia modelo/técnica
    assert {r["model"] for r in imported} == {"m1", "m2"}


# --- LLM-as-a-judge ----------------------------------------------------------

def test_llm_judge_parses_scores() -> None:
    judge_json = json.dumps(
        {"clareza": 5, "relevancia": 4, "completude": 4, "precisao_percebida": 5, "justificativa": "boa"}
    )
    provider = FakeLLMProvider(make_fake_config(responses=[AIMessage(content=judge_json)]))
    result = judge_answer(provider, "pergunta?", "resposta.")
    assert result["is_ai"] is True
    assert result["evaluator"].startswith("llm_judge:")
    assert result["scores"]["clareza"] == 5


def test_llm_judge_handles_non_json() -> None:
    provider = FakeLLMProvider(make_fake_config(responses=[AIMessage(content="sem json aqui")]))
    result = judge_answer(provider, "pergunta?", "resposta.")
    assert all(v is None for v in result["scores"].values())
