"""Página Mercado — consulta visual de um ativo."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _p in (str(_ROOT), str(_ROOT / "frontend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from components.cards import UNAVAILABLE, card_row, fmt_int, fmt_money, fmt_pct  # noqa: E402
from components.charts import price_chart  # noqa: E402
from components.ui import empty_state, footer, inject_styles, page_header, section  # noqa: E402
from services import market  # noqa: E402

inject_styles()
page_header("Mercado", "Consulte preço, variação e histórico de um ativo.")

# --- Controles ---------------------------------------------------------------
with st.sidebar:
    st.markdown("### Configurações")
    source_label = st.radio("Fonte dos dados", ["Base histórica", "Mercado atual"])
    source = "snapshot" if source_label == "Base histórica" else "live"
    snapshot_set = "default"

symbols = market.available_symbols(source, snapshot_set)
col_a, col_b = st.columns([2, 1])
with col_a:
    default_symbol = symbols[0] if symbols else "PETR4.SA"
    symbol = st.text_input("Pesquisar ativo", value=default_symbol).strip().upper()
    if symbols:
        st.caption("Disponíveis nesta base: " + ", ".join(symbols))
with col_b:
    period_label = st.selectbox("Período", [*market.PERIODS.keys(), "Personalizado"], index=4)

if period_label == "Personalizado":
    c1, c2 = st.columns(2)
    start = c1.date_input("Início", value=date(2024, 1, 1)).isoformat()
    end = c2.date_input("Fim", value=date(2024, 7, 1)).isoformat()
else:
    start, end = market.period_range(market.PERIODS[period_label], source, snapshot_set)

if not symbol:
    empty_state("Digite um ativo para consultar", "Ex.: PETR4.SA, VALE3.SA, AAPL.")
    footer()
    st.stop()

# --- Consulta ----------------------------------------------------------------
try:
    overview = market.market_overview(symbol, start, end, source, snapshot_set)
except Exception:
    st.error("Não foi possível concluir a consulta.")
    st.caption("Verifique o ativo informado e a fonte de dados selecionada.")
    footer()
    st.stop()

if not overview["found"] and not overview["bars"]:
    empty_state(f"Informação indisponível para {symbol}",
                "Este ativo pode não existir na base selecionada ou os dados ainda não foram coletados.")
    footer()
    st.stop()

section(f"{symbol} · {source_label}")
currency = overview.get("currency") or "BRL"
trend = "up" if (overview["variation_pct"] or 0) >= 0 else "down"
card_row([
    {"label": "Preço atual", "value": fmt_money(overview["price"], currency)},
    {"label": "Variação (período)", "value": fmt_pct(overview["variation_pct"]), "trend": trend},
    {"label": "Máxima", "value": fmt_money(overview["high"], currency)},
])
card_row([
    {"label": "Mínima", "value": fmt_money(overview["low"], currency)},
    {"label": "Volume", "value": fmt_int(overview["volume"])},
    {"label": "Última atualização", "value": overview["date"] or UNAVAILABLE},
])

section("Histórico de preço")
chart = price_chart(overview["bars"], currency)
if chart is not None:
    st.altair_chart(chart, use_container_width=True)
else:
    empty_state("Sem dados no período selecionado", "Tente um período maior.")

footer()
