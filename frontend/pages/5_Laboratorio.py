"""Página Laboratório Experimental — pesquisa em Engenharia de Prompt."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components.cards import stat_card  # noqa: E402
from components.charts import bar_by  # noqa: E402
from components.ui import empty_state, footer, inject_styles, page_header, section  # noqa: E402

inject_styles()
page_header("Laboratório Experimental",
            "Ambiente destinado à avaliação comparativa de estratégias de Engenharia de Prompt.")

DB_PATH = str(_ROOT / "data" / "experiments.db")
_ICON = {"PASS": "✅ Pronto", "WARN": "⚠️ Pendente", "FAIL": "⚠️ Pendente"}
_LABELS = {"DATASET": "Dataset", "SNAPSHOTS": "Snapshots", "REFERENCES": "Gabaritos",
           "PROMPTS": "Prompts", "MODELS": "Modelos", "PROTOCOL": "Protocolo"}

tab_status, tab_bench, tab_run, tab_results = st.tabs(
    ["Prontidão", "Benchmark", "Executar", "Resultados"]
)

# =========================== PRONTIDÃO ======================================
with tab_status:
    from experiments.readiness import run_readiness

    report = run_readiness()
    checks = {c.name: c for c in report.checks}
    section("Status do experimento")
    names = ["DATASET", "SNAPSHOTS", "REFERENCES", "PROMPTS", "MODELS", "PROTOCOL"]
    for row_start in (0, 3):
        cols = st.columns(3)
        for col, name in zip(cols, names[row_start:row_start + 3]):
            c = checks.get(name)
            with col:
                stat_card(_LABELS[name], _ICON.get(c.status, "—") if c else "—",
                          c.details if c else "")
    if report.ready:
        st.success("FINAL EXPERIMENT READY: YES")
    else:
        st.warning("FINAL EXPERIMENT READY: NO — há itens pendentes (ver acima).")

# =========================== BENCHMARK ======================================
with tab_bench:
    section("Conjunto de questões (benchmark)")
    dataset_path = _ROOT / "experiments" / "datasets" / "benchmark_v2.json"
    if not dataset_path.exists():
        empty_state("Dataset do benchmark ainda não gerado",
                    "Importe a planilha para gerar o benchmark de 30 questões.")
    else:
        from experiments.datasets.benchmark_loader import load_benchmark_dataset

        dataset = load_benchmark_dataset(dataset_path)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de questões", len(dataset.questions))
        c2.metric("Categorias", len(dataset.category_counts()))
        c3.metric("Dificuldades", len(dataset.difficulty_counts()))
        cc1, cc2 = st.columns(2)
        with cc1:
            st.caption("Por categoria")
            st.dataframe(pd.DataFrame(dataset.category_counts().items(),
                                      columns=["Categoria", "Questões"]),
                         hide_index=True, use_container_width=True)
        with cc2:
            st.caption("Por dificuldade")
            st.dataframe(pd.DataFrame(dataset.difficulty_counts().items(),
                                      columns=["Dificuldade", "Questões"]),
                         hide_index=True, use_container_width=True)
        st.caption(f"Versão do dataset: {dataset.dataset_version} · congelado: {dataset.frozen}")

# =========================== EXECUTAR =======================================
with tab_run:
    section("Configuração do experimento")
    STRAT = {"Zero-shot": "zero_shot", "Few-shot": "few_shot", "Raciocínio estruturado": "chain_of_thought"}
    exp_label = st.radio("Experimento", ["Agente", "LLM isolado"], horizontal=True)
    experiment_type = "agent" if exp_label == "Agente" else "llm_only"
    tech_labels = st.multiselect("Técnicas", list(STRAT.keys()), default=list(STRAT.keys()))
    techniques = [STRAT[t] for t in tech_labels]
    colr1, colr2 = st.columns(2)
    repetitions = colr1.number_input("Repetições", min_value=1, max_value=10, value=3)
    n_questions = colr2.number_input("Questões (piloto offline)", min_value=1, max_value=20, value=10)

    planned = len(techniques) * repetitions * int(n_questions)
    st.info(f"Chamadas previstas: **{planned}**")
    from app.metrics import load_price_table
    price_table = load_price_table()
    if price_table.is_configured():
        st.caption("Custo estimado disponível pela tabela de preços configurada.")
    else:
        st.caption("Custo estimado: tabela de preços não configurada (custo permanecerá nulo).")

    st.divider()
    section("Piloto offline (seguro)")
    st.caption("Executa um piloto determinístico com o oráculo (sem chave, sem internet). "
               "Rotulado PILOT_ONLY — não é um resultado científico.")
    if st.button("Executar piloto offline", type="primary"):
        with st.spinner("Executando piloto offline…"):
            from experiments.pilot import PilotConfig, run_pilot
            from experiments.runner import ResultStore, oracle_model_spec

            store = ResultStore(DB_PATH)
            cfg = PilotConfig(num_questions=int(n_questions), strategies=techniques or ["zero_shot"],
                              repetitions=int(repetitions), experiment_type="agent")
            summary, prechecks, audit = run_pilot(store, oracle_model_spec(), cfg)
            store.close()
        if summary is None:
            st.error("Piloto interrompido nas pré-checagens.")
        else:
            st.success(f"Piloto concluído: {summary.executed} execuções, "
                       f"{summary.succeeded} ok, {summary.failed} falhas. Veja a aba Resultados.")
            with st.expander("Relatório de auditoria do piloto (PILOT_ONLY)"):
                st.json(audit)

    st.divider()
    section("Experimento final")
    if not report.ready:
        pending = [_LABELS.get(c.name, c.name) for c in report.checks
                   if c.name in _LABELS and c.status != "PASS"]
        st.warning("Experimento final bloqueado. Pendências: " + ", ".join(pending))
        st.button("Executar experimento final", disabled=True,
                  help="Requer prontidão total (readiness).")
    else:
        confirm = st.checkbox("Confirmo que desejo executar o experimento final (chamadas reais).")
        st.button("Executar experimento final", disabled=not confirm)
        st.caption("O experimento final usa provedores reais e exige dupla confirmação.")

# =========================== RESULTADOS =====================================
with tab_results:
    from experiments.analysis import (
        group_metrics, list_experiments, load_scored_dataframe, overview,
        technique_comparison,
    )

    experiments = list_experiments(DB_PATH)
    if not experiments:
        empty_state("Nenhum resultado armazenado ainda",
                    "Execute o piloto offline na aba Executar para gerar dados.")
        footer()
        st.stop()

    exp_choice = st.selectbox("Experimento", ["Todos", *experiments])
    df = load_scored_dataframe(DB_PATH, None if exp_choice == "Todos" else exp_choice)
    if df.empty:
        empty_state("Sem registros para o experimento selecionado.")
        footer()
        st.stop()

    if (df["model"] == "oracle-fake").any():
        st.warning("Contém resultados do oráculo determinístico — não representam desempenho de LLM real.")

    section("Visão geral")
    ov = overview(df)
    cols = st.columns(5)
    cols[0].metric("Execuções", ov["total"])
    cols[1].metric("Sucessos", ov["success"])
    cols[2].metric("Erros", ov["errors"])
    cols[3].metric("Modelos", ov["models"])
    cols[4].metric("Técnicas", ov["techniques"])

    section("Qualidade e eficiência por técnica")
    comp = technique_comparison(df)
    st.dataframe(comp, use_container_width=True, hide_index=True)

    if (df.get("experiment_type") == "agent").any():
        from app.metrics import (data_grounding_accuracy, task_success_rate,
                                  tool_execution_success_rate, tool_selection_accuracy)
        rows = df[df["experiment_type"] == "agent"].to_dict("records")
        section("Métricas do agente")
        a = st.columns(4)
        _p = lambda v: f"{v:.1%}" if v is not None else "—"  # noqa: E731
        a[0].metric("Tool Selection", _p(tool_selection_accuracy(rows)))
        a[1].metric("Tool Execution", _p(tool_execution_success_rate(rows)))
        a[2].metric("Data Grounding", _p(data_grounding_accuracy(rows)))
        a[3].metric("Task Success", _p(task_success_rate(rows)))

    section("Gráficos")
    g1, g2 = st.columns(2)
    with g1:
        chart = bar_by(comp, "strategy", "precisao", "Técnica", "Precisão", pct=True)
        st.altair_chart(chart, use_container_width=True) if chart is not None else st.caption("Sem dados de precisão.")
        chart = bar_by(comp, "strategy", "tokens_total_medio", "Técnica", "Tokens")
        st.altair_chart(chart, use_container_width=True) if chart is not None else st.caption("Sem dados de tokens.")
    with g2:
        chart = bar_by(comp, "strategy", "latencia_ms_media", "Técnica", "Latência (ms)")
        st.altair_chart(chart, use_container_width=True) if chart is not None else st.caption("Sem dados de latência.")
        by_cat = group_metrics(df, ["category"])
        chart = bar_by(by_cat, "category", "precisao", "Categoria", "Precisão", pct=True)
        st.altair_chart(chart, use_container_width=True) if chart is not None else st.caption("Sem dados por categoria.")

    if "difficulty" in df.columns and df["difficulty"].notna().any():
        by_diff = group_metrics(df, ["difficulty"])
        chart = bar_by(by_diff, "difficulty", "precisao", "Dificuldade", "Precisão", pct=True)
        if chart is not None:
            section("Desempenho por dificuldade")
            st.altair_chart(chart, use_container_width=True)

footer()
