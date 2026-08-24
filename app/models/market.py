"""Modelos de dados financeiros (independentes da fonte).

Toda resposta de ferramenta identifica: ativo, data, valor, moeda e fonte.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HistoryBar(BaseModel):
    """Uma barra (candle) de histórico de preços."""

    date: str = Field(..., description="Data no formato ISO (YYYY-MM-DD).")
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float = Field(..., description="Preço de fechamento.")
    volume: int | None = None


class Quote(BaseModel):
    """Cotação de um ativo em um instante."""

    symbol: str
    price: float
    currency: str
    date: str = Field(..., description="Data da cotação (ISO).")
    timestamp: str | None = Field(None, description="Timestamp da cotação (ISO), se houver.")
    source: str = Field(..., description="Fonte dos dados (ex.: 'snapshot:default').")


class StockHistory(BaseModel):
    """Histórico de preços de um ativo em um período."""

    symbol: str
    currency: str
    source: str
    start_date: str
    end_date: str
    bars: list[HistoryBar] = Field(default_factory=list)
