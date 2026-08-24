"""Exportação dos resultados de um experimento.

Gera os artefatos usados na pesquisa:
    - raw_results.csv            (todas as execuções, dados exatos)
    - aggregated_results.csv     (métricas agregadas por provider/model/strategy/category)
    - human_evaluation_blind.csv (avaliação humana cega) + mapeamento + rubrica
    - experiment_metadata.json   (metadados do experimento)

Representa exatamente os dados armazenados — não altera resultados.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.metrics import generate_blind_evaluation, load_price_table
from experiments.analysis import group_metrics, load_scored_dataframe
from experiments.runner.storage import ResultStore


def export_raw(db_path: str | Path, experiment_id: str, out_path: str | Path) -> int:
    store = ResultStore(db_path)
    try:
        return store.export_csv(out_path, experiment_id)
    finally:
        store.close()


def export_aggregated(
    scored_df, out_path: str | Path, by: tuple[str, ...] = ("provider", "model", "strategy", "category")
) -> int:
    agg = group_metrics(scored_df, list(by))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(out_path, index=False, encoding="utf-8")
    return len(agg)


def export_metadata(out_path: str | Path, metadata: dict) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def export_experiment(
    db_path: str | Path,
    experiment_id: str,
    out_dir: str | Path,
    metadata: dict | None = None,
    seed: int = 42,
) -> dict:
    """Exporta todos os artefatos de um experimento para ``out_dir``.

    Retorna um resumo com os caminhos e contagens gerados.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "raw_results.csv"
    n_raw = export_raw(db_path, experiment_id, raw_path)

    price_table = load_price_table()
    scored = load_scored_dataframe(db_path, experiment_id, price_table=price_table)

    agg_path = out_dir / "aggregated_results.csv"
    n_agg = export_aggregated(scored, agg_path) if not scored.empty else 0

    blind_path = out_dir / "human_evaluation_blind.csv"
    map_path = out_dir / "human_evaluation_mapping.json"
    n_blind = 0
    if not scored.empty:
        n_blind = generate_blind_evaluation(scored.to_dict("records"), blind_path, map_path, seed=seed)

    meta = {
        "experiment_id": experiment_id,
        "n_rows": n_raw,
        "price_table": price_table.metadata(),
        **(metadata or {}),
    }
    meta_path = out_dir / "experiment_metadata.json"
    export_metadata(meta_path, meta)

    return {
        "raw": str(raw_path),
        "aggregated": str(agg_path),
        "blind": str(blind_path),
        "mapping": str(map_path),
        "metadata": str(meta_path),
        "n_raw": n_raw,
        "n_aggregated": n_agg,
        "n_blind": n_blind,
    }
