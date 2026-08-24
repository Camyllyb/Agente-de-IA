"""Concordância entre avaliadores (para a avaliação humana).

Implementa Cohen's Kappa, Kappa ponderado (linear/quadrático) e Krippendorff's
Alpha (nominal/ordinal/intervalar). Cada função retorna ``None`` quando os dados
não permitem o cálculo — nunca força um resultado.
"""

from __future__ import annotations

from collections import Counter
from itertools import permutations

import numpy as np


def _paired(a, b):
    return [(x, y) for x, y in zip(a, b) if x is not None and y is not None]


def cohen_kappa(a, b) -> float | None:
    """Cohen's Kappa para dois avaliadores (categórico)."""
    pairs = _paired(a, b)
    if len(pairs) < 2:
        return None
    n = len(pairs)
    categories = sorted({v for pair in pairs for v in pair})
    po = sum(1 for x, y in pairs if x == y) / n
    ca = Counter(x for x, _ in pairs)
    cb = Counter(y for _, y in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in categories)
    if abs(1 - pe) < 1e-12:
        return None
    return (po - pe) / (1 - pe)


def weighted_kappa(a, b, weights: str = "quadratic") -> float | None:
    """Kappa ponderado (para escalas ordinais)."""
    pairs = _paired(a, b)
    if len(pairs) < 2:
        return None
    ratings = sorted({v for pair in pairs for v in pair})
    k = len(ratings)
    if k < 2:
        return None
    idx = {r: i for i, r in enumerate(ratings)}
    n = len(pairs)

    observed = np.zeros((k, k))
    for x, y in pairs:
        observed[idx[x], idx[y]] += 1
    observed /= n

    row = observed.sum(axis=1)
    col = observed.sum(axis=0)
    expected = np.outer(row, col)

    weight = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if weights == "linear":
                weight[i, j] = abs(i - j) / (k - 1)
            else:  # quadratic
                weight[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)

    den = float((weight * expected).sum())
    if abs(den) < 1e-12:
        return None
    return 1 - float((weight * observed).sum()) / den


def krippendorff_alpha(reliability_data, level: str = "ordinal") -> float | None:
    """Krippendorff's Alpha.

    Args:
        reliability_data: lista de avaliadores; cada um é uma sequência alinhada
            por unidade (use ``None`` para valores ausentes).
        level: "nominal", "ordinal" ou "interval".
    """
    matrix = [list(r) for r in reliability_data]
    if len(matrix) < 2:
        return None
    n_units = max(len(r) for r in matrix)
    for r in matrix:
        r.extend([None] * (n_units - len(r)))

    # Unidades com ≥2 avaliações.
    units = []
    for u in range(n_units):
        vals = [r[u] for r in matrix if r[u] is not None]
        if len(vals) >= 2:
            units.append(vals)
    if not units:
        return None

    values = sorted({v for vals in units for v in vals})
    vindex = {v: i for i, v in enumerate(values)}
    k = len(values)

    # Matriz de coincidências.
    coincidence = np.zeros((k, k))
    for vals in units:
        m = len(vals)
        counts = Counter(vals)
        for c in counts:
            for d in counts:
                if c == d:
                    pairs = counts[c] * (counts[c] - 1)
                else:
                    pairs = counts[c] * counts[d]
                coincidence[vindex[c], vindex[d]] += pairs / (m - 1)

    marginals = coincidence.sum(axis=1)
    n_total = marginals.sum()
    if n_total < 2:
        return None

    def metric(ci: int, cj: int) -> float:
        vi, vj = values[ci], values[cj]
        if level == "nominal":
            return 0.0 if ci == cj else 1.0
        if level == "interval":
            return float((vi - vj) ** 2)
        # ordinal
        lo, hi = (ci, cj) if ci <= cj else (cj, ci)
        g = marginals[lo:hi + 1].sum() - (marginals[lo] + marginals[hi]) / 2.0
        return float(g ** 2)

    do = 0.0
    de = 0.0
    for ci in range(k):
        for cj in range(k):
            do += coincidence[ci, cj] * metric(ci, cj)
            de += marginals[ci] * marginals[cj] * metric(ci, cj)
    do /= n_total
    de /= n_total * (n_total - 1)
    if abs(de) < 1e-12:
        return None
    return 1 - do / de


def pairwise_kappa_matrix(ratings_by_rater: dict[str, list], weighted: bool = True) -> dict:
    """Kappa (ponderado por padrão) entre cada par de avaliadores."""
    result = {}
    raters = list(ratings_by_rater)
    for a, b in permutations(raters, 2):
        if (b, a) in result:
            continue
        fn = weighted_kappa if weighted else cohen_kappa
        result[(a, b)] = fn(ratings_by_rater[a], ratings_by_rater[b])
    return result
