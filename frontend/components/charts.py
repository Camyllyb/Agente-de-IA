"""Gráficos (Altair) para as páginas de mercado e comparação."""

from __future__ import annotations

import altair as alt
import pandas as pd

_PRIMARY = "#1E4E79"
_PALETTE = ["#1E4E79", "#2C8C5A", "#C08A2E", "#8C4A6B", "#3A6EA5", "#6B7280"]


def price_chart(bars: list[dict], currency: str = "BRL"):
    """Linha de preço (fechamento) a partir de barras {date, close}."""
    if not bars:
        return None
    df = pd.DataFrame(bars)
    df["date"] = pd.to_datetime(df["date"])
    return (
        alt.Chart(df)
        .mark_line(color=_PRIMARY, point=alt.OverlayMarkDef(color=_PRIMARY, size=32))
        .encode(
            x=alt.X("date:T", title="Data"),
            y=alt.Y("close:Q", title=f"Preço ({currency})", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("date:T", title="Data"), alt.Tooltip("close:Q", title="Fechamento", format=".2f")],
        )
        .properties(height=320)
        .interactive()
    )


def comparison_chart(series: dict[str, list[dict]]):
    """Índice base-100 por ativo (permite comparar desempenho na mesma escala)."""
    frames = []
    for symbol, bars in series.items():
        if not bars:
            continue
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])
        base = df["close"].iloc[0]
        if not base:
            continue
        df["indice"] = df["close"] / base * 100.0
        df["ativo"] = symbol
        frames.append(df[["date", "indice", "ativo"]])
    if not frames:
        return None
    data = pd.concat(frames, ignore_index=True)
    return (
        alt.Chart(data)
        .mark_line(point=False)
        .encode(
            x=alt.X("date:T", title="Data"),
            y=alt.Y("indice:Q", title="Índice (base 100)", scale=alt.Scale(zero=False)),
            color=alt.Color("ativo:N", title="Ativo", scale=alt.Scale(range=_PALETTE)),
            tooltip=["ativo", alt.Tooltip("date:T", title="Data"), alt.Tooltip("indice:Q", format=".1f")],
        )
        .properties(height=340)
        .interactive()
    )


def bar_by(df: pd.DataFrame, x: str, y: str, x_title: str, y_title: str, pct: bool = False):
    """Barra genérica (usada no laboratório)."""
    if df is None or df.empty or df[y].isna().all():
        return None
    axis = alt.Axis(format="%") if pct else alt.Axis()
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=_PRIMARY)
        .encode(
            x=alt.X(f"{x}:N", title=x_title, sort="-y"),
            y=alt.Y(f"{y}:Q", title=y_title, axis=axis),
            tooltip=[x, alt.Tooltip(f"{y}:Q", format=".4f")],
        )
        .properties(height=280)
    )
