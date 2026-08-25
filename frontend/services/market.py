"""Acesso a dados de mercado para as páginas Mercado e Comparar.

Reutiliza o ``FinancialToolset`` existente sobre uma ``MarketDataProvider``
(snapshot ou live) — não duplica lógica do backend e não inventa valores.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.tools.financial_tools import FinancialToolset
from app.tools.market_data import get_market_data_provider

# Rótulos de fonte usados na interface.
SOURCE_LABELS = {"Base histórica": "snapshot", "Mercado atual": "live"}

PERIODS = {
    "7 dias": 7, "30 dias": 30, "3 meses": 91, "6 meses": 182, "1 ano": 365,
}

# Universo sugerido para o modo ao vivo (símbolos no formato do Yahoo/yfinance:
# ações e FIIs da B3 usam sufixo .SA). Lista de conveniência do produto.
LIVE_UNIVERSE = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBAS3.SA", "WEGE3.SA",
    "HGLG11.SA", "MXRF11.SA", "KNRI11.SA", "XPML11.SA", "VISC11.SA", "AAPL",
]


def _toolset(source: str, snapshot_set: str) -> FinancialToolset:
    provider = get_market_data_provider(source, snapshot_set=snapshot_set)
    return FinancialToolset(provider)


def available_symbols(source: str = "snapshot", snapshot_set: str = "default") -> list[str]:
    """Ativos sugeridos: do snapshot (dados congelados) ou o universo ao vivo."""
    if source == "live":
        return list(LIVE_UNIVERSE)
    provider = get_market_data_provider(source, snapshot_set=snapshot_set)
    return provider.available_symbols() if hasattr(provider, "available_symbols") else []


def reference_date(source: str, snapshot_set: str) -> date:
    """Data de referência (última cotação disponível) para calcular períodos."""
    symbols = available_symbols(source, snapshot_set)
    if symbols:
        quote = _toolset(source, snapshot_set).get_stock_quote(symbols[0])
        if quote.get("found") and quote.get("date"):
            try:
                return date.fromisoformat(quote["date"])
            except ValueError:
                pass
    return date.today()


def period_range(period_days: int, source: str, snapshot_set: str) -> tuple[str, str]:
    end = reference_date(source, snapshot_set)
    start = end - timedelta(days=period_days)
    return start.isoformat(), end.isoformat()


def get_quote(symbol: str, source: str = "snapshot", snapshot_set: str = "default") -> dict:
    return _toolset(source, snapshot_set).get_stock_quote(symbol)


def get_history(symbol: str, start: str, end: str,
                source: str = "snapshot", snapshot_set: str = "default") -> dict:
    return _toolset(source, snapshot_set).get_stock_history(symbol, start, end)


def market_overview(symbol: str, start: str, end: str,
                    source: str = "snapshot", snapshot_set: str = "default") -> dict:
    """Resumo para os cards: preço, variação, máxima, mínima, volume, data."""
    ts = _toolset(source, snapshot_set)
    quote = ts.get_stock_quote(symbol)
    history = ts.get_stock_history(symbol, start, end)

    overview = {
        "found": quote.get("found", False),
        "symbol": symbol,
        "price": quote.get("price") if quote.get("found") else None,
        "currency": quote.get("currency") if quote.get("found") else None,
        "date": quote.get("date") if quote.get("found") else None,
        "source": quote.get("source"),
        "variation_pct": None, "high": None, "low": None, "volume": None,
        "bars": [],
    }
    if history.get("found") and history.get("bars"):
        bars = history["bars"]
        closes = [b["close"] for b in bars if b.get("close") is not None]
        highs = [b["high"] for b in bars if b.get("high") is not None]
        lows = [b["low"] for b in bars if b.get("low") is not None]
        volumes = [b["volume"] for b in bars if b.get("volume") is not None]
        overview["bars"] = bars
        if len(closes) >= 2 and closes[0]:
            overview["variation_pct"] = round((closes[-1] / closes[0] - 1) * 100, 2)
        overview["high"] = max(highs) if highs else None
        overview["low"] = min(lows) if lows else None
        overview["volume"] = volumes[-1] if volumes else None
        overview["currency"] = overview["currency"] or history.get("currency")
    return overview


def compare(symbols: list[str], start: str, end: str,
            source: str = "snapshot", snapshot_set: str = "default") -> dict:
    """Retorno de cada ativo no período + destaque de maior retorno."""
    ts = _toolset(source, snapshot_set)
    rows = []
    series = {}
    for symbol in symbols:
        ret = ts.calculate_return(symbol, start, end)
        history = ts.get_stock_history(symbol, start, end)
        if history.get("found"):
            series[symbol] = history["bars"]
        if ret.get("found"):
            rows.append({
                "Ativo": symbol,
                "Inicial": ret["start_price"],
                "Final": ret["end_price"],
                "Retorno": ret["return_pct"],
                "Moeda": ret.get("currency"),
            })
        else:
            rows.append({"Ativo": symbol, "Inicial": None, "Final": None,
                         "Retorno": None, "Moeda": None})
    valid = [r for r in rows if r["Retorno"] is not None]
    best = max(valid, key=lambda r: r["Retorno"])["Ativo"] if valid else None
    return {"rows": rows, "series": series, "best_symbol": best, "source": source}
