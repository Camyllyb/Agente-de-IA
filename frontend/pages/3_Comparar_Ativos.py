"""Página Comparar Ativos — comparação de desempenho entre 2 e 5 ativos."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from components.charts import comparison_chart  # noqa: E402
from components.ui import empty_state, footer, inject_styles, page_header, section  # noqa: E402
from services import market  # noqa: E402

inject_styles()
page_header("Comparar Ativos", "Compare o desempenho de vários ativos no mesmo período.")

with st.sidebar:
    st.markdown("### Configurações")
    source_label = st.radio("Fonte dos dados", ["Base histórica", "Mercado atual"])
    source = "snapshot" if source_label == "Base histórica" else "live"
    snapshot_set = "default"

symbols_available = market.available_symbols(source, snapshot_set)

if symbols_available:
    default = symbols_available[:2]
    selected = st.multiselect("Ativos (2 a 5)", symbols_available, default=default, max_selections=5)
else:
    raw = st.text_input("Ativos (separados por vírgula, 2 a 5)", value="PETR4.SA, VALE3.SA")
    selected = [s.strip().upper() for s in raw.split(",") if s.strip()][:5]

c1, c2 = st.columns(2)
start = c1.date_input("Data inicial", value=date(2024, 1, 1)).isoformat()
end = c2.date_input("Data final", value=date(2024, 7, 1)).isoformat()

run = st.button("Comparar", type="primary")

if not run:
    empty_state("Selecione os ativos e clique em Comparar")
    footer()
    st.stop()

if len(selected) < 2:
    st.warning("Selecione pelo menos 2 ativos.")
    footer()
    st.stop()

try:
    result = market.compare(selected, start, end, source, snapshot_set)
except Exception:
    st.error("Não foi possível concluir a consulta.")
    footer()
    st.stop()

rows = result["rows"]
if all(r["Retorno"] is None for r in rows):
    empty_state("Informação indisponível para o período/ativos selecionados",
                "Os dados podem ainda não ter sido coletados nesta base.")
    footer()
    st.stop()

# --- Tabela ------------------------------------------------------------------
section("Resultados")
display = []
for r in rows:
    variacao = None
    if r["Inicial"] is not None and r["Final"] is not None:
        variacao = round(r["Final"] - r["Inicial"], 2)
    display.append({
        "Ativo": r["Ativo"],
        "Inicial": r["Inicial"] if r["Inicial"] is not None else "N/D",
        "Final": r["Final"] if r["Final"] is not None else "N/D",
        "Retorno": f"{r['Retorno']:+.2f}%" if r["Retorno"] is not None else "N/D",
        "Variação": variacao if variacao is not None else "N/D",
    })
st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)

if result["best_symbol"]:
    st.markdown(
        f'<span class="fpl-badge ok">Maior retorno no período: {result["best_symbol"]}</span>',
        unsafe_allow_html=True,
    )
    st.caption("Nota: indicador informativo. Não constitui recomendação de investimento.")

# --- Gráfico -----------------------------------------------------------------
section("Evolução (base 100)")
chart = comparison_chart(result["series"])
if chart is not None:
    st.altair_chart(chart, use_container_width=True)
else:
    st.caption("Sem série histórica disponível para o gráfico.")

# --- FIIs --------------------------------------------------------------------
fiis = [s for s in selected if s.upper().endswith("11")]
if fiis:
    section("Fundos de Investimento Imobiliário (FIIs)")
    st.caption("Dados periódicos (CVM). Quando não coletados, permanecem como N/D.")
    fii_rows = [{
        "FII": f, "Patrimônio líquido": "N/D", "Valor patrimonial/cota": "N/D",
        "Nº de cotistas": "N/D", "Rendimento/cota": "N/D",
    } for f in fiis]
    st.dataframe(pd.DataFrame(fii_rows), use_container_width=True, hide_index=True)

footer()
