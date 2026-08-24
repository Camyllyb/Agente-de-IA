"""Cards com números destacados (preço, retorno, volume, métricas…)."""

from __future__ import annotations

import streamlit as st

UNAVAILABLE = "Informação indisponível"


def _card_html(label: str, value: str, sub: str = "", trend: str | None = None) -> str:
    cls = ""
    if trend == "up":
        cls = "fpl-up"
    elif trend == "down":
        cls = "fpl-down"
    sub_html = f'<div class="fpl-card-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="fpl-card"><div class="fpl-card-label">{label}</div>'
        f'<div class="fpl-card-value {cls}">{value}</div>{sub_html}</div>'
    )


def stat_card(label: str, value: str, sub: str = "", trend: str | None = None) -> None:
    st.markdown(_card_html(label, value, sub, trend), unsafe_allow_html=True)


def card_row(cards: list[dict]) -> None:
    """Renderiza uma linha de cards. Cada card: {label, value, sub?, trend?}."""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            stat_card(card["label"], card.get("value", UNAVAILABLE),
                      card.get("sub", ""), card.get("trend"))


def fmt_money(value, currency: str = "BRL") -> str:
    if value is None:
        return UNAVAILABLE
    symbol = {"BRL": "R$", "USD": "US$"}.get(currency, "")
    return f"{symbol} {value:,.2f}".strip()


def fmt_pct(value) -> str:
    if value is None:
        return UNAVAILABLE
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_int(value) -> str:
    if value is None:
        return UNAVAILABLE
    return f"{int(value):,}".replace(",", ".")
