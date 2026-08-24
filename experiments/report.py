"""Geração de figuras publicáveis e de um relatório de análise (Markdown).

Consome exclusivamente os dados fornecidos (registros pontuados). Não inventa,
completa nem estima observações ausentes. Quando um teste não é aplicável, isso
é declarado explicitamente.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from experiments.statistics import analyze_metric, describe_by_strategy

_STRATEGY_COLORS = {
    "zero_shot": "#4F46E5",
    "few_shot": "#0D9488",
    "chain_of_thought": "#D97706",
}

# Métricas analisadas (coluna -> rótulo, se "maior é melhor").
_METRICS = [
    ("correct_num", "Precisão factual", True),
    ("latency_ms", "Latência (ms)", False),
    ("total_tokens", "Tokens totais", False),
    ("estimated_cost", "Custo estimado", False),
]


def make_figures(df: pd.DataFrame, out_dir: str | Path) -> list[str]:
    """Gera figuras (PNG). Retorna os caminhos criados."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    strategies = [s for s in _STRATEGY_COLORS if s in df["strategy"].unique()]
    colors = [_STRATEGY_COLORS[s] for s in strategies]

    def _save(fig, name: str) -> None:
        path = out_dir / name
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        created.append(str(path))

    # Precisão × estratégia (barra)
    prec = df[df["factual_applicable"] == True].groupby("strategy")["correct_num"].mean()  # noqa: E712
    prec = prec.reindex(strategies)
    if prec.notna().any():
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(strategies, prec.values, color=colors)
        ax.set_ylabel("Precisão factual")
        ax.set_ylim(0, 1)
        ax.set_title("Precisão × estratégia")
        _save(fig, "precisao_por_estrategia.png")

    # Latência e tokens × estratégia (boxplot)
    for column, label, fname in [
        ("latency_ms", "Latência (ms)", "latencia_por_estrategia.png"),
        ("total_tokens", "Tokens totais", "tokens_por_estrategia.png"),
    ]:
        data = [df[df["strategy"] == s][column].dropna().to_numpy() for s in strategies]
        if any(len(d) for d in data):
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.boxplot(data, tick_labels=strategies)
            ax.set_ylabel(label)
            ax.set_title(f"{label} × estratégia")
            _save(fig, fname)

    # Custo × estratégia (barra) — só se houver custo
    if df["estimated_cost"].notna().any():
        cost = df.groupby("strategy")["estimated_cost"].mean().reindex(strategies)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(strategies, cost.values, color=colors)
        ax.set_ylabel("Custo estimado médio")
        ax.set_title("Custo × estratégia")
        _save(fig, "custo_por_estrategia.png")

    # Modelo × estratégia (precisão) — heatmap simples
    models = sorted(df["model"].dropna().unique().tolist())
    if len(models) > 1:
        pivot = (
            df[df["factual_applicable"] == True]  # noqa: E712
            .pivot_table(index="model", columns="strategy", values="correct_num", aggfunc="mean")
            .reindex(columns=strategies)
        )
        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            im = ax.imshow(pivot.values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
            ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=30, ha="right")
            ax.set_yticks(range(len(pivot.index)), pivot.index)
            fig.colorbar(im, ax=ax, label="Precisão")
            ax.set_title("Modelo × estratégia (precisão)")
            _save(fig, "modelo_por_estrategia.png")

    return created


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _describe_table(df: pd.DataFrame, metric: str, label: str) -> list[str]:
    desc = describe_by_strategy(df, metric)
    if desc.empty:
        return [f"### {label}", "", "_Sem dados._", ""]
    lines = [f"### {label}", "", "| Técnica | n | média | mediana | dp | mín | máx | IC95% |",
             "|---|---|---|---|---|---|---|---|"]
    for _, row in desc.iterrows():
        ci = (
            f"[{_fmt(row['ci95_low'])}, {_fmt(row['ci95_high'])}]"
            if row["ci95_low"] is not None else "—"
        )
        lines.append(
            f"| {row['strategy']} | {row['n']} | {_fmt(row['mean'])} | {_fmt(row['median'])} | "
            f"{_fmt(row['std'])} | {_fmt(row['min'])} | {_fmt(row['max'])} | {ci} |"
        )
    lines.append("")
    return lines


def _test_block(df: pd.DataFrame, metric: str, label: str) -> list[str]:
    analysis = analyze_metric(df, metric)
    fr = analysis.friedman
    lines = [f"**Teste (Friedman) — {label}:** "]
    if fr.get("applicable"):
        lines[-1] += (
            f"χ²={fr['statistic']:.4f}, p={fr['p_value']:.4g}, "
            f"W de Kendall={_fmt(fr.get('kendalls_w'))}, blocos={fr['n_blocks']}."
        )
        for pair in analysis.pairwise:
            if pair.get("applicable"):
                lines.append(
                    f"- {pair['a']} vs {pair['b']}: p={pair['p_value']:.4g} "
                    f"(Holm={_fmt(pair.get('p_value_holm'))}), "
                    f"rank-biserial={_fmt(pair.get('rank_biserial'))}."
                )
    else:
        lines[-1] += f"não aplicável ({fr.get('reason', 'dados insuficientes')})."
    lines.append("")
    return lines


def generate_markdown_report(
    df: pd.DataFrame,
    out_dir: str | Path,
    data_label: str,
    make_plots: bool = True,
) -> str:
    """Gera REPORT.md (e figuras) a partir dos dados fornecidos."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Análise dos resultados",
        "",
        f"**Origem dos dados:** {data_label}",
        f"**Execuções:** {len(df)} · **modelos:** {df['model'].nunique()} · "
        f"**técnicas:** {df['strategy'].nunique()} · **questões:** {df['question_id'].nunique()}",
        "",
    ]

    if df.empty:
        lines.append("_Nenhum dado disponível para análise._")
        path = out_dir / "REPORT.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    lines += ["## Estatística descritiva por técnica", ""]
    for column, label, _ in _METRICS:
        if column in df.columns and df[column].notna().any():
            lines += _describe_table(df, column, label)

    lines += ["## Testes de significância", ""]
    lines += _test_block(df, "correct_num", "Precisão factual")
    lines += _test_block(df, "latency_ms", "Latência")
    lines += _test_block(df, "total_tokens", "Tokens")

    figures: list[str] = []
    if make_plots:
        try:
            figures = make_figures(df, out_dir / "figures")
        except Exception as exc:  # pragma: no cover
            lines.append(f"_Falha ao gerar figuras: {exc}_")
    if figures:
        lines += ["", "## Figuras", ""]
        for fig in figures:
            name = Path(fig).name
            lines.append(f"![{name}](figures/{name})")
    lines.append("")

    path = out_dir / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
