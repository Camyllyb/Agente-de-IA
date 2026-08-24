"""Testes do módulo de estatística (offline, com dados sintéticos com variância)."""

from __future__ import annotations

import pandas as pd
import pytest

from experiments.statistics import (
    describe,
    describe_by_strategy,
    friedman_test,
    holm_correction,
    pairwise_wilcoxon,
)


def _synthetic_df() -> pd.DataFrame:
    """3 técnicas × 6 questões com variabilidade controlada."""
    rows = []
    # Precisão: zero_shot pior, chain_of_thought melhor (padrão claro).
    correctness = {
        "zero_shot": [1, 0, 0, 0, 1, 0],
        "few_shot": [1, 1, 0, 1, 1, 0],
        "chain_of_thought": [1, 1, 1, 1, 1, 1],
    }
    latency = {
        "zero_shot": [50, 55, 60, 52, 58, 54],
        "few_shot": [70, 72, 75, 71, 74, 73],
        "chain_of_thought": [90, 95, 92, 96, 93, 94],
    }
    for strategy in correctness:
        for i in range(6):
            rows.append({
                "strategy": strategy,
                "model": "m1",
                "question_id": f"Q{i:03d}",
                "factual_applicable": True,
                "correct_num": float(correctness[strategy][i]),
                "latency_ms": latency[strategy][i],
                "total_tokens": 100 + i,
                "estimated_cost": None,
                "success": True,
            })
    return pd.DataFrame(rows)


def test_describe_basic() -> None:
    d = describe([1, 2, 3, 4, 5])
    assert d["n"] == 5
    assert d["mean"] == 3.0
    assert d["median"] == 3.0
    assert d["ci95_low"] is not None and d["ci95_low"] < 3.0 < d["ci95_high"]


def test_describe_empty() -> None:
    d = describe([None, float("nan")])
    assert d["n"] == 0 and d["mean"] is None


def test_describe_by_strategy() -> None:
    df = _synthetic_df()
    desc = describe_by_strategy(df, "latency_ms")
    assert set(desc["strategy"]) == {"zero_shot", "few_shot", "chain_of_thought"}


def test_friedman_applicable_with_variability() -> None:
    df = _synthetic_df()
    result = friedman_test(df, "latency_ms", ["zero_shot", "few_shot", "chain_of_thought"])
    assert result["applicable"] is True
    assert result["p_value"] < 0.05  # padrão de latência é forte
    assert result["kendalls_w"] is not None


def test_friedman_not_applicable_without_variability() -> None:
    df = _synthetic_df()
    df["const"] = 1.0
    result = friedman_test(df, "const", ["zero_shot", "few_shot", "chain_of_thought"])
    assert result["applicable"] is False


def test_pairwise_wilcoxon_holm() -> None:
    df = _synthetic_df()
    pairs = pairwise_wilcoxon(df, "latency_ms", ["zero_shot", "few_shot", "chain_of_thought"])
    applicable = [p for p in pairs if p.get("applicable")]
    assert len(applicable) == 3
    assert all("p_value_holm" in p for p in applicable)


def test_holm_correction_monotonic() -> None:
    adj = holm_correction([0.01, 0.02, 0.03])
    assert all(0.0 <= a <= 1.0 for a in adj)
    # Holm aumenta (ou mantém) os p-valores.
    assert adj[0] >= 0.01
