"""Página 'Experimentos' — painel dos resultados reais armazenados.

Lê o banco de resultados e apresenta visão geral, comparação de técnicas,
gráficos e filtros. Representa exatamente os dados armazenados — não altera nem
"melhora" resultados.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = next(p for p in _HERE.parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.config.settings import get_settings  # noqa: E402
from experiments.analysis import (  # noqa: E402
    group_metrics,
    list_experiments,
    load_scored_dataframe,
    overview,
    repetition_consistency,
    technique_comparison,
)
from lib.theme import inject_theme, render_footer, render_header  # noqa: E402

STRATEGY_COLORS = {
    "zero_shot": "#4F46E5",
    "few_shot": "#0D9488",
    "chain_of_thought": "#D97706",
}
_CATEGORICAL = ["#4F46E5", "#0D9488", "#D97706", "#DB2777", "#2563EB", "#65A30D"]

st.set_page_config(page_title="Experimentos · Financial Prompt Lab", page_icon="🧪", layout="wide")
inject_theme()
render_header(
    title="Experimentos",
    subtitle="Comparação empírica entre técnicas de prompting sob métricas objetivas.",
)

settings = get_settings()
DB_PATH = settings.database_path
experiments = list_experiments(DB_PATH)


def _empty_state() -> None:
    st.info(
        "Nenhum resultado encontrado no banco. Gere dados executando o runner de "
        "experimentos e recarregue esta página."
    )
    st.markdown(
        "```bash\n"
        "# pré-visualização (sem chamadas)\n"
        "python -m experiments.runner --dry-run\n\n"
        "# pipeline offline (oráculo determinístico — não é um LLM real)\n"
        "python -m experiments.runner --oracle\n"
        "```"
    )
    render_footer()


if not experiments:
    _empty_state()
    st.stop()

# --- Filtros ----------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔎 Filtros")
    exp_choice = st.selectbox("Experimento", ["Todos", *experiments])
    experiment_id = None if exp_choice == "Todos" else exp_choice

df = load_scored_dataframe(DB_PATH, experiment_id)
if df.empty:
    _empty_state()
    st.stop()

with st.sidebar:
    models = sorted(df["model"].dropna().unique().tolist())
    strategies = sorted(df["strategy"].dropna().unique().tolist())
    categories = sorted(df["category"].dropna().unique().tolist())
    sel_models = st.multiselect("Modelo", models, default=models)
    sel_strategies = st.multiselect("Técnica", strategies, default=strategies)
    sel_categories = st.multiselect("Categoria", categories, default=categories)

    exp_types = sorted(x for x in df.get("experiment_type", pd.Series(dtype=str)).dropna().unique())
    sel_exp_types = exp_types
    if len(exp_types) > 1:
        st.markdown("**Tipo de experimento**")
        st.caption("Experimento A (llm_only) e B (agent) nunca são misturados.")
        sel_exp_types = st.multiselect("Tipo", exp_types, default=exp_types)

mask = (
    df["model"].isin(sel_models)
    & df["strategy"].isin(sel_strategies)
    & df["category"].isin(sel_categories)
)
if "experiment_type" in df.columns and exp_types:
    mask = mask & df["experiment_type"].isin(sel_exp_types)
df = df[mask]
if df.empty:
    st.warning("Nenhum registro para os filtros selecionados.")
    st.stop()

# Aviso honesto quando os dados vêm do oráculo (não é desempenho de LLM real).
if (df["model"] == "oracle-fake").any():
    st.warning(
        "Este experimento contém resultados do **oráculo determinístico** "
        "(`oracle-fake`), usados para validar o pipeline. Eles **não** representam "
        "o desempenho de um modelo de linguagem real."
    )

# --- Visão geral ------------------------------------------------------------
st.subheader("Visão geral")
ov = overview(df)
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Execuções", ov["total"])
c2.metric("Modelos", ov["models"])
c3.metric("Técnicas", ov["techniques"])
c4.metric("Questões", ov["questions"])
c5.metric("Sucesso", ov["success"])
c6.metric("Erros", ov["errors"])

# --- Comparação das técnicas ------------------------------------------------
st.subheader("Comparação das técnicas")
comp = technique_comparison(df)
display = comp.copy()
display["precisao"] = display["precisao"].apply(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
display["tool_accuracy"] = display["tool_accuracy"].apply(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
display["taxa_sucesso"] = display["taxa_sucesso"].apply(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
display["latencia_ms_media"] = display["latencia_ms_media"].round(1)
display["tokens_total_medio"] = display["tokens_total_medio"].round(1)
display["custo_medio"] = display["custo_medio"].apply(lambda v: f"{v:.6f}" if pd.notna(v) else "—")
display = display.rename(
    columns={
        "strategy": "Técnica", "n": "N", "precisao": "Precisão",
        "tool_accuracy": "Tool acc.", "taxa_sucesso": "Sucesso",
        "latencia_ms_media": "Latência (ms)", "tokens_total_medio": "Tokens",
        "custo_medio": "Custo", "tokens_in_medio": "Tokens in", "tokens_out_medio": "Tokens out",
    }
)
st.dataframe(
    display[["Técnica", "N", "Precisão", "Tool acc.", "Sucesso", "Latência (ms)", "Tokens", "Custo"]],
    use_container_width=True,
    hide_index=True,
)
st.caption("Clareza/Relevância/Completude vêm da avaliação humana (importe o CSV cego para incluí-las).")

# --- Métricas agentivas (Experimento B) -------------------------------------
agent_df = df[df.get("experiment_type") == "agent"] if "experiment_type" in df.columns else df
if not agent_df.empty and agent_df["tool_required"].any():
    from app.metrics import (
        data_grounding_accuracy,
        task_success_rate,
        tool_execution_success_rate,
        tool_selection_accuracy,
    )

    st.subheader("Métricas agentivas (Experimento B)")
    rows = agent_df.to_dict("records")

    def _pct(v):
        return f"{v:.1%}" if v is not None else "—"

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Tool Selection", _pct(tool_selection_accuracy(rows)))
    a2.metric("Tool Execution", _pct(tool_execution_success_rate(rows)))
    a3.metric("Data Grounding", _pct(data_grounding_accuracy(rows)))
    a4.metric("Task Success", _pct(task_success_rate(rows)))


# --- Gráficos ---------------------------------------------------------------
def _strategy_scale():
    domain = [s for s in STRATEGY_COLORS if s in df["strategy"].unique()]
    return alt.Scale(domain=domain, range=[STRATEGY_COLORS[s] for s in domain])


def _bar_by_strategy(data: pd.DataFrame, y: str, y_title: str, pct: bool = False):
    if data.empty or data[y].isna().all():
        st.caption(f"Sem dados para: {y_title}.")
        return
    axis = alt.Axis(format="%") if pct else alt.Axis()
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("strategy:N", title="Técnica", sort=list(STRATEGY_COLORS.keys())),
            y=alt.Y(f"{y}:Q", title=y_title, axis=axis),
            color=alt.Color("strategy:N", scale=_strategy_scale(), legend=None),
            tooltip=["strategy", alt.Tooltip(f"{y}:Q", format=".4f")],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)


st.subheader("Precisão e eficiência por técnica")
g1, g2 = st.columns(2)
with g1:
    st.markdown("**Precisão factual por técnica**")
    _bar_by_strategy(comp, "precisao", "Precisão", pct=True)
with g2:
    st.markdown("**Latência média por técnica (ms)**")
    _bar_by_strategy(comp, "latencia_ms_media", "Latência (ms)")

g3, g4 = st.columns(2)
with g3:
    st.markdown("**Tokens totais médios por técnica**")
    _bar_by_strategy(comp, "tokens_total_medio", "Tokens")
with g4:
    st.markdown("**Custo médio por técnica**")
    if comp["custo_medio"].notna().any():
        _bar_by_strategy(comp, "custo_medio", "Custo estimado")
    else:
        st.caption("Custo não configurado (tabela de preços vazia) → sem dados de custo.")

# Desempenho por modelo e modelo × técnica
st.subheader("Desempenho por modelo")
by_model = group_metrics(df, ["model"])
mm1, mm2 = st.columns(2)
with mm1:
    st.markdown("**Precisão por modelo**")
    if not by_model.empty and by_model["precisao"].notna().any():
        chart = (
            alt.Chart(by_model)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("model:N", title="Modelo"),
                y=alt.Y("precisao:Q", title="Precisão", axis=alt.Axis(format="%")),
                color=alt.Color("model:N", scale=alt.Scale(range=_CATEGORICAL), legend=None),
                tooltip=["model", alt.Tooltip("precisao:Q", format=".2%")],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("Sem dados de precisão por modelo.")
with mm2:
    st.markdown("**Modelo × técnica (precisão)**")
    mt = group_metrics(df, ["model", "strategy"])
    if not mt.empty and mt["precisao"].notna().any():
        chart = (
            alt.Chart(mt)
            .mark_rect()
            .encode(
                x=alt.X("strategy:N", title="Técnica"),
                y=alt.Y("model:N", title="Modelo"),
                color=alt.Color("precisao:Q", title="Precisão", scale=alt.Scale(scheme="blues")),
                tooltip=["model", "strategy", alt.Tooltip("precisao:Q", format=".2%")],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("Sem dados suficientes para o cruzamento modelo × técnica.")

# Categoria e consistência
st.subheader("Categoria da questão e consistência")
cc1, cc2 = st.columns(2)
with cc1:
    st.markdown("**Precisão por categoria da questão**")
    by_cat = group_metrics(df, ["category"])
    if not by_cat.empty and by_cat["precisao"].notna().any():
        chart = (
            alt.Chart(by_cat)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("category:N", title="Categoria", sort="-y"),
                y=alt.Y("precisao:Q", title="Precisão", axis=alt.Axis(format="%")),
                color=alt.Color("category:N", scale=alt.Scale(range=_CATEGORICAL), legend=None),
                tooltip=["category", alt.Tooltip("precisao:Q", format=".2%")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("Sem categorias com métrica automática aplicável.")
with cc2:
    st.markdown("**Consistência entre repetições (desvio médio)**")
    cons = repetition_consistency(df)
    if not cons.empty:
        chart = (
            alt.Chart(cons)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("strategy:N", title="Técnica", sort=list(STRATEGY_COLORS.keys())),
                y=alt.Y("desvio_medio_repeticoes:Q", title="Desvio médio (menor = mais consistente)"),
                color=alt.Color("strategy:N", scale=_strategy_scale(), legend=None),
                tooltip=["strategy", alt.Tooltip("desvio_medio_repeticoes:Q", format=".4f")],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.caption("Repetições insuficientes para avaliar consistência (use repetitions ≥ 2).")

# Dados brutos
with st.expander("Ver registros (dados exatos armazenados)"):
    st.dataframe(df, use_container_width=True, height=320)

render_footer()
