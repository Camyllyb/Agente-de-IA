"""Análise/agregação dos resultados armazenados (para o painel e o artigo).

Funções puras baseadas em pandas — testáveis e reutilizadas tanto pela página
Streamlit de Experimentos quanto pela análise estatística. Representam exatamente
os dados armazenados: não alteram nem "melhoram" resultados.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app.metrics import build_scored_records, load_price_table, to_dataframe
from experiments.datasets import load_questions
from experiments.runner.storage import ResultStore


def list_experiments(db_path: str | Path) -> list[str]:
    """IDs de experimentos presentes no banco (vazio se o banco não existe)."""
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT DISTINCT experiment_id FROM runs ORDER BY experiment_id"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [r[0] for r in rows if r[0]]


def load_scored_dataframe(
    db_path: str | Path,
    experiment_id: str | None = None,
    questions: list[dict] | None = None,
    price_table=None,
) -> pd.DataFrame:
    """Carrega os registros e adiciona colunas de métricas automáticas."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    store = ResultStore(db_path)
    try:
        records = store.fetch_all(experiment_id)
    finally:
        store.close()
    if not records:
        return pd.DataFrame()

    questions = questions if questions is not None else load_questions()
    qmap = {q["id"]: q for q in questions}
    price_table = price_table if price_table is not None else load_price_table()
    scored = build_scored_records(records, qmap, price_table)
    df = to_dataframe(scored)

    # Coluna numérica auxiliar para precisão (True->1, False->0, None->NaN).
    df["correct_num"] = df["is_correct"].map({True: 1.0, False: 0.0})
    df["tool_correct_num"] = df["tool_correct"].map({True: 1.0, False: 0.0})
    return df


def overview(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total": 0, "models": 0, "techniques": 0, "questions": 0, "success": 0, "errors": 0}
    return {
        "total": len(df),
        "models": df["model"].nunique(),
        "techniques": df["strategy"].nunique(),
        "questions": df["question_id"].nunique(),
        "success": int(df["success"].sum()),
        "errors": int((~df["success"]).sum()),
    }


def _precision(group: pd.DataFrame) -> float | None:
    applicable = group[group["factual_applicable"] == True]  # noqa: E712
    if applicable.empty:
        return None
    return float(applicable["correct_num"].mean())


def _tool_acc(group: pd.DataFrame) -> float | None:
    required = group[group["tool_required"] == True]  # noqa: E712
    if required.empty:
        return None
    return float(required["tool_correct_num"].mean())


def group_metrics(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Agrega métricas por uma ou mais colunas (ex.: ['strategy'])."""
    if df.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in df.groupby(by):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(by, key_values))
        row.update(
            {
                "n": len(group),
                "precisao": _precision(group),
                "tool_accuracy": _tool_acc(group),
                "taxa_sucesso": float(group["success"].mean()),
                "latencia_ms_media": float(group["latency_ms"].mean()),
                "tokens_total_medio": float(group["total_tokens"].mean()),
                "tokens_in_medio": float(group["input_tokens"].mean()),
                "tokens_out_medio": float(group["output_tokens"].mean()),
                "custo_medio": (
                    float(group["estimated_cost"].mean())
                    if group["estimated_cost"].notna().any()
                    else None
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def technique_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela comparativa por técnica (precisão, latência, tokens, custo...)."""
    return group_metrics(df, ["strategy"])


def repetition_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Consistência entre repetições: desvio-padrão médio por técnica.

    Para questões numéricas usa o desvio do valor previsto; caso contrário, o
    desvio da corretude (0/1) entre repetições do mesmo (modelo, técnica, questão).
    """
    if df.empty or "repetition" not in df.columns:
        return pd.DataFrame()
    working = df.copy()
    working["predicted_num"] = pd.to_numeric(working["predicted_value"], errors="coerce")
    group_cols = ["strategy", "model", "question_id"]
    stds = []
    for _keys, group in working.groupby(group_cols):
        if len(group) < 2:
            continue
        if group["predicted_num"].notna().any():
            std = group["predicted_num"].std(ddof=0)
        else:
            std = group["correct_num"].std(ddof=0)
        if pd.notna(std):
            stds.append({"strategy": group["strategy"].iloc[0], "std": float(std)})
    if not stds:
        return pd.DataFrame()
    out = pd.DataFrame(stds).groupby("strategy", as_index=False)["std"].mean()
    return out.rename(columns={"std": "desvio_medio_repeticoes"})
