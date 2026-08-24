"""Estatística descritiva e testes para a análise dos experimentos.

Escolhe testes adequados ao desenho (medidas relacionadas por questão) e a dados
ordinais (avaliações humanas): usa testes NÃO PARAMÉTRICOS por padrão (Friedman
para k técnicas relacionadas; Wilcoxon pareado com correção de Holm), reporta
tamanho de efeito e degrada com segurança quando os dados não permitem o teste.

Não inventa dados: se não houver variabilidade ou observações suficientes, indica
que o teste não é aplicável.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

try:  # scipy é opcional; sem ele, apenas a estatística descritiva funciona
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover
    _scipy_stats = None


def _clean(values) -> np.ndarray:
    arr = pd.to_numeric(pd.Series(list(values)), errors="coerce").to_numpy(dtype=float)
    return arr[~np.isnan(arr)]


def describe(values) -> dict:
    """Estatística descritiva com IC95% (t de Student) quando n ≥ 2."""
    arr = _clean(values)
    n = int(arr.size)
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None,
                "ci95_low": None, "ci95_high": None}
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    ci_low = ci_high = None
    if n > 1 and _scipy_stats is not None:
        sem = std / math.sqrt(n)
        t = _scipy_stats.t.ppf(0.975, df=n - 1)
        ci_low, ci_high = mean - t * sem, mean + t * sem
    return {
        "n": n, "mean": mean, "median": float(np.median(arr)), "std": std,
        "min": float(arr.min()), "max": float(arr.max()),
        "ci95_low": ci_low, "ci95_high": ci_high,
    }


def describe_by_strategy(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Estatística descritiva de ``metric`` por técnica."""
    if df.empty or metric not in df.columns:
        return pd.DataFrame()
    rows = []
    for strategy, group in df.groupby("strategy"):
        stats_dict = describe(group[metric])
        rows.append({"strategy": strategy, **stats_dict})
    return pd.DataFrame(rows)


def normality(values) -> dict:
    """Teste de Shapiro-Wilk (informa a escolha do teste)."""
    arr = _clean(values)
    if _scipy_stats is None or not (3 <= arr.size <= 5000) or np.ptp(arr) == 0:
        return {"test": "shapiro", "applicable": False, "p_value": None}
    stat, p = _scipy_stats.shapiro(arr)
    return {"test": "shapiro", "applicable": True, "statistic": float(stat), "p_value": float(p),
            "normal_at_0.05": bool(p > 0.05)}


def _pivot_by_block(df: pd.DataFrame, metric: str, strategies: list[str], block: str = "question_id") -> pd.DataFrame:
    """Matriz blocos (questões) × técnicas com a média de ``metric`` por célula."""
    sub = df[df["strategy"].isin(strategies)]
    pivot = sub.pivot_table(index=block, columns="strategy", values=metric, aggfunc="mean")
    pivot = pivot.reindex(columns=strategies).dropna(axis=0, how="any")
    return pivot


def friedman_test(df: pd.DataFrame, metric: str, strategies: list[str]) -> dict:
    """Teste de Friedman (k técnicas relacionadas por questão) + W de Kendall."""
    if _scipy_stats is None:
        return {"test": "friedman", "applicable": False, "reason": "scipy indisponível"}
    pivot = _pivot_by_block(df, metric, strategies)
    n_blocks, k = pivot.shape
    if k < 3 or n_blocks < 2:
        return {"test": "friedman", "applicable": False, "reason": "blocos/grupos insuficientes",
                "n_blocks": int(n_blocks), "k": int(k)}
    columns = [pivot[s].to_numpy() for s in strategies]
    if all(np.ptp(np.concatenate(columns)) == 0 for _ in [0]):
        return {"test": "friedman", "applicable": False, "reason": "sem variabilidade",
                "n_blocks": int(n_blocks), "k": int(k)}
    try:
        stat, p = _scipy_stats.friedmanchisquare(*columns)
    except ValueError as exc:
        return {"test": "friedman", "applicable": False, "reason": str(exc)}
    kendalls_w = float(stat / (n_blocks * (k - 1))) if n_blocks * (k - 1) else None
    return {"test": "friedman", "applicable": True, "statistic": float(stat), "p_value": float(p),
            "kendalls_w": kendalls_w, "n_blocks": int(n_blocks), "k": int(k)}


def holm_correction(pvalues: list[float]) -> list[float]:
    """Correção de Holm para múltiplas comparações."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvalues[idx]
        running = max(running, val)
        adjusted[idx] = min(1.0, running)
    return adjusted


def pairwise_wilcoxon(df: pd.DataFrame, metric: str, strategies: list[str]) -> list[dict]:
    """Wilcoxon pareado para cada par de técnicas, com correção de Holm.

    Tamanho de efeito: correlação bisserial de postos (rank-biserial).
    """
    if _scipy_stats is None:
        return []
    pivot = _pivot_by_block(df, metric, strategies)
    if pivot.shape[0] < 2:
        return []
    pairs, raw_p = [], []
    for i in range(len(strategies)):
        for j in range(i + 1, len(strategies)):
            a, b = strategies[i], strategies[j]
            x, y = pivot[a].to_numpy(), pivot[b].to_numpy()
            diff = x - y
            if np.all(diff == 0):
                pairs.append({"a": a, "b": b, "applicable": False, "reason": "sem diferença"})
                raw_p.append(1.0)
                continue
            try:
                stat, p = _scipy_stats.wilcoxon(x, y)
            except ValueError as exc:
                pairs.append({"a": a, "b": b, "applicable": False, "reason": str(exc)})
                raw_p.append(1.0)
                continue
            n = int(np.sum(diff != 0))
            rank_biserial = float(1 - (2 * stat) / (n * (n + 1) / 2)) if n else None
            pairs.append({
                "a": a, "b": b, "applicable": True, "statistic": float(stat),
                "p_value": float(p), "rank_biserial": rank_biserial,
                "median_diff": float(np.median(diff)), "n": n,
            })
            raw_p.append(p)

    applicable_idx = [i for i, pr in enumerate(pairs) if pr.get("applicable")]
    if applicable_idx:
        adj = holm_correction([raw_p[i] for i in applicable_idx])
        for slot, i in enumerate(applicable_idx):
            pairs[i]["p_value_holm"] = adj[slot]
    return pairs


@dataclass
class MetricAnalysis:
    metric: str
    descriptive: pd.DataFrame
    normality: dict
    friedman: dict
    pairwise: list[dict]


def analyze_metric(df: pd.DataFrame, metric: str, strategies: list[str] | None = None) -> MetricAnalysis:
    strategies = strategies or sorted(df["strategy"].dropna().unique().tolist())
    return MetricAnalysis(
        metric=metric,
        descriptive=describe_by_strategy(df, metric),
        normality=normality(df[metric]) if metric in df.columns else {"applicable": False},
        friedman=friedman_test(df, metric, strategies),
        pairwise=pairwise_wilcoxon(df, metric, strategies),
    )
